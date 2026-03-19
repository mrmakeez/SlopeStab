from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, AutoRefineSearchInput, PrescribedCircleInput
from slope_stab.search.common import (
    SurfaceBatchEvaluator,
    TIE_TOL,
    circle_from_endpoints_and_tangent,
    evaluate_surface_candidates_batch,
    surface_key,
)


TANGENT_EPS_RAD = math.radians(0.5)
_DIVISION_EDGE_EPS = 1e-4


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
    iteration_diagnostics: list[AutoRefineIterationDiagnostics]
    generated_surfaces: int
    valid_surfaces: int
    invalid_surfaces: int


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


def _generate_tangent_angles(_theta_min: float, count: int) -> list[float]:
    lo = TANGENT_EPS_RAD
    hi = 0.5 * math.pi - TANGENT_EPS_RAD
    if lo >= hi:
        return []
    if count <= 1:
        return [0.5 * (lo + hi)]
    return [lo + (hi - lo) * ((i / (count - 1)) ** 2) for i in range(count)]


def _interpolate_point(a: tuple[float, float], b: tuple[float, float], fraction: float) -> tuple[float, float]:
    x = a[0] + fraction * (b[0] - a[0])
    y = a[1] + fraction * (b[1] - a[1])
    return (x, y)


def _van_der_corput(index: int, base: int) -> float:
    value = 0.0
    denominator = 1.0
    i = index
    while i > 0:
        i, remainder = divmod(i, base)
        denominator *= base
        value += remainder / denominator
    return value


def _sample_fractions(index: int, total: int) -> tuple[float, float]:
    if total <= 1:
        return (0.5, 0.5)
    left = _van_der_corput(index + 1, 2)
    right = _van_der_corput(index + 1, 3)
    return (left, right)


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
                left_start = boundaries[i]
                left_end = boundaries[i + 1]
                right_start = boundaries[j]
                right_end = boundaries[j + 1]

                theta_min = math.atan2(
                    p_right_mid[1] - p_left_mid[1],
                    p_right_mid[0] - p_left_mid[0],
                )
                angles = _generate_tangent_angles(theta_min, config.circles_per_division)
                candidate_surfaces: list[PrescribedCircleInput | None] = []
                for angle_index, theta in enumerate(angles):
                    frac_left, frac_right = _sample_fractions(angle_index, len(angles))
                    frac_left = min(max(frac_left, _DIVISION_EDGE_EPS), 1.0 - _DIVISION_EDGE_EPS)
                    frac_right = min(max(frac_right, _DIVISION_EDGE_EPS), 1.0 - _DIVISION_EDGE_EPS)
                    p_left = _interpolate_point(left_start, left_end, frac_left)
                    p_right = _interpolate_point(right_start, right_end, frac_right)
                    candidate_surfaces.append(circle_from_endpoints_and_tangent(p_left, p_right, theta))

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

    if best_result is not None and best_surface is not None:
        best_surface, best_result = _run_toe_crest_refinement(
            profile=profile,
            config=config,
            evaluate_surface=evaluate_surface,
            batch_evaluate_surfaces=batch_evaluate_surfaces,
            min_batch_size=min_batch_size,
            best_surface=best_surface,
            best_result=best_result,
        )
        best_surface, best_result = _run_toe_locked_beta_refinement(
            profile=profile,
            config=config,
            evaluate_surface=evaluate_surface,
            batch_evaluate_surfaces=batch_evaluate_surfaces,
            min_batch_size=min_batch_size,
            best_surface=best_surface,
            best_result=best_result,
        )

    if best_result is None or best_surface is None:
        raise ConvergenceError("Auto-refine search did not produce any valid surfaces.")

    return AutoRefineSearchResult(
        winning_surface=best_surface,
        winning_result=best_result,
        iteration_diagnostics=diagnostics,
        generated_surfaces=total_generated,
        valid_surfaces=total_valid,
        invalid_surfaces=total_generated - total_valid,
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
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    left_min = max(config.search_limits.x_min, profile.x_toe)
    left_max = min(config.search_limits.x_max, profile.x_toe + 0.2 * profile.h)
    right_min = max(config.search_limits.x_min, profile.crest_x)
    right_max = min(config.search_limits.x_max, profile.crest_x + 0.2 * profile.h)

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
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    # Preserve the current right endpoint and re-sweep beta with toe-anchored entry.
    if not (config.search_limits.x_min <= profile.x_toe <= config.search_limits.x_max):
        return best_surface, best_result

    x_left = profile.x_toe
    x_right = best_surface.x_right
    if x_right <= x_left:
        return best_surface, best_result

    y_left = profile.y_ground(x_left)
    y_right = profile.y_ground(x_right)
    beta_samples = 61
    theta_lo = TANGENT_EPS_RAD
    theta_hi = 0.5 * math.pi - TANGENT_EPS_RAD

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
