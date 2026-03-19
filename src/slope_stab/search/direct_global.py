from __future__ import annotations

from dataclasses import dataclass
import math

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, DirectGlobalSearchInput, PrescribedCircleInput
from slope_stab.search.auto_refine import _run_toe_crest_refinement, _run_toe_locked_beta_refinement
from slope_stab.search.common import SurfaceBatchEvaluator, SurfaceEvaluator, X_SEP_MIN, repair_vector_clip
from slope_stab.search.direct_partition import (
    DirectRectangle,
    seeded_centers_3x3x3,
    select_potentially_optimal,
    split_rectangle,
)
from slope_stab.search.objective_evaluator import (
    CachedObjectiveEvaluator,
    ObjectiveEvaluation,
    ObjectiveScoringPolicy,
)
from slope_stab.search.post_polish import default_post_polish_refine_config


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


def run_direct_global_search(
    profile: UniformSlopeProfile,
    config: DirectGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None = None,
    min_batch_size: int = 1,
) -> DirectGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= X_SEP_MIN:
        raise GeometryError("DIRECT search limits must satisfy x_max - x_min > 0.05 m.")

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
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
    )

    next_rect_id = 0

    def make_rectangle(
        center: tuple[float, float, float],
        half_sizes: tuple[float, float, float],
        evaluation: ObjectiveEvaluation,
    ) -> DirectRectangle[ObjectiveEvaluation]:
        nonlocal next_rect_id
        rect = DirectRectangle(
            rect_id=next_rect_id,
            center=center,
            half_sizes=half_sizes,
            score=evaluation.score,
            payload=evaluation,
        )
        next_rect_id += 1
        return rect

    # Deterministic broad initialization: trisect each parameter once to seed
    # 3x3x3 boxes and avoid early lock-in to a single local basin.
    centers_1d = seeded_centers_3x3x3()
    base_half_sizes = (1.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0)
    centers: list[tuple[float, float, float]] = []
    for u0 in centers_1d:
        for u1 in centers_1d:
            for u2 in centers_1d:
                centers.append((u0, u1, u2))
    initial_evals = evaluator.evaluate_vectors_batch(centers)
    rectangles: list[DirectRectangle[ObjectiveEvaluation]] = []
    for center, evaluation in zip(centers, initial_evals):
        rectangles.append(make_rectangle(center, base_half_sizes, evaluation))

    if not rectangles:
        raise ConvergenceError("DIRECT search initialization failed.")
    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("DIRECT search did not produce any valid surfaces from the initial rectangle.")

    incumbent_rect_id = min(rectangles, key=lambda r: (r.score, r.rect_id)).rect_id
    diagnostics: list[DirectIterationDiagnostics] = []
    best_history: list[float] = []
    termination_reason = "max_iterations"

    for iteration in range(1, config.max_iterations + 1):
        if evaluator.total_evaluations >= config.max_evaluations:
            termination_reason = "max_evaluations"
            break

        selected = select_potentially_optimal(rectangles, incumbent_id=incumbent_rect_id)
        selected_ids = {rect.rect_id for rect in selected}

        next_rectangles: list[DirectRectangle[ObjectiveEvaluation]] = [
            rect for rect in rectangles if rect.rect_id not in selected_ids
        ]
        child_specs: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
        for rect in selected:
            for child_center, child_half_sizes in split_rectangle(rect):
                child_specs.append((child_center, child_half_sizes))

        child_evals = evaluator.evaluate_vectors_batch([center for center, _ in child_specs])
        for (center, half_sizes), evaluation in zip(child_specs, child_evals):
            child = make_rectangle(center=center, half_sizes=half_sizes, evaluation=evaluation)
            next_rectangles.append(child)

        rectangles = next_rectangles
        incumbent = min(rectangles, key=lambda r: (r.score, r.rect_id))
        incumbent_rect_id = incumbent.rect_id
        incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
        best_history.append(incumbent_fos)
        incumbent_size = incumbent.size_metric

        diagnostics.append(
            DirectIterationDiagnostics(
                iteration=iteration,
                total_evaluations=evaluator.total_evaluations,
                potentially_optimal_count=len(selected),
                incumbent_fos=incumbent_fos,
                min_rectangle_half_size=incumbent_size,
            )
        )

        if evaluator.total_evaluations >= config.max_evaluations:
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

    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("DIRECT search did not produce any valid surfaces.")

    # Deterministic post-polish to match established circular-search behavior
    # near toe/crest basins after global exploration.
    refine_config = default_post_polish_refine_config(config.search_limits)
    best_surface, best_result = _run_toe_crest_refinement(
        profile=profile,
        config=refine_config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=evaluator.best_surface,
        best_result=evaluator.best_result,
    )
    best_surface, best_result = _run_toe_locked_beta_refinement(
        profile=profile,
        config=refine_config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
    )

    return DirectGlobalSearchResult(
        winning_surface=best_surface,
        winning_result=best_result,
        iteration_diagnostics=diagnostics,
        total_evaluations=evaluator.total_evaluations,
        valid_evaluations=evaluator.valid_evaluations,
        infeasible_evaluations=evaluator.infeasible_evaluations,
        termination_reason=termination_reason,
    )
