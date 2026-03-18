from __future__ import annotations

from dataclasses import dataclass
import math

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, AutoRefineSearchInput, DirectGlobalSearchInput, PrescribedCircleInput
from slope_stab.search.auto_refine import _run_toe_crest_refinement, _run_toe_locked_beta_refinement
from slope_stab.search.common import (
    CACHE_ROUND,
    TIE_TOL,
    X_SEP_MIN,
    SurfaceEvaluator,
    clip01,
    evaluate_surface_candidate,
    is_better_score,
    map_vector_to_surface,
    repair_vector_clip,
    round_vector,
)


_SIZE_ROUND = 15
_DIMENSIONS = 3
_LIPSCHITZ_POWERS = tuple(range(-6, 7))


@dataclass(frozen=True)
class DirectIterationDiagnostics:
    iteration: int
    total_evaluations: int
    potentially_optimal_count: int
    incumbent_fos: float
    min_rectangle_half_size: float


@dataclass(frozen=True)
class DirectGlobalSearchResult:
    winning_surface: PrescribedCircleInput
    winning_result: AnalysisResult
    iteration_diagnostics: list[DirectIterationDiagnostics]
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
class _Rectangle:
    rect_id: int
    center: tuple[float, float, float]
    half_sizes: tuple[float, float, float]
    value: float
    surface: PrescribedCircleInput | None
    result: AnalysisResult | None

    @property
    def size_metric(self) -> float:
        return max(self.half_sizes)


def _best_rect_per_size(rectangles: list[_Rectangle]) -> list[_Rectangle]:
    best_by_size: dict[float, _Rectangle] = {}
    for rect in rectangles:
        key = round(rect.size_metric, _SIZE_ROUND)
        current = best_by_size.get(key)
        if current is None:
            best_by_size[key] = rect
            continue
        if rect.value < current.value - TIE_TOL:
            best_by_size[key] = rect
            continue
        if abs(rect.value - current.value) <= TIE_TOL and rect.rect_id < current.rect_id:
            best_by_size[key] = rect

    return sorted(best_by_size.values(), key=lambda r: (r.size_metric, r.value, r.rect_id))


def _select_potentially_optimal(rectangles: list[_Rectangle], incumbent_id: int) -> list[_Rectangle]:
    if not rectangles:
        return []
    reduced = _best_rect_per_size(rectangles)
    selected: dict[int, _Rectangle] = {}

    # Deterministic DIRECT-style lower-envelope probing over a fixed K grid.
    k_values = [0.0] + [10.0 ** power for power in _LIPSCHITZ_POWERS]
    for k in k_values:
        chosen = min(
            reduced,
            key=lambda r: (r.value - k * r.size_metric, r.value, r.rect_id),
        )
        selected[chosen.rect_id] = chosen

    if incumbent_id not in selected:
        incumbent_rect = next((rect for rect in rectangles if rect.rect_id == incumbent_id), None)
        if incumbent_rect is not None:
            selected[incumbent_rect.rect_id] = incumbent_rect

    if not selected:
        fallback = min(rectangles, key=lambda r: (r.value, r.rect_id))
        selected[fallback.rect_id] = fallback

    return sorted(selected.values(), key=lambda r: r.rect_id)


