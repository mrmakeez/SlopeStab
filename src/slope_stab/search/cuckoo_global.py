from __future__ import annotations

from dataclasses import dataclass
import math
import random

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, CuckooGlobalSearchInput, PrescribedCircleInput
from slope_stab.search.auto_refine import _run_toe_crest_refinement, _run_toe_locked_beta_refinement
from slope_stab.search.common import TIE_TOL, SurfaceEvaluator, X_SEP_MIN, repair_vector_clip, surface_key
from slope_stab.search.objective_evaluator import (
    CachedObjectiveEvaluator,
    ObjectiveEvaluation,
    ObjectiveScoringPolicy,
)
from slope_stab.search.post_polish import default_post_polish_refine_config


_VALID_INIT_ATTEMPTS_FACTOR = 200


@dataclass(frozen=True)
class CuckooIterationDiagnostics:
    iteration: int
    alpha: float
    total_evaluations: int
    valid_evaluations: int
    infeasible_evaluations: int
    replacements: int
    abandoned: int
    incumbent_fos: float


@dataclass(frozen=True)
class CuckooGlobalSearchResult:
    winning_surface: PrescribedCircleInput
    winning_result: AnalysisResult
    iteration_diagnostics: list[CuckooIterationDiagnostics]
    total_evaluations: int
    valid_evaluations: int
    infeasible_evaluations: int
    termination_reason: str


@dataclass(frozen=True)
class _Nest:
    vector: tuple[float, float, float]
    evaluation: ObjectiveEvaluation


def _alpha_for_iteration(config: CuckooGlobalSearchInput, iteration: int) -> float:
    if config.max_iterations <= 1:
        return config.alpha_min
    ratio = iteration / config.max_iterations
    decay = math.log(config.alpha_min / config.alpha_max)
    return config.alpha_max * math.exp(decay * ratio)


def _levy_sigma(beta: float) -> float:
    return (
        (
            math.gamma(1.0 + beta)
            * math.sin(math.pi * beta / 2.0)
            / (math.gamma((1.0 + beta) / 2.0) * beta * (2.0 ** ((beta - 1.0) / 2.0)))
        )
        ** (1.0 / beta)
    )


def _levy_step(rng: random.Random, beta: float, sigma_u: float) -> tuple[float, float, float]:
    def draw() -> float:
        u = rng.gauss(0.0, sigma_u)
        v = rng.gauss(0.0, 1.0)
        return u / ((abs(v) ** (1.0 / beta)) + 1e-12)

    return (draw(), draw(), draw())


def _candidate_rank(evaluation: ObjectiveEvaluation) -> tuple[float, tuple[float, float, float]]:
    if not math.isfinite(evaluation.score):
        return (float("inf"), (float("inf"), float("inf"), float("inf")))
    if evaluation.surface is None:
        return (evaluation.score, (float("inf"), float("inf"), float("inf")))
    return (evaluation.score, surface_key(evaluation.surface))


def _is_better(candidate: ObjectiveEvaluation, incumbent: ObjectiveEvaluation) -> bool:
    cand_rank = _candidate_rank(candidate)
    inc_rank = _candidate_rank(incumbent)
    if cand_rank[0] < inc_rank[0] - TIE_TOL:
        return True
    if abs(cand_rank[0] - inc_rank[0]) <= TIE_TOL and cand_rank[1] < inc_rank[1]:
        return True
    return False


