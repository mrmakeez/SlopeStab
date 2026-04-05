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
_RETAINED_PATH_TOL = 1e-9
_GROUND_INTERSECTION_TOL = 1e-7
_GROUND_DIFF_TOL = 1.5e-6
_GROUND_BREAKPOINT_SNAP_TOL = 4e-4
_ENTRY_EXIT_ELEV_TOL = 1e-6
_MODEL_BOUNDARY_TOL = 1e-6
_REVERSE_CURVATURE_TOL = 1e-6


@dataclass(frozen=True)
class RetainedPathSegment:
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class AutoRefineIterationDiagnostics:
    iteration: int
    active_x_min: float
    active_x_max: float
    active_path_segments: list[RetainedPathSegment]
    generated_surfaces: int
    valid_surfaces: int
    invalid_surfaces: int
    minimum_fos: float | None
    minimum_surface: PrescribedCircleInput | None
    retained_division_indices: list[int]
    expanded_retained_division_indices: list[int]
    next_active_path_segments: list[RetainedPathSegment]


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


def _segment_length(segment: RetainedPathSegment) -> float:
    return math.hypot(
        segment.end[0] - segment.start[0],
        segment.end[1] - segment.start[1],
    )


def _polyline_to_retained_path(polyline: list[tuple[float, float]]) -> list[RetainedPathSegment]:
    retained_path: list[RetainedPathSegment] = []
    for start, end in zip(polyline[:-1], polyline[1:]):
        segment = RetainedPathSegment(start=start, end=end)
        if _segment_length(segment) <= _RETAINED_PATH_TOL:
            continue
        retained_path.append(segment)
    return retained_path


def _build_retained_path(profile: UniformSlopeProfile, x_min: float, x_max: float) -> list[RetainedPathSegment]:
    return _polyline_to_retained_path(_build_ground_polyline(profile, x_min, x_max))


def _retained_path_total_length(retained_path: list[RetainedPathSegment]) -> float:
    return sum(_segment_length(segment) for segment in retained_path)


def _retained_path_bounds(retained_path: list[RetainedPathSegment]) -> tuple[float, float]:
    if not retained_path:
        raise GeometryError("Retained path must contain at least one segment.")
    x_values = [segment.start[0] for segment in retained_path]
    x_values.extend(segment.end[0] for segment in retained_path)
    return (min(x_values), max(x_values))


def _point_on_segment(segment: RetainedPathSegment, distance: float) -> tuple[float, float]:
    length = _segment_length(segment)
    if length <= _RETAINED_PATH_TOL:
        return segment.end
    if distance <= 0.0:
        return segment.start
    if distance >= length:
        return segment.end
    ratio = distance / length
    return (
        segment.start[0] + ratio * (segment.end[0] - segment.start[0]),
        segment.start[1] + ratio * (segment.end[1] - segment.start[1]),
    )


def _segments_are_mergeable(
    first: RetainedPathSegment,
    second: RetainedPathSegment,
    tol: float = _RETAINED_PATH_TOL,
) -> bool:
    if math.hypot(first.end[0] - second.start[0], first.end[1] - second.start[1]) > tol:
        return False

    dx1 = first.end[0] - first.start[0]
    dy1 = first.end[1] - first.start[1]
    dx2 = second.end[0] - second.start[0]
    dy2 = second.end[1] - second.start[1]
    len1 = math.hypot(dx1, dy1)
    len2 = math.hypot(dx2, dy2)
    if len1 <= tol or len2 <= tol:
        return True

    cross = dx1 * dy2 - dy1 * dx2
    dot = dx1 * dx2 + dy1 * dy2
    return abs(cross) <= tol * max(1.0, len1 * len2) and dot >= -tol


def _merge_adjacent_retained_segments(
    retained_path: list[RetainedPathSegment],
    tol: float = _RETAINED_PATH_TOL,
) -> list[RetainedPathSegment]:
    merged: list[RetainedPathSegment] = []
    for segment in retained_path:
        if _segment_length(segment) <= tol:
            continue
        if merged and _segments_are_mergeable(merged[-1], segment, tol=tol):
            merged[-1] = RetainedPathSegment(start=merged[-1].start, end=segment.end)
            continue
        merged.append(segment)
    return merged


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
    retained_path = _polyline_to_retained_path(polyline)
    return _division_boundaries_and_midpoints_for_retained_path(retained_path, divisions)