def run_direct_global_search(
    profile: UniformSlopeProfile,
    config: DirectGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> DirectGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= X_SEP_MIN:
        raise GeometryError("DIRECT search limits must satisfy x_max - x_min > 0.05 m.")

    cache: dict[tuple[float, float, float], _Evaluation] = {}
    total_evaluations = 0
    valid_evaluations = 0
    infeasible_evaluations = 0
    next_rect_id = 0

    best_surface: PrescribedCircleInput | None = None
    best_result: AnalysisResult | None = None
    best_value = float("inf")

    def evaluate_point(u: tuple[float, float, float]) -> _Evaluation:
        nonlocal total_evaluations, valid_evaluations, infeasible_evaluations
        nonlocal best_surface, best_result, best_value

        key = round_vector(u, digits=CACHE_ROUND)
        cached = cache.get(key)
        if cached is not None:
            return cached

        if total_evaluations >= config.max_evaluations:
            eval_result = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = eval_result
            return eval_result

        total_evaluations += 1
        surface = map_vector_to_surface(
            profile=profile,
            x_min=x_min,
            x_max=x_max,
            vector=key,
            repair_vector=repair_vector_clip,
        )
        evaluation = evaluate_surface_candidate(surface, evaluate_surface, driving_moment_tol=1e-9)
        if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
            infeasible_evaluations += 1
            eval_result = _Evaluation(value=float("inf"), surface=None, result=None)
            cache[key] = eval_result
            return eval_result

        valid_evaluations += 1
        result = evaluation.result
        surface = evaluation.surface
        value = result.fos
        if is_better_score(value, surface, best_value, best_surface):
            best_value = value
            best_surface = surface
            best_result = result
        elif best_surface is None:
            best_value = value
            best_surface = surface
            best_result = result

        eval_result = _Evaluation(value=value, surface=surface, result=result)
        cache[key] = eval_result
        return eval_result

    def make_rectangle(center: tuple[float, float, float], half_sizes: tuple[float, float, float]) -> _Rectangle:
        nonlocal next_rect_id
        evaluation = evaluate_point(center)
        rect = _Rectangle(
            rect_id=next_rect_id,
            center=center,
            half_sizes=half_sizes,
            value=evaluation.value,
            surface=evaluation.surface,
            result=evaluation.result,
        )
        next_rect_id += 1
        return rect

    # Deterministic broad initialization: trisect each parameter once to seed
    # 3x3x3 boxes and avoid early lock-in to a single local basin.
    centers_1d = (1.0 / 6.0, 0.5, 5.0 / 6.0)
    base_half_sizes = (1.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0)
    rectangles: list[_Rectangle] = []
    for u0 in centers_1d:
        for u1 in centers_1d:
            for u2 in centers_1d:
                rectangles.append(make_rectangle((u0, u1, u2), base_half_sizes))

    if not rectangles:
        raise ConvergenceError("DIRECT search initialization failed.")
    if best_surface is None or best_result is None:
        raise ConvergenceError("DIRECT search did not produce any valid surfaces from the initial rectangle.")

    incumbent_rect_id = min(rectangles, key=lambda r: (r.value, r.rect_id)).rect_id
    diagnostics: list[DirectIterationDiagnostics] = []
    best_history: list[float] = []
    termination_reason = "max_iterations"

    for iteration in range(1, config.max_iterations + 1):
        if total_evaluations >= config.max_evaluations:
            termination_reason = "max_evaluations"
            break

        selected = _select_potentially_optimal(rectangles, incumbent_rect_id)
        selected_ids = {rect.rect_id for rect in selected}

        next_rectangles: list[_Rectangle] = [rect for rect in rectangles if rect.rect_id not in selected_ids]
        for rect in selected:
            half_sizes = rect.half_sizes
            split_dim = min(
                (i for i in range(_DIMENSIONS) if abs(half_sizes[i] - max(half_sizes)) <= TIE_TOL),
                default=0,
            )
            delta = half_sizes[split_dim] / 3.0
            new_half_sizes = list(half_sizes)
            new_half_sizes[split_dim] = delta
            child_half_sizes = (new_half_sizes[0], new_half_sizes[1], new_half_sizes[2])

            for shift in (-delta, 0.0, delta):
                child_center = list(rect.center)
                child_center[split_dim] = clip01(child_center[split_dim] + shift)
                child = make_rectangle(
                    center=(child_center[0], child_center[1], child_center[2]),
                    half_sizes=child_half_sizes,
                )
                next_rectangles.append(child)
                if total_evaluations >= config.max_evaluations:
                    break
            if total_evaluations >= config.max_evaluations:
                break

        rectangles = next_rectangles
        incumbent = min(rectangles, key=lambda r: (r.value, r.rect_id))
        incumbent_rect_id = incumbent.rect_id
        incumbent_fos = best_result.fos if best_result is not None else float("inf")
        best_history.append(incumbent_fos)
        incumbent_size = incumbent.size_metric

        diagnostics.append(
            DirectIterationDiagnostics(
                iteration=iteration,
                total_evaluations=total_evaluations,
                potentially_optimal_count=len(selected),
                incumbent_fos=incumbent_fos,
                min_rectangle_half_size=incumbent_size,
            )
        )

        if total_evaluations >= config.max_evaluations:
            termination_reason = "max_evaluations"
            break

        if incumbent_size <= config.min_rectangle_half_size:
            termination_reason = "min_rectangle_half_size_reached"
            break

        if len(best_history) > config.stall_iterations:
            previous = best_history[-config.stall_iterations - 1]
            current = best_history[-1]
            if math.isfinite(previous) and math.isfinite(current):
                if (previous - current) < config.min_improvement:
                    termination_reason = "stall_tolerance_reached"
                    break

    if best_surface is None or best_result is None:
        raise ConvergenceError("DIRECT search did not produce any valid surfaces.")

    # Deterministic post-polish to match established circular-search behavior
    # near toe/crest basins after global exploration.
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

    return DirectGlobalSearchResult(
        winning_surface=best_surface,
        winning_result=best_result,
        iteration_diagnostics=diagnostics,
        total_evaluations=total_evaluations,
        valid_evaluations=valid_evaluations,
        infeasible_evaluations=infeasible_evaluations,
        termination_reason=termination_reason,
    )