def run_cuckoo_global_search(
    profile: UniformSlopeProfile,
    config: CuckooGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> CuckooGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= X_SEP_MIN:
        raise GeometryError("Cuckoo search limits must satisfy x_max - x_min > 0.05 m.")

    rng = random.Random(config.seed)
    sigma_u = _levy_sigma(config.levy_beta)
    evaluator = CachedObjectiveEvaluator(
        profile=profile,
        x_min=x_min,
        x_max=x_max,
        max_evaluations=config.max_evaluations,
        evaluate_surface=evaluate_surface,
        policy=ObjectiveScoringPolicy(
            repair_vector=repair_vector_clip,
            invalid_geometry_score=float("inf"),
            invalid_result_score=float("inf"),
            evaluation_exception_score=float("inf"),
            keep_invalid_payload=False,
        ),
        driving_moment_tol=1e-9,
    )

    def random_vector() -> tuple[float, float, float]:
        return (rng.random(), rng.random(), rng.random())

    population: list[_Nest] = []
    attempts = 0
    max_attempts = config.population_size * _VALID_INIT_ATTEMPTS_FACTOR
    while len(population) < config.population_size and attempts < max_attempts:
        attempts += 1
        evaluation = evaluator.evaluate_vector(random_vector())
        if math.isfinite(evaluation.score):
            population.append(_Nest(vector=evaluation.vector, evaluation=evaluation))

    while len(population) < config.population_size:
        evaluation = evaluator.evaluate_vector(random_vector())
        population.append(_Nest(vector=evaluation.vector, evaluation=evaluation))

    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("Cuckoo search did not produce any valid surfaces in initialization.")

    diagnostics: list[CuckooIterationDiagnostics] = []
    best_history: list[float] = []
    termination_reason = "max_iterations"

    for iteration in range(1, config.max_iterations + 1):
        if evaluator.total_evaluations >= config.max_evaluations:
            termination_reason = "max_evaluations"
            break

        alpha = _alpha_for_iteration(config, iteration)
        replacements = 0
        abandoned = 0

        for nest in population:
            if evaluator.total_evaluations >= config.max_evaluations:
                termination_reason = "max_evaluations"
                break

            step = _levy_step(rng, config.levy_beta, sigma_u)
            trial_raw = (
                nest.vector[0] + alpha * step[0],
                nest.vector[1] + alpha * step[1],
                nest.vector[2] + alpha * step[2],
            )
            trial_eval = evaluator.evaluate_vector(trial_raw)

            target_idx = rng.randrange(len(population))
            target = population[target_idx]
            if _is_better(trial_eval, target.evaluation):
                population[target_idx] = _Nest(vector=trial_eval.vector, evaluation=trial_eval)
                replacements += 1

        if evaluator.total_evaluations < config.max_evaluations:
            abandon_count = max(1, math.ceil(config.discovery_rate * config.population_size))
            ranked = sorted(
                enumerate(population),
                key=lambda item: (_candidate_rank(item[1].evaluation), item[0]),
            )
            worst_indices = [idx for idx, _ in ranked[-abandon_count:]]
            for idx in worst_indices:
                if evaluator.total_evaluations >= config.max_evaluations:
                    termination_reason = "max_evaluations"
                    break
                evaluation = evaluator.evaluate_vector(random_vector())
                population[idx] = _Nest(vector=evaluation.vector, evaluation=evaluation)
                abandoned += 1

        if evaluator.best_surface is None or evaluator.best_result is None:
            raise ConvergenceError("Cuckoo search lost incumbent surface unexpectedly.")

        best_history.append(evaluator.best_result.fos)
        diagnostics.append(
            CuckooIterationDiagnostics(
                iteration=iteration,
                alpha=alpha,
                total_evaluations=evaluator.total_evaluations,
                valid_evaluations=evaluator.valid_evaluations,
                infeasible_evaluations=evaluator.infeasible_evaluations,
                replacements=replacements,
                abandoned=abandoned,
                incumbent_fos=evaluator.best_result.fos,
            )
        )

        if len(best_history) > config.stall_iterations:
            previous = best_history[-config.stall_iterations - 1]
            current = best_history[-1]
            if math.isfinite(previous) and math.isfinite(current):
                if (previous - current) < config.min_improvement:
                    termination_reason = "stall_tolerance_reached"
                    break

    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("Cuckoo search did not produce any valid surfaces.")

    best_surface = evaluator.best_surface
    best_result = evaluator.best_result
    if config.post_polish:
        refine_config = default_post_polish_refine_config(config.search_limits)
        best_surface, best_result = _run_toe_crest_refinement(
            profile=profile,
            config=refine_config,
            evaluate_surface=evaluate_surface,
            best_surface=best_surface,
            best_result=best_result,
        )
        best_surface, best_result = _run_toe_locked_beta_refinement(
            profile=profile,
            config=refine_config,
            evaluate_surface=evaluate_surface,
            best_surface=best_surface,
            best_result=best_result,
        )

    return CuckooGlobalSearchResult(
        winning_surface=best_surface,
        winning_result=best_result,
        iteration_diagnostics=diagnostics,
        total_evaluations=evaluator.total_evaluations,
        valid_evaluations=evaluator.valid_evaluations,
        infeasible_evaluations=evaluator.infeasible_evaluations,
        termination_reason=termination_reason,
    )
