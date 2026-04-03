from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, AutoRefineSearchInput, PrescribedCircleInput
from slope_stab.search.common import (
    PhaseEvaluationCounts,
    SurfaceBatchEvaluator,
    TIE_TOL,
    circle_from_endpoints_and_tangent,
    evaluate_surface_candidates_batch,
    surface_key,
)


TANGENT_EPS_RAD = math.radians(0.5)
_LOCAL_TOE_LOCKED_POLISH_MIN_IMPROVEMENT = 0.0
_DEFAULT_POST_POLISH_RIGHT_WINDOW_H_FRACTION = 0.2
_AUTO_REFINE_POST_POLISH_RIGHT_WINDOW_H_FRACTION = 0.38


@dataclass(frozen=True)
class AutoRefineIterationDiagnostics:
    iteration: int
    active_x_min: float
    active_x_max: float
    generated_surfaces: int
    valid_surfaces: int
    invalid_surfaces: int
    minimum_fos: float | None
    retained_division_indices: list[int]


@dataclass(frozen=True)
class AutoRefineSearchResult:
    winning_surface: PrescribedCircleInput
    winning_result: AnalysisResult
    before_post_polish_surface: PrescribedCircleInput
    before_post_polish_result: AnalysisResult
    after_post_polish_surface: PrescribedCircleInput
    after_post_polish_result: AnalysisResult
    iteration_diagnostics: list[AutoRefineIterationDiagnostics]
    generated_surfaces: int
    valid_surfaces: int
    invalid_surfaces: int
    post_refinement_generated_surfaces: int
    post_refinement_valid_surfaces: int
    post_refinement_invalid_surfaces: int


SurfaceEvaluator = Callable[[PrescribedCircleInput], AnalysisResult]


def _build_ground_polyline(profile: UniformSlopeProfile, x_min: float, x_max: float) -> list[tuple[float, float]]:
    if x_max <= x_min:
        raise GeometryError("Search limits must satisfy x_max > x_min.")

    x_points = [x_min, x_max]
    for breakpoint_x in (profile.x_toe, profile.crest_x):
        if x_min < breakpoint_x < x_max:
            x_points.append(breakpoint_x)

    x_points = sorted(set(x_points))
    return [(x, profile.y_ground(x)) for x in x_points]


def _cumulative_lengths(polyline: list[tuple[float, float]]) -> tuple[list[float], float]:
    cumulative = [0.0]
    total = 0.0
    for (x1, y1), (x2, y2) in zip(polyline[:-1], polyline[1:]):
        segment_length = math.hypot(x2 - x1, y2 - y1)
        total += segment_length
        cumulative.append(total)
    return cumulative, total


def _point_at_arc_length(polyline: list[tuple[float, float]], cumulative: list[float], s: float) -> tuple[float, float]:
    if s <= 0.0:
        return polyline[0]
    if s >= cumulative[-1]:
        return polyline[-1]

    for idx in range(1, len(cumulative)):
        if s <= cumulative[idx]:
            s0 = cumulative[idx - 1]
            s1 = cumulative[idx]
            if s1 <= s0:
                return polyline[idx]
            ratio = (s - s0) / (s1 - s0)
            x0, y0 = polyline[idx - 1]
            x1, y1 = polyline[idx]
            return (x0 + ratio * (x1 - x0), y0 + ratio * (y1 - y0))

    return polyline[-1]


