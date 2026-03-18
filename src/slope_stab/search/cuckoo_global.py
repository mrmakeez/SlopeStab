from __future__ import annotations

from dataclasses import dataclass
import math
import random

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisResult,
    AutoRefineSearchInput,
    CuckooGlobalSearchInput,
    PrescribedCircleInput,
)
from slope_stab.search.auto_refine import _run_toe_crest_refinement, _run_toe_locked_beta_refinement
from slope_stab.search.common import (
    CACHE_ROUND,
    TIE_TOL,
    X_SEP_MIN,
    SurfaceEvaluator,
    evaluate_surface_candidate,
    is_better_score,
    map_vector_to_surface,
    repair_vector_clip,
    round_vector,
    surface_key,
)


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
class _Evaluation:
    value: float
    surface: PrescribedCircleInput | None
    result: AnalysisResult | None


@dataclass(frozen=True)
class _Nest:
    vector: tuple[float, float, float]
    evaluation: _Evaluation


def _alpha_for_iteration(config: CuckooGlobalSearchInput, iteration: int) -> float:
    if config.max_iterations <= 1:
        return config.alpha_min
    ratio = iteration / config.max_iterations
    decay = math.log(config.alpha_min / config.alpha_max)
    return config.alpha_max * math.exp(decay * ratio)


def _levy_step(rng: random.Random, beta: float) -> tuple[float, float, float]:
    sigma_u = (
        (
            math.gamma(1.0 + beta)
            * math.sin(math.pi * beta / 2.0)
            / (math.gamma((1.0 + beta) / 2.0) * beta * (2.0 ** ((beta - 1.0) / 2.0)))
        )
        ** (1.0 / beta)
    )

    def draw() -> float:
        u = rng.gauss(0.0, sigma_u)
        v = rng.gauss(0.0, 1.0)
        return u / ((abs(v) ** (1.0 / beta)) + 1e-12)

    return (draw(), draw(), draw())


def _candidate_rank(evaluation: _Evaluation) -> tuple[float, tuple[float, float, float]]:
    if not math.isfinite(evaluation.value):
        return (float("inf"), (float("inf"), float("inf"), float("inf")))
    if evaluation.surface is None:
        return (evaluation.value, (float("inf"), float("inf"), float("inf")))
    return (evaluation.value, surface_key(evaluation.surface))


