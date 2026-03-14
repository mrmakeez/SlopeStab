from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisResult,
    AutoRefineSearchInput,
    CuckooGlobalSearchInput,
    PrescribedCircleInput,
)
from slope_stab.search.auto_refine import _run_toe_crest_refinement, _run_toe_locked_beta_refinement


SurfaceEvaluator = Callable[[PrescribedCircleInput], AnalysisResult]

_X_SEP_MIN = 0.05
_BETA_MIN_RAD = math.radians(0.5)
_BETA_MAX_RAD = math.radians(89.5)
_TIE_TOL = 1e-12
_CACHE_ROUND = 15
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


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _repair_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (_clip01(vector[0]), _clip01(vector[1]), _clip01(vector[2]))


def _surface_key(surface: PrescribedCircleInput) -> tuple[float, float, float]:
    return (surface.x_left, surface.x_right, surface.r)


def _round_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (round(vector[0], _CACHE_ROUND), round(vector[1], _CACHE_ROUND), round(vector[2], _CACHE_ROUND))


def _map_to_surface(
    profile: UniformSlopeProfile,
    x_min: float,
    x_max: float,
    vector: tuple[float, float, float],
) -> PrescribedCircleInput | None:
    u_left, u_span, u_beta = _repair_vector(vector)
    width = x_max - x_min
    if width <= _X_SEP_MIN:
        return None

    left_range = width - _X_SEP_MIN
    x_left = x_min + u_left * left_range
    right_range = x_max - x_left - _X_SEP_MIN
    if right_range < 0.0:
        return None

    x_right = x_left + _X_SEP_MIN + u_span * right_range
    if x_right <= x_left:
        return None

    y_left = profile.y_ground(x_left)
    y_right = profile.y_ground(x_right)
    beta = _BETA_MIN_RAD + u_beta * (_BETA_MAX_RAD - _BETA_MIN_RAD)
    return _circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)


def _circle_from_endpoints_and_tangent(
    p_left: tuple[float, float],
    p_right: tuple[float, float],
    beta: float,
) -> PrescribedCircleInput | None:
    x1, y1 = p_left
    x2, y2 = p_right
    if x2 <= x1:
        return None
    if beta <= 0.0 or beta >= 0.5 * math.pi:
        return None

    dx = x2 - x1
    dy = y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0.0:
        return None

    sin_beta = math.sin(beta)
    tan_beta = math.tan(beta)
    if abs(sin_beta) <= 1e-12 or abs(tan_beta) <= 1e-12:
        return None

    radius = chord / (2.0 * sin_beta)
    center_offset = chord / (2.0 * tan_beta)
    if radius <= 0.0 or not math.isfinite(radius) or not math.isfinite(center_offset):
        return None

    mid_x = 0.5 * (x1 + x2)
    mid_y = 0.5 * (y1 + y2)

    normal_x = -dy / chord
    normal_y = dx / chord
    if normal_y < 0.0:
        normal_x = -normal_x
        normal_y = -normal_y

    xc = mid_x + center_offset * normal_x
    yc = mid_y + center_offset * normal_y
    if not math.isfinite(xc) or not math.isfinite(yc):
        return None
    if yc <= max(y1, y2) + 1e-9:
        return None

    return PrescribedCircleInput(
        xc=xc,
        yc=yc,
        r=radius,
        x_left=x1,
        y_left=y1,
        x_right=x2,
        y_right=y2,
    )


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
    return (evaluation.value, _surface_key(evaluation.surface))


def _is_better(candidate: _Evaluation, incumbent: _Evaluation) -> bool:
    cand_rank = _candidate_rank(candidate)
    inc_rank = _candidate_rank(incumbent)
    if cand_rank[0] < inc_rank[0] - _TIE_TOL:
        return True
    if abs(cand_rank[0] - inc_rank[0]) <= _TIE_TOL and cand_rank[1] < inc_rank[1]:
        return True
    return False


def run_cuckoo_global_search(
    profile: UniformSlopeProfile,
    config: CuckooGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> CuckooGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= _X_SEP_MIN:
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

        key = _round_vector(_repair_vector(vector))
        cached = cache.get(key)
        if cached is not None:
            return cached

        if total_evaluations >= config.max_evaluations:
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        total_evaluations += 1
        surface = _map_to_surface(profile=profile, x_min=x_min, x_max=x_max, vector=key)
        if surface is None:
            infeasible_evaluations += 1
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        try:
            result = evaluate_surface(surface)
        except (ConvergenceError, GeometryError, ValueError):
            infeasible_evaluations += 1
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        if (
            (not result.converged)
            or (not math.isfinite(result.fos))
            or result.fos <= 0.0
            or (not math.isfinite(result.driving_moment))
            or abs(result.driving_moment) <= 1e-9
            or (not math.isfinite(result.resisting_moment))
        ):
            infeasible_evaluations += 1
            evaluation = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = evaluation
            return evaluation

        valid_evaluations += 1
        value = result.fos

        if (value < best_value - _TIE_TOL) or (
            abs(value - best_value) <= _TIE_TOL
            and best_surface is not None
            and _surface_key(surface) < _surface_key(best_surface)
        ):
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
            population.append(_Nest(vector=_round_vector(vector), evaluation=evaluation))

    while len(population) < config.population_size:
        vector = random_vector()
        evaluation = evaluate_point(vector)
        population.append(_Nest(vector=_round_vector(vector), evaluation=evaluation))

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
            trial_vector = _repair_vector(
                (
                    nest.vector[0] + alpha * step[0],
                    nest.vector[1] + alpha * step[1],
                    nest.vector[2] + alpha * step[2],
                )
            )
            trial_vector = _round_vector(trial_vector)
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
                vector = _round_vector(random_vector())
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