def _point_at_retained_arc_length(
    retained_path: list[RetainedPathSegment],
    s: float,
) -> tuple[float, float]:
    if not retained_path:
        raise GeometryError("Retained path must contain at least one segment.")

    total = _retained_path_total_length(retained_path)
    if total <= 0.0:
        raise GeometryError("Search polyline length must be greater than zero.")
    if s <= 0.0:
        return retained_path[0].start
    if s >= total:
        return retained_path[-1].end

    traversed = 0.0
    for segment in retained_path:
        length = _segment_length(segment)
        if s <= traversed + length:
            return _point_on_segment(segment, s - traversed)
        traversed += length
    return retained_path[-1].end


def _division_boundaries_and_midpoints_for_retained_path(
    retained_path: list[RetainedPathSegment],
    divisions: int,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    total = _retained_path_total_length(retained_path)
    if total <= 0.0:
        raise GeometryError("Search polyline length must be greater than zero.")

    boundaries: list[tuple[float, float]] = []
    midpoints: list[tuple[float, float]] = []

    for i in range(divisions + 1):
        target = (i / divisions) * total
        boundaries.append(_point_at_retained_arc_length(retained_path, target))

    for i in range(divisions):
        target = ((i + 0.5) / divisions) * total
        midpoints.append(_point_at_retained_arc_length(retained_path, target))

    return boundaries, midpoints


def _extract_retained_interval(
    retained_path: list[RetainedPathSegment],
    start_s: float,
    end_s: float,
) -> list[RetainedPathSegment]:
    if end_s <= start_s + _RETAINED_PATH_TOL:
        return []

    extracted: list[RetainedPathSegment] = []
    traversed = 0.0
    for segment in retained_path:
        length = _segment_length(segment)
        seg_start = traversed
        seg_end = traversed + length
        traversed = seg_end

        overlap_start = max(start_s, seg_start)
        overlap_end = min(end_s, seg_end)
        if overlap_end <= overlap_start + _RETAINED_PATH_TOL:
            continue

        extracted.append(
            RetainedPathSegment(
                start=_point_on_segment(segment, overlap_start - seg_start),
                end=_point_on_segment(segment, overlap_end - seg_start),
            )
        )

    return _merge_adjacent_retained_segments(extracted)


def _build_next_retained_path(
    retained_path: list[RetainedPathSegment],
    divisions: int,
    retained_indices: list[int],
) -> list[RetainedPathSegment]:
    total = _retained_path_total_length(retained_path)
    if total <= 0.0:
        raise GeometryError("Search polyline length must be greater than zero.")

    next_path: list[RetainedPathSegment] = []
    for idx in retained_indices:
        start_s = (idx / divisions) * total
        end_s = ((idx + 1) / divisions) * total
        next_path.extend(_extract_retained_interval(retained_path, start_s, end_s))

    return _merge_adjacent_retained_segments(next_path)


def _close_small_retained_index_gaps(retained_indices: list[int], max_gap: int = 1) -> list[int]:
    if not retained_indices:
        return []

    expanded = [retained_indices[0]]
    for idx in retained_indices[1:]:
        gap = idx - expanded[-1] - 1
        if 0 < gap <= max_gap:
            expanded.extend(range(expanded[-1] + 1, idx))
        expanded.append(idx)
    return expanded


def _pad_retained_index_runs(
    retained_indices: list[int],
    divisions: int,
    edge_padding: int = 1,
) -> list[int]:
    if not retained_indices:
        return []

    padded: list[int] = []
    run_start = retained_indices[0]
    run_end = retained_indices[0]
    for idx in retained_indices[1:]:
        if idx == run_end + 1:
            run_end = idx
            continue
        padded.extend(
            range(
                max(0, run_start - edge_padding),
                min(divisions - 1, run_end + edge_padding) + 1,
            )
        )
        run_start = idx
        run_end = idx

    padded.extend(
        range(
            max(0, run_start - edge_padding),
            min(divisions - 1, run_end + edge_padding) + 1,
        )
    )
    return sorted(set(padded))


def _generate_slide2_betas(theta_chord: float, count: int) -> list[float]:
    if count <= 0:
        return []
    beta_max = 0.5 * math.pi - theta_chord
    if beta_max <= 0.0:
        return []
    return [(m / count) * beta_max for m in range(1, count + 1)]


def _circle_lower_y(surface: PrescribedCircleInput, x: float) -> float:
    inside = surface.r * surface.r - (x - surface.xc) ** 2
    if inside < -1e-10:
        raise GeometryError(
            f"x={x} falls outside prescribed circle domain for xc={surface.xc}, r={surface.r}."
        )
    return surface.yc - math.sqrt(max(inside, 0.0))


def _surface_has_reverse_curvature(
    surface: PrescribedCircleInput,
    tol: float = _REVERSE_CURVATURE_TOL,
) -> bool:
    # Slide2 defines reverse curvature in terms of the slip arc rising above the circle center.
    # Auto-refine uses the lower circular branch, so this should stay false for valid candidates.
    max_y = max(surface.y_left, surface.y_right)
    sample_xs = (
        surface.x_left,
        0.5 * (surface.x_left + surface.x_right),
        surface.x_right,
    )
    domain_tol = max(1e-9, 2.0 * max(1.0, surface.r) * tol)
    for x in sample_xs:
        inside = surface.r * surface.r - (x - surface.xc) ** 2
        if inside < -domain_tol:
            continue
        max_y = max(max_y, surface.yc - math.sqrt(max(inside, 0.0)))
    return max_y > surface.yc + tol


def _dedupe_sorted_roots(roots: list[float], tol: float = _GROUND_INTERSECTION_TOL) -> list[float]:
    if not roots:
        return []
    ordered = sorted(roots)
    deduped = [ordered[0]]
    for x in ordered[1:]:
        if abs(x - deduped[-1]) > tol:
            deduped.append(x)
    return deduped


def _clip_root_to_segment(x: float, x_start: float, x_end: float, tol: float = _GROUND_INTERSECTION_TOL) -> float | None:
    if x < x_start - tol or x > x_end + tol:
        return None
    return min(max(x, x_start), x_end)


def _snap_x_to_ground_breakpoints(
    x: float,
    breakpoints: list[float],
    tol: float = _GROUND_BREAKPOINT_SNAP_TOL,
) -> float:
    for breakpoint_x in breakpoints:
        if abs(x - breakpoint_x) <= tol:
            return breakpoint_x
    return x


def _horizontal_ground_intersections(
    surface: PrescribedCircleInput,
    y_ground: float,
    x_start: float,
    x_end: float,
) -> list[float]:
    if x_end <= x_start:
        return []
    inside = surface.r * surface.r - (surface.yc - y_ground) ** 2
    if inside < -_GROUND_INTERSECTION_TOL:
        return []
    inside = max(inside, 0.0)
    dx = math.sqrt(inside)
    roots: list[float] = []
    for x in (surface.xc - dx, surface.xc + dx):
        clipped = _clip_root_to_segment(x, x_start, x_end)
        if clipped is None:
            continue
        if abs(_circle_lower_y(surface, clipped) - y_ground) <= _GROUND_DIFF_TOL:
            roots.append(clipped)
    return roots


def _linear_ground_intersections(
    surface: PrescribedCircleInput,
    slope: float,
    intercept: float,
    x_start: float,
    x_end: float,
) -> list[float]:
    if x_end <= x_start:
        return []

    a = 1.0 + slope * slope
    b = 2.0 * (slope * (intercept - surface.yc) - surface.xc)
    c = surface.xc * surface.xc + (intercept - surface.yc) ** 2 - surface.r * surface.r
    discriminant = b * b - 4.0 * a * c
    if discriminant < -_GROUND_INTERSECTION_TOL:
        return []
    discriminant = max(discriminant, 0.0)
    sqrt_discriminant = math.sqrt(discriminant)

    roots: list[float] = []
    for x in (
        (-b - sqrt_discriminant) / (2.0 * a),
        (-b + sqrt_discriminant) / (2.0 * a),
    ):
        clipped = _clip_root_to_segment(x, x_start, x_end)
        if clipped is None:
            continue
        y_ground = slope * clipped + intercept
        if abs(_circle_lower_y(surface, clipped) - y_ground) <= _GROUND_DIFF_TOL:
            roots.append(clipped)
    return roots


def _ground_intersections_for_circle(
    profile: UniformSlopeProfile,
    surface: PrescribedCircleInput,
    x_min: float,
    x_max: float,
) -> list[float]:
    if x_max <= x_min:
        return []

    roots: list[float] = []
    toe_end = min(x_max, profile.x_toe)
    if x_min < toe_end:
        roots.extend(_horizontal_ground_intersections(surface, profile.y_toe, x_min, toe_end))

    slope_start = max(x_min, profile.x_toe)
    slope_end = min(x_max, profile.crest_x)
    if slope_start < slope_end:
        roots.extend(
            _linear_ground_intersections(
                surface,
                slope=profile.slope_gradient,
                intercept=profile.y_toe - profile.slope_gradient * profile.x_toe,
                x_start=slope_start,
                x_end=slope_end,
            )
        )

    crest_start = max(x_min, profile.crest_x)
    if crest_start < x_max:
        roots.extend(_horizontal_ground_intersections(surface, profile.crest_y, crest_start, x_max))

    return _dedupe_sorted_roots(roots)


def _clip_construction_circle_to_ground_intercepts(
    profile: UniformSlopeProfile,
    construction_surface: PrescribedCircleInput,
    search_x_min: float,
    search_x_max: float,
    construction_mid_x: float,
    model_boundary_floor_y: float | None = None,
) -> PrescribedCircleInput | None:
    roots = _ground_intersections_for_circle(
        profile=profile,
        surface=construction_surface,
        x_min=search_x_min,
        x_max=search_x_max,
    )
    if len(roots) < 2:
        return None

    valid_intervals: list[tuple[float, float]] = []
    for x_left, x_right in zip(roots[:-1], roots[1:]):
        if x_right <= x_left + _GROUND_INTERSECTION_TOL:
            continue
        x_mid = 0.5 * (x_left + x_right)
        y_diff = profile.y_ground(x_mid) - _circle_lower_y(construction_surface, x_mid)
        if y_diff >= -_GROUND_DIFF_TOL:
            valid_intervals.append((x_left, x_right))

    if not valid_intervals:
        return None

    ordered_intervals = sorted(
        valid_intervals,
        key=lambda interval: (
            0
            if interval[0] - _GROUND_INTERSECTION_TOL <= construction_mid_x <= interval[1] + _GROUND_INTERSECTION_TOL
            else 1,
            -(interval[1] - interval[0]),
            interval[0],
            interval[1],
        ),
    )

    for x_left, x_right in ordered_intervals:
        if x_right <= x_left + 1e-9:
            continue

        snapped_x_left = _snap_x_to_ground_breakpoints(
            x_left,
            [
                search_x_min,
                profile.x_toe,
                profile.crest_x,
                search_x_max,
            ],
        )
        snapped_x_right = _snap_x_to_ground_breakpoints(
            x_right,
            [
                search_x_min,
                profile.x_toe,
                profile.crest_x,
                search_x_max,
            ],
        )
        if snapped_x_right <= snapped_x_left + 1e-9:
            continue

        candidate = PrescribedCircleInput(
            xc=construction_surface.xc,
            yc=construction_surface.yc,
            r=construction_surface.r,
            x_left=snapped_x_left,
            y_left=profile.y_ground(snapped_x_left),
            x_right=snapped_x_right,
            y_right=profile.y_ground(snapped_x_right),
        )
        if abs(candidate.y_left - candidate.y_right) <= _ENTRY_EXIT_ELEV_TOL:
            continue
        if _surface_has_reverse_curvature(candidate):
            continue
        if model_boundary_floor_y is not None:
            x_min_y = min(max(candidate.xc, candidate.x_left), candidate.x_right)
            if _circle_lower_y(candidate, x_min_y) < model_boundary_floor_y - _MODEL_BOUNDARY_TOL:
                continue
        return candidate

    return None


def _generate_pre_polish_pair_candidates(
    profile: UniformSlopeProfile,
    search_x_min: float,
    search_x_max: float,
    p_left: tuple[float, float],
    p_right: tuple[float, float],
    circles_per_division: int,
    model_boundary_floor_y: float | None = None,
) -> list[PrescribedCircleInput | None]:
    if p_right[0] <= p_left[0]:
        return []
    theta_chord = math.atan2(
        p_right[1] - p_left[1],
        p_right[0] - p_left[0],
    )
    betas = _generate_slide2_betas(theta_chord, circles_per_division)
    construction_mid_x = 0.5 * (p_left[0] + p_right[0])
    candidates: list[PrescribedCircleInput | None] = []
    for beta in betas:
        construction_surface = circle_from_endpoints_and_tangent(p_left, p_right, beta)
        if construction_surface is None:
            candidates.append(None)
            continue
        candidates.append(
            _clip_construction_circle_to_ground_intercepts(
                profile=profile,
                construction_surface=construction_surface,
                search_x_min=search_x_min,
                search_x_max=search_x_max,
                construction_mid_x=construction_mid_x,
                model_boundary_floor_y=model_boundary_floor_y,
            )
        )
    return candidates


def run_auto_refine_search(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None = None,
    min_batch_size: int = 1,
) -> AutoRefineSearchResult:
    active_retained_path = _build_retained_path(
        profile,
        config.search_limits.x_min,
        config.search_limits.x_max,
    )

    diagnostics: list[AutoRefineIterationDiagnostics] = []
    best_surface: PrescribedCircleInput | None = None
    best_result: AnalysisResult | None = None

    total_generated = 0
    total_valid = 0
    post_refinement_counts = PhaseEvaluationCounts()

    for iteration in range(1, config.iterations + 1):
        current_x_min, current_x_max = _retained_path_bounds(active_retained_path)
        _, midpoints = _division_boundaries_and_midpoints_for_retained_path(
            active_retained_path,
            config.divisions_along_slope,
        )

        division_fos: list[list[float]] = [[] for _ in range(config.divisions_along_slope)]
        generated = 0
        valid = 0
        iter_min_fos: float | None = None
        iter_min_surface: PrescribedCircleInput | None = None

        for i in range(config.divisions_along_slope):
            for j in range(i + 1, config.divisions_along_slope):
                p_left_mid = midpoints[i]
                p_right_mid = midpoints[j]
                candidate_surfaces = _generate_pre_polish_pair_candidates(
                    profile=profile,
                    search_x_min=config.search_limits.x_min,
                    search_x_max=config.search_limits.x_max,
                    p_left=p_left_mid,
                    p_right=p_right_mid,
                    circles_per_division=config.circles_per_division,
                    model_boundary_floor_y=config.model_boundary_floor_y,
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
                        iter_min_surface = evaluation.surface
                    elif iter_min_fos is not None and abs(result.fos - iter_min_fos) <= TIE_TOL:
                        assert iter_min_surface is not None
                        candidate_key = surface_key(evaluation.surface)
                        iter_key = surface_key(iter_min_surface)
                        if candidate_key < iter_key:
                            iter_min_surface = evaluation.surface

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
        expanded_retained_indices = retained_indices

        next_active_retained_path = _build_next_retained_path(
            active_retained_path,
            config.divisions_along_slope,
            expanded_retained_indices,
        )
        if not next_active_retained_path:
            next_active_retained_path = active_retained_path

        diagnostics.append(
            AutoRefineIterationDiagnostics(
                iteration=iteration,
                active_x_min=current_x_min,
                active_x_max=current_x_max,
                active_path_segments=active_retained_path,
                generated_surfaces=generated,
                valid_surfaces=valid,
                invalid_surfaces=generated - valid,
                minimum_fos=iter_min_fos,
                minimum_surface=iter_min_surface,
                retained_division_indices=retained_indices,
                expanded_retained_division_indices=expanded_retained_indices,
                next_active_path_segments=next_active_retained_path,
            )
        )

        active_retained_path = next_active_retained_path

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