def _is_better(candidate: _Evaluation, incumbent: _Evaluation) -> bool:
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
    cache: dict[tuple[float, float, float], _Evaluation] = {}

    total_evaluations = 0
    valid_evaluations = 0
    infeasible_evaluations = 0
    best_surface: PrescribedCircleInput | None = None
    best_result: AnalysisResult | None = None
    best_value = float("inf")

    def evaluate_point(vector: tuple[float, float, float]) -> _Evaluation:
        nonlocal total_evaluations, valid_evaluations, infeasible_evaluations
        nonlocal best_surface, best_result, best_value

        key = round_vector(repair_vector_clip(vector), digits=CACHE_ROUND)
        cached = cache.get(key)
        if cached is not None:
            return cached

        if total_evaluations >= config.max_evaluations:
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        total_evaluations += 1
        surface = map_vector_to_surface(
            profile=profile,
            x_min=x_min,
            x_max=x_max,
            vector=key,
            repair_vector=repair_vector_clip,
        )
        candidate = evaluate_surface_candidate(surface, evaluate_surface, driving_moment_tol=1e-9)
        if not candidate.valid or candidate.surface is None or candidate.result is None:
            infeasible_evaluations += 1
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        valid_evaluations += 1
        result = candidate.result
        surface = candidate.surface
        value = result.fos
        if is_better_score(value, surface, best_value, best_surface):
            best_value = value
            best_surface = surface
            best_result = result
        elif best_surface is None:
            best_value = value
            best_surface = surface
            best_result = result

        evaluation = _Evaluation(value=value, surface=surface, result=result)
        cache[key] = evaluation
        return evaluation

    def random_vector() -> tuple[float, float, float]:
        return (rng.random(), rng.random(), rng.random())

    population: list[_Nest] = []
    attempts = 0
    max_attempts = config.population_size * _VALID_INIT_ATTEMPTS_FACTOR
    while len(population) < config.population_size and attempts < max_attempts:
        attempts += 1
        vector = random_vector()
        evaluation = evaluate_point(vector)
        if math.isfinite(evaluation.value):
            population.append(_Nest(vector=round_vector(vector, digits=CACHE_ROUND), evaluation=evaluation))

    while len(population) < config.population_size:
        vector = random_vector()
        evaluation = evaluate_point(vector)
        population.append(_Nest(vector=round_vector(vector, digits=CACHE_ROUND), evaluation=evaluation))

    if best_surface is None or best_result is None:
        raise ConvergenceError("Cuckoo search did not produce any valid surfaces in initialization.")

    diagnostics: list[CuckooIterationDiagnostics] = []
    best_history: list[float] = []
    termination_reason = "max_iterations"

    for iteration in range(1, config.max_iterations + 1):
        if total_evaluations >= config.max_evaluations:
            termination_reason = "max_evaluations"
            break

        alpha = _alpha_for_iteration(config, iteration)
        replacements = 0
        abandoned = 0

        for nest in population:
            if total_evaluations >= config.max_evaluations:
                termination_reason = "max_evaluations"
                break

            step = _levy_step(rng, config.levy_beta)
            trial_vector = repair_vector_clip(
                (
                    nest.vector[0] + alpha * step[0],
                    nest.vector[1] + alpha * step[1],
                    nest.vector[2] + alpha * step[2],
                )
            )
            trial_vector = round_vector(trial_vector, digits=CACHE_ROUND)
            trial_eval = evaluate_point(trial_vector)

            target_idx = rng.randrange(len(population))
            target = population[target_idx]
            if _is_better(trial_eval, target.evaluation):
                population[target_idx] = _Nest(vector=trial_vector, evaluation=trial_eval)
                replacements += 1

        if total_evaluations < config.max_evaluations:
            abandon_count = max(1, math.ceil(config.discovery_rate * config.population_size))
            ranked = sorted(
                enumerate(population),
                key=lambda item: (_candidate_rank(item[1].evaluation), item[0]),
            )
            worst_indices = [idx for idx, _ in ranked[-abandon_count:]]
            for idx in worst_indices:
                if total_evaluations >= config.max_evaluations:
                    termination_reason = "max_evaluations"
                    break
                vector = round_vector(random_vector(), digits=CACHE_ROUND)
                evaluation = evaluate_point(vector)
                population[idx] = _Nest(vector=vector, evaluation=evaluation)
                abandoned += 1

        if best_surface is None or best_result is None:
            raise ConvergenceError("Cuckoo search lost incumbent surface unexpectedly.")

        best_history.append(best_result.fos)
        diagnostics.append(
            CuckooIterationDiagnostics(
                iteration=iteration,
                alpha=alpha,
                total_evaluations=total_evaluations,
                valid_evaluations=valid_evaluations,
                infeasible_evaluations=infeasible_evaluations,
                replacements=replacements,
                abandoned=abandoned,
                incumbent_fos=best_result.fos,
            )
        )

        if len(best_history) > config.stall_iterations:
            previous = best_history[-config.stall_iterations - 1]
            current = best_history[-1]
            if math.isfinite(previous) and math.isfinite(current):
                if (previous - current) < config.min_improvement:
                    termination_reason = "stall_tolerance_reached"
                    break

    if best_surface is None or best_result is None:
        raise ConvergenceError("Cuckoo search did not produce any valid surfaces.")

    if config.post_polish:
        refine_config = AutoRefineSearchInput(
            divisions_along_slope=2,
            circles_per_division=15,
            iterations=1,
            divisions_to_use_next_iteration_pct=50.0,
            search_limits=config.search_limits,
        )
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
        total_evaluations=total_evaluations,
        valid_evaluations=valid_evaluations,
        infeasible_evaluations=infeasible_evaluations,
        termination_reason=termination_reason,
    )