def _division_boundaries_and_midpoints(
    polyline: list[tuple[float, float]], divisions: int
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    cumulative, total = _cumulative_lengths(polyline)
    if total <= 0.0:
        raise GeometryError("Search polyline length must be greater than zero.")

    boundaries: list[tuple[float, float]] = []
    midpoints: list[tuple[float, float]] = []

    for i in range(divisions + 1):
        target = (i / divisions) * total
        boundaries.append(_point_at_arc_length(polyline, cumulative, target))

    for i in range(divisions):
        target = ((i + 0.5) / divisions) * total
        midpoints.append(_point_at_arc_length(polyline, cumulative, target))

    return boundaries, midpoints


def _generate_slide2_betas(theta_chord: float, count: int) -> list[float]:
    if count <= 0:
        return []
    beta_max = 0.5 * math.pi - theta_chord
    if beta_max <= 0.0:
        return []
    return [(m / count) * beta_max for m in range(1, count + 1)]


def _generate_pre_polish_pair_candidates(
    p_left: tuple[float, float],
    p_right: tuple[float, float],
    circles_per_division: int,
) -> list[PrescribedCircleInput | None]:
    if p_right[0] <= p_left[0]:
        return []
    theta_chord = math.atan2(
        p_right[1] - p_left[1],
        p_right[0] - p_left[0],
    )
    betas = _generate_slide2_betas(theta_chord, circles_per_division)
    return [circle_from_endpoints_and_tangent(p_left, p_right, beta) for beta in betas]


def run_auto_refine_search(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None = None,
    min_batch_size: int = 1,
) -> AutoRefineSearchResult:
    current_x_min = config.search_limits.x_min
    current_x_max = config.search_limits.x_max

    diagnostics: list[AutoRefineIterationDiagnostics] = []
    best_surface: PrescribedCircleInput | None = None
    best_result: AnalysisResult | None = None

    total_generated = 0
    total_valid = 0
    post_refinement_counts = PhaseEvaluationCounts()

    for iteration in range(1, config.iterations + 1):
        polyline = _build_ground_polyline(profile, current_x_min, current_x_max)
        boundaries, midpoints = _division_boundaries_and_midpoints(polyline, config.divisions_along_slope)

        division_fos: list[list[float]] = [[] for _ in range(config.divisions_along_slope)]
        generated = 0
        valid = 0
        iter_min_fos: float | None = None

        for i in range(config.divisions_along_slope):
            for j in range(i + 1, config.divisions_along_slope):
                p_left_mid = midpoints[i]
                p_right_mid = midpoints[j]
                candidate_surfaces = _generate_pre_polish_pair_candidates(
                    p_left=p_left_mid,
                    p_right=p_right_mid,
                    circles_per_division=config.circles_per_division,
                )

                generated += len(candidate_surfaces)
                use_batch = batch_evaluate_surfaces is not None and len(candidate_surfaces) >= max(1, min_batch_size)
                evaluations = evaluate_surface_candidates_batch(
                    surfaces=candidate_surfaces,
                    evaluate_surface=evaluate_surface,
                    driving_moment_tol=1e-6,
                    batch_evaluate_surfaces=batch_evaluate_surfaces if use_batch else None,
                )
                for evaluation in evaluations:
                    if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
                        continue
                    result = evaluation.result

                    valid += 1
                    division_fos[i].append(result.fos)
                    division_fos[j].append(result.fos)

                    if iter_min_fos is None or result.fos < iter_min_fos - TIE_TOL:
                        iter_min_fos = result.fos

                    if best_result is None or result.fos < best_result.fos - TIE_TOL:
                        best_surface = evaluation.surface
                        best_result = result
                    elif best_result is not None and abs(result.fos - best_result.fos) <= TIE_TOL:
                        # Deterministic tie-break using left, right, then radius.
                        assert best_surface is not None
                        candidate_key = surface_key(evaluation.surface)
                        best_key = surface_key(best_surface)
                        if candidate_key < best_key:
                            best_surface = evaluation.surface
                            best_result = result

        total_generated += generated
        total_valid += valid

        averages: list[float] = []
        for fos_values in division_fos:
            if fos_values:
                averages.append(sum(fos_values) / len(fos_values))
            else:
                averages.append(float("inf"))

        keep_count = max(
            1,
            math.ceil(config.divisions_along_slope * config.divisions_to_use_next_iteration_pct / 100.0),
        )
        ranked_indices = sorted(range(config.divisions_along_slope), key=lambda idx: (averages[idx], idx))
        retained_indices = sorted(ranked_indices[:keep_count])

        next_x_min = min(boundaries[idx][0] for idx in retained_indices)
        next_x_max = max(boundaries[idx + 1][0] for idx in retained_indices)
        if next_x_max <= next_x_min + 1e-9:
            next_x_min = current_x_min
            next_x_max = current_x_max

        diagnostics.append(
            AutoRefineIterationDiagnostics(
                iteration=iteration,
                active_x_min=current_x_min,
                active_x_max=current_x_max,
                generated_surfaces=generated,
                valid_surfaces=valid,
                invalid_surfaces=generated - valid,
                minimum_fos=iter_min_fos,
                retained_division_indices=retained_indices,
            )
        )

        current_x_min = next_x_min
        current_x_max = next_x_max

    if best_result is None or best_surface is None:
        raise ConvergenceError("Auto-refine search did not produce any valid surfaces.")

    # Snapshot winner at the end of the core iterative search, before any
    # post-polish refinement passes are applied.
    before_post_polish_surface = best_surface
    before_post_polish_result = best_result

    best_surface, best_result = _run_toe_crest_refinement(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
        post_refinement_counts=post_refinement_counts,
        right_window_h_fraction=_AUTO_REFINE_POST_POLISH_RIGHT_WINDOW_H_FRACTION,
    )
    best_surface, best_result = _run_toe_locked_beta_refinement(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
        post_refinement_counts=post_refinement_counts,
    )
    best_surface, best_result = _run_toe_locked_local_xright_beta_polish(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
        post_refinement_counts=post_refinement_counts,
    )

    return AutoRefineSearchResult(
        winning_surface=best_surface,
        winning_result=best_result,
        before_post_polish_surface=before_post_polish_surface,
        before_post_polish_result=before_post_polish_result,
        after_post_polish_surface=best_surface,
        after_post_polish_result=best_result,
        iteration_diagnostics=diagnostics,
        generated_surfaces=total_generated,
        valid_surfaces=total_valid,
        invalid_surfaces=total_generated - total_valid,
        post_refinement_generated_surfaces=post_refinement_counts.total,
        post_refinement_valid_surfaces=post_refinement_counts.valid,
        post_refinement_invalid_surfaces=post_refinement_counts.infeasible,
    )


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if count <= 1:
        return [0.5 * (start + stop)]
    return [start + (stop - start) * (i / (count - 1)) for i in range(count)]


def _run_toe_crest_refinement(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
    post_refinement_counts: PhaseEvaluationCounts | None = None,
    right_window_h_fraction: float = _DEFAULT_POST_POLISH_RIGHT_WINDOW_H_FRACTION,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    left_min = max(config.search_limits.x_min, profile.x_toe)
    left_max = min(config.search_limits.x_max, profile.x_toe + 0.2 * profile.h)
    right_min = max(config.search_limits.x_min, profile.crest_x)
    right_max = min(
        config.search_limits.x_max,
        profile.crest_x + right_window_h_fraction * profile.h,
    )

    if left_max <= left_min or right_max <= right_min:
        return best_surface, best_result

    left_samples = _linspace(left_min, left_max, 21)
    right_samples = _linspace(right_min, right_max, 21)
    beta_samples = max(11, config.circles_per_division + 1)
    theta_hi = 0.5 * math.pi - TANGENT_EPS_RAD

    for x_left in left_samples:
        y_left = profile.y_ground(x_left)
        for x_right in right_samples:
            if x_right <= x_left:
                continue
            y_right = profile.y_ground(x_right)
            theta_lo = math.atan2(y_right - y_left, x_right - x_left) + TANGENT_EPS_RAD
            if theta_lo >= theta_hi:
                continue

            candidates: list[PrescribedCircleInput | None] = []
            for k in range(beta_samples):
                u = k / (beta_samples - 1)
                beta = theta_lo + (theta_hi - theta_lo) * (u * u)
                candidates.append(circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta))

            use_batch = batch_evaluate_surfaces is not None and len(candidates) >= max(1, min_batch_size)
            evaluations = evaluate_surface_candidates_batch(
                surfaces=candidates,
                evaluate_surface=evaluate_surface,
                driving_moment_tol=1e-6,
                batch_evaluate_surfaces=batch_evaluate_surfaces if use_batch else None,
            )
            if post_refinement_counts is not None:
                post_refinement_counts.record_batch(evaluations)
            for evaluation in evaluations:
                if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
                    continue
                result = evaluation.result

                if result.fos < best_result.fos - TIE_TOL:
                    best_surface = evaluation.surface
                    best_result = result
                elif abs(result.fos - best_result.fos) <= TIE_TOL:
                    candidate_key = surface_key(evaluation.surface)
                    best_key = surface_key(best_surface)
                    if candidate_key < best_key:
                        best_surface = evaluation.surface
                        best_result = result

    return best_surface, best_result


def _run_toe_locked_beta_refinement(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
    post_refinement_counts: PhaseEvaluationCounts | None = None,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    # Preserve the current right endpoint and re-sweep beta with toe-anchored entry.
    if not (config.search_limits.x_min <= profile.x_toe <= config.search_limits.x_max):
        return best_surface, best_result

    return _run_toe_locked_refinement_for_xright_values(
        profile=profile,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
        x_right_values=[best_surface.x_right],
        post_refinement_counts=post_refinement_counts,
    )


def _run_toe_locked_local_xright_beta_polish(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
    post_refinement_counts: PhaseEvaluationCounts | None = None,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    # Deterministic local sweep around incumbent toe-anchored right endpoint.
    if not (config.search_limits.x_min <= profile.x_toe <= config.search_limits.x_max):
        return best_surface, best_result

    right_min = max(config.search_limits.x_min, profile.crest_x)
    right_max = min(
        config.search_limits.x_max,
        profile.crest_x + _AUTO_REFINE_POST_POLISH_RIGHT_WINDOW_H_FRACTION * profile.h,
    )
    if right_max <= right_min:
        return best_surface, best_result

    coarse_step = (right_max - right_min) / 20.0
    if coarse_step <= 0.0:
        return best_surface, best_result

    x_right_center = min(max(best_surface.x_right, right_min), right_max)
    half_window = 6.0 * coarse_step
    local_step = 0.25 * coarse_step
    local_min = max(right_min, x_right_center - half_window)
    local_max = min(right_max, x_right_center + half_window)
    if local_max <= local_min:
        x_right_values = [local_min]
    else:
        x_right_values = sorted(
            {
                min(max(x_right_center + offset * local_step, local_min), local_max)
                for offset in range(-24, 25)
            }
        )

    polished_surface, polished_result = _run_toe_locked_refinement_for_xright_values(
        profile=profile,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
        best_surface=best_surface,
        best_result=best_result,
        x_right_values=x_right_values,
        post_refinement_counts=post_refinement_counts,
    )
    # Accept only meaningful improvements to avoid platform-dependent drift in
    # near-flat objective regions while preserving deterministic tie-break rules.
    if polished_result.fos < best_result.fos - _LOCAL_TOE_LOCKED_POLISH_MIN_IMPROVEMENT:
        return polished_surface, polished_result
    return best_surface, best_result


def _run_toe_locked_refinement_for_xright_values(
    profile: UniformSlopeProfile,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
    x_right_values: list[float],
    post_refinement_counts: PhaseEvaluationCounts | None = None,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    x_left = profile.x_toe
    y_left = profile.y_ground(x_left)
    beta_samples = 121
    theta_lo = TANGENT_EPS_RAD
    theta_hi = 0.5 * math.pi - TANGENT_EPS_RAD

    for x_right in x_right_values:
        if x_right <= x_left:
            continue
        y_right = profile.y_ground(x_right)
        candidates: list[PrescribedCircleInput | None] = []
        for k in range(beta_samples):
            u = k / (beta_samples - 1)
            beta = theta_lo + (theta_hi - theta_lo) * u
            candidates.append(circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta))

        use_batch = batch_evaluate_surfaces is not None and len(candidates) >= max(1, min_batch_size)
        evaluations = evaluate_surface_candidates_batch(
            surfaces=candidates,
            evaluate_surface=evaluate_surface,
            driving_moment_tol=1e-6,
            batch_evaluate_surfaces=batch_evaluate_surfaces if use_batch else None,
        )
        if post_refinement_counts is not None:
            post_refinement_counts.record_batch(evaluations)
        for evaluation in evaluations:
            if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
                continue
            result = evaluation.result

            if result.fos < best_result.fos - TIE_TOL:
                best_surface = evaluation.surface
                best_result = result
            elif abs(result.fos - best_result.fos) <= TIE_TOL:
                candidate_key = surface_key(evaluation.surface)
                best_key = surface_key(best_surface)
                if candidate_key < best_key:
                    best_surface = evaluation.surface
                    best_result = result

    return best_surface, best_result
