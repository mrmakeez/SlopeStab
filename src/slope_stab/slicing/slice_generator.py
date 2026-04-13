from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq, minimize_scalar

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.materials.soil_domain import SoilDomain
from slope_stab.models import GroundwaterInput, LoadsInput, SeismicLoadInput, SliceGeometry, UniformSurchargeInput
from slope_stab.surfaces.circular import CircularSlipSurface


_NEG_HEIGHT_TOL = 1e-9
_VERTICAL_TOL = 1e-12
_WATER_SURFACE_X_TOL = 1e-9
_PONDED_NUMERIC_SAMPLES = 129
_ROOT_SOLVER_MAXITER = 200


def _slice_edge_tolerances(
    x_left: float,
    x_right: float,
    profile: UniformSlopeProfile,
) -> tuple[float, float]:
    span = max(1.0, x_right - x_left)
    x_tol = 1e-9 * span
    y_tol = 1e-9 * max(1.0, abs(profile.y_toe) + profile.h)
    return float(x_tol), float(y_tol)


def _integration_nodes(
    x_edges: np.ndarray,
    profile: UniformSlopeProfile,
    soil_domain: SoilDomain | None = None,
) -> np.ndarray:
    breakpoints: list[float] = []
    for breakpoint_x in (profile.x_toe, profile.crest_x):
        if float(x_edges[0]) < breakpoint_x < float(x_edges[-1]):
            breakpoints.append(breakpoint_x)

    if soil_domain is not None:
        for polyline in soil_domain.boundary_polylines:
            for x, _ in polyline:
                if float(x_edges[0]) < x < float(x_edges[-1]):
                    breakpoints.append(float(x))

    if not breakpoints:
        return x_edges

    merged = np.concatenate((x_edges, np.asarray(breakpoints, dtype=float)))
    return np.unique(merged)


def _surcharge_overlap_interval(
    surcharge: UniformSurchargeInput,
    profile: UniformSlopeProfile,
    x_left: float,
    x_right: float,
) -> tuple[float, float] | None:
    if surcharge.placement == "crest_infinite":
        overlap_left = max(x_left, profile.crest_x)
        overlap_right = x_right
    else:
        assert surcharge.x_start is not None
        assert surcharge.x_end is not None
        overlap_left = max(x_left, surcharge.x_start)
        overlap_right = min(x_right, surcharge.x_end)

    if overlap_right <= overlap_left:
        return None
    return overlap_left, overlap_right


def _base_y_linear(
    x: float,
    x_left: float,
    x_right: float,
    y_left: float,
    y_right: float,
) -> float:
    width = x_right - x_left
    if abs(width) <= _VERTICAL_TOL:
        return y_left
    ratio = (x - x_left) / width
    return y_left + ratio * (y_right - y_left)


def _water_surface_y_and_slope(
    surface_points: tuple[tuple[float, float], ...],
    x: float,
) -> tuple[float, float]:
    x_min = surface_points[0][0]
    x_max = surface_points[-1][0]
    if x < x_min - _WATER_SURFACE_X_TOL or x > x_max + _WATER_SURFACE_X_TOL:
        raise GeometryError(
            f"Water surface x={x} is outside supplied groundwater surface range [{x_min}, {x_max}]."
        )

    if x <= x_min + _WATER_SURFACE_X_TOL:
        seg_idx = 0
    elif x >= x_max - _WATER_SURFACE_X_TOL:
        seg_idx = len(surface_points) - 2
    else:
        xs = _water_surface_x_coordinates(surface_points)
        seg_idx = bisect_right(xs, x) - 1
        seg_idx = max(0, min(seg_idx, len(surface_points) - 2))

    x0, y0 = surface_points[seg_idx]
    x1, y1 = surface_points[seg_idx + 1]
    if abs(x1 - x0) <= _VERTICAL_TOL:
        raise GeometryError("Groundwater surface contains a vertical segment, which is not supported.")
    slope = (y1 - y0) / (x1 - x0)
    y = y0 + slope * (x - x0)
    return y, slope


@lru_cache(maxsize=64)
def _water_surface_x_coordinates(surface_points: tuple[tuple[float, float], ...]) -> tuple[float, ...]:
    return tuple(point[0] for point in surface_points)


def _surface_water_intersections(
    *,
    surface: CircularSlipSurface,
    surface_points: tuple[tuple[float, float], ...],
    x_left: float,
    x_right: float,
    x_tol: float,
    y_tol: float,
) -> list[float]:
    roots: list[float] = []
    xtol_solver = max(1e-12, x_tol * 0.1)

    for idx in range(len(surface_points) - 1):
        x0, y0 = surface_points[idx]
        x1, y1 = surface_points[idx + 1]
        if abs(x1 - x0) <= _VERTICAL_TOL:
            raise GeometryError("Groundwater surface contains a vertical segment, which is not supported.")

        seg_left = max(x_left, min(x0, x1))
        seg_right = min(x_right, max(x0, x1))
        if seg_right - seg_left <= x_tol:
            continue

        slope = (y1 - y0) / (x1 - x0)
        intercept = y0 - slope * x0

        def f(x: float) -> float:
            return float(surface.y_base(float(x)) - (slope * float(x) + intercept))

        fa = f(seg_left)
        fb = f(seg_right)
        if not math.isfinite(fa) or not math.isfinite(fb):
            continue

        if abs(fa) <= y_tol:
            roots.append(float(seg_left))
        if abs(fb) <= y_tol:
            roots.append(float(seg_right))

        if fa * fb < 0.0:
            try:
                root = brentq(
                    f,
                    float(seg_left),
                    float(seg_right),
                    xtol=xtol_solver,
                    rtol=1e-12,
                    maxiter=_ROOT_SOLVER_MAXITER,
                )
            except (ValueError, RuntimeError):
                root = None
            if root is not None and math.isfinite(root):
                roots.append(float(root))
            continue

        # Tangency path: deterministic bounded minimization of |f(x)| on segment.
        try:
            minimum = minimize_scalar(
                lambda x: abs(f(float(x))),
                bounds=(float(seg_left), float(seg_right)),
                method="bounded",
                options={"xatol": xtol_solver, "maxiter": _ROOT_SOLVER_MAXITER},
            )
        except (ValueError, RuntimeError):
            minimum = None

        if minimum is not None and minimum.success and math.isfinite(minimum.x):
            x_tan = float(minimum.x)
            if abs(f(x_tan)) <= y_tol:
                roots.append(x_tan)

    return roots


def _merge_close_points(
    values: list[float],
    merge_tol: float,
) -> list[float]:
    if not values:
        return []
    ordered = sorted(float(v) for v in values if math.isfinite(v))
    if not ordered:
        return []

    merged: list[float] = []
    cluster: list[float] = [ordered[0]]
    for value in ordered[1:]:
        if abs(value - cluster[-1]) <= merge_tol:
            cluster.append(value)
            continue
        merged.append(float(np.mean(cluster)))
        cluster = [value]
    merged.append(float(np.mean(cluster)))
    return merged


def _collapse_small_intervals(
    points: list[float],
    x_tol: float,
) -> list[float]:
    collapsed = list(points)
    while len(collapsed) > 2:
        widths = np.diff(np.asarray(collapsed, dtype=float))
        bad = [i for i, width in enumerate(widths) if width <= x_tol]
        if not bad:
            break
        idx = bad[0]
        if idx == 0:
            del collapsed[1]
            continue
        if idx + 1 == len(collapsed) - 1:
            del collapsed[idx]
            continue
        left_width = collapsed[idx] - collapsed[idx - 1]
        right_width = collapsed[idx + 2] - collapsed[idx + 1]
        if left_width <= right_width:
            del collapsed[idx]
        else:
            del collapsed[idx + 1]
    return collapsed


def _allocate_interval_slice_counts(
    points: list[float],
    n_slices: int,
    x_tol: float,
) -> np.ndarray | None:
    n_intervals = len(points) - 1
    if n_intervals <= 0 or n_intervals > n_slices:
        return None

    lengths = np.diff(np.asarray(points, dtype=float))
    if np.any(lengths <= x_tol):
        return None

    total_length = float(np.sum(lengths))
    if total_length <= _VERTICAL_TOL:
        return None
    # Full-proportion deterministic allocation with min-one enforcement.
    # This path is retained because it best matches observed Slide2 boundary signatures.
    ideal_counts = n_slices * (lengths / total_length)
    floor_counts = np.floor(ideal_counts).astype(int)
    frac = ideal_counts - floor_counts

    counts = np.maximum(floor_counts, 1)
    delta = int(n_slices - np.sum(counts))

    if delta > 0:
        # Add in order: descending fractional remainder, descending width, ascending index.
        add_order = np.lexsort((np.arange(n_intervals), -lengths, -frac))
        for idx in add_order[:delta]:
            counts[int(idx)] += 1
    elif delta < 0:
        # Remove in order: ascending fractional remainder, ascending width, descending index.
        remove_order = np.lexsort((-np.arange(n_intervals), lengths, frac))
        to_remove = -delta
        for idx in remove_order:
            i = int(idx)
            while to_remove > 0 and counts[i] > 1:
                counts[i] -= 1
                to_remove -= 1
            if to_remove == 0:
                break
        if to_remove > 0:
            return None

    if int(np.sum(counts)) != n_slices or np.any(counts < 1):
        return None
    return counts


def _build_edges_from_counts(
    points: list[float],
    counts: np.ndarray,
    n_slices: int,
) -> np.ndarray | None:
    if len(points) != len(counts) + 1:
        return None

    edges: list[float] = [float(points[0])]
    for idx, count in enumerate(counts):
        segment_edges = np.linspace(float(points[idx]), float(points[idx + 1]), int(count) + 1, dtype=float)
        edges.extend(float(v) for v in segment_edges[1:])

    x_edges = np.asarray(edges, dtype=float)
    if x_edges.size != n_slices + 1:
        return None
    x_edges[0] = float(points[0])
    x_edges[-1] = float(points[-1])
    if np.any(np.diff(x_edges) <= 0.0):
        return None
    return x_edges


def _resolve_slice_edges(
    *,
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    groundwater: GroundwaterInput | None,
    soil_domain: SoilDomain | None,
    x_left: float,
    x_right: float,
    n_slices: int,
) -> np.ndarray:
    uniform_edges = np.linspace(x_left, x_right, n_slices + 1, dtype=float)
    raw_roots: list[float] = []
    if groundwater is not None and groundwater.model == "water_surfaces":
        x_tol, y_tol = _slice_edge_tolerances(x_left=x_left, x_right=x_right, profile=profile)
        raw_roots.extend(
            _surface_water_intersections(
                surface=surface,
                surface_points=groundwater.surface,
                x_left=x_left,
                x_right=x_right,
                x_tol=x_tol,
                y_tol=y_tol,
            )
        )
    if soil_domain is not None and soil_domain.is_non_uniform:
        raw_roots.extend(
            soil_domain.base_boundary_intersection_xs(
                surface=surface,
                x_left=x_left,
                x_right=x_right,
            )
        )

    if not raw_roots:
        return uniform_edges

    x_tol, y_tol = _slice_edge_tolerances(x_left=x_left, x_right=x_right, profile=profile)
    merged_roots = _merge_close_points(raw_roots, merge_tol=10.0 * x_tol)
    internal_roots = [x for x in merged_roots if (x_left + x_tol) < x < (x_right - x_tol)]
    if not internal_roots:
        return uniform_edges

    points = [float(x_left), *internal_roots, float(x_right)]
    points = _merge_close_points(points, merge_tol=10.0 * x_tol)
    if len(points) < 2:
        return uniform_edges
    points[0] = float(x_left)
    points[-1] = float(x_right)
    points = _collapse_small_intervals(points, x_tol=x_tol)
    if len(points) < 2:
        return uniform_edges

    counts = _allocate_interval_slice_counts(points=points, n_slices=n_slices, x_tol=x_tol)
    if counts is None:
        return uniform_edges

    resolved = _build_edges_from_counts(points=points, counts=counts, n_slices=n_slices)
    return uniform_edges if resolved is None else resolved


def _ground_y_and_slope(
    profile: UniformSlopeProfile,
    x: float,
) -> tuple[float, float]:
    y = float(profile.y_ground(x))
    if x < profile.x_toe:
        slope = 0.0
    elif x > profile.crest_x:
        slope = 0.0
    else:
        slope = profile.h / profile.l if abs(profile.l) > _VERTICAL_TOL else 0.0
    return y, float(slope)


def _combine_external_resultants(
    *,
    resultants: list[tuple[float, float, float, float]],
    x_mid: float,
    y_mid: float,
) -> tuple[float, float, float, float]:
    if not resultants:
        return 0.0, 0.0, x_mid, y_mid

    sum_fx = 0.0
    sum_fy = 0.0
    sum_x_fy = 0.0
    sum_y_fx = 0.0
    for fx, fy, x_app, y_app in resultants:
        sum_fx += fx
        sum_fy += fy
        sum_x_fy += x_app * fy
        sum_y_fx += y_app * fx

    if abs(sum_fy) > _VERTICAL_TOL:
        x_app = sum_x_fy / sum_fy
    elif abs(sum_fx) > _VERTICAL_TOL:
        x_app = sum(x_app * abs(fx) for fx, _, x_app, _ in resultants) / sum(
            abs(fx) for fx, _, _, _ in resultants
        )
    else:
        x_app = x_mid

    if abs(sum_fx) > _VERTICAL_TOL:
        y_app = sum_y_fx / sum_fx
    elif abs(sum_fy) > _VERTICAL_TOL:
        y_app = sum(y_app * abs(fy) for _, fy, _, y_app in resultants) / sum(
            abs(fy) for _, fy, _, _ in resultants
        )
    else:
        y_app = y_mid

    return float(sum_fx), float(sum_fy), float(x_app), float(y_app)


def _seismic_inertial_resultant(
    seismic: SeismicLoadInput | None,
    *,
    weight: float,
    x_left: float,
    x_right: float,
    y_top_left: float,
    y_top_right: float,
    y_base_left: float,
    y_base_right: float,
) -> tuple[float, float, float, float]:
    x_mid = 0.5 * (x_left + x_right)
    y_centroid = 0.25 * (y_top_left + y_top_right + y_base_left + y_base_right)
    if seismic is None or seismic.model == "none":
        return 0.0, 0.0, x_mid, y_centroid
    if seismic.model != "pseudo_static":
        raise GeometryError(f"Unsupported seismic model: {seismic.model}")
    if seismic.kv != 0.0:
        raise GeometryError("v1 seismic requires kv = 0.0.")

    # v1 mass basis is soil self-weight only. External vertical loads
    # (surcharge/ponded) and pore-pressure channels are excluded.
    seismic_fx = seismic.kh * weight
    return float(seismic_fx), 0.0, float(x_mid), float(y_centroid)


def _ponded_water_top_resultant(
    profile: UniformSlopeProfile,
    groundwater: GroundwaterInput,
    x_left: float,
    x_right: float,
) -> tuple[float, float, float, float]:
    if groundwater.model != "water_surfaces":
        return 0.0, 0.0, 0.5 * (x_left + x_right), float(profile.y_ground(0.5 * (x_left + x_right)))

    x_min = groundwater.surface[0][0]
    x_max = groundwater.surface[-1][0]
    x_eval_left = max(x_left, x_min)
    x_eval_right = min(x_right, x_max)
    x_mid = 0.5 * (x_left + x_right)
    y_mid = float(profile.y_ground(x_mid))
    if x_eval_right <= x_eval_left:
        return 0.0, 0.0, x_mid, y_mid

    # Deterministic fixed-node numerical integration; this keeps behavior stable
    # while allowing ponded-depth integration across piecewise profile/water surfaces.
    xs = np.linspace(x_eval_left, x_eval_right, _PONDED_NUMERIC_SAMPLES, dtype=float)
    y_ground = np.empty_like(xs)
    slopes = np.empty_like(xs)
    y_water = np.empty_like(xs)
    for idx, x in enumerate(xs):
        y_g, slope_g = _ground_y_and_slope(profile, float(x))
        y_w, _ = _water_surface_y_and_slope(groundwater.surface, float(x))
        y_ground[idx] = y_g
        slopes[idx] = slope_g
        y_water[idx] = y_w

    depth = np.maximum(y_water - y_ground, 0.0)
    area = float(np.trapezoid(depth, xs))
    if area <= _VERTICAL_TOL:
        return 0.0, 0.0, x_mid, y_mid

    gamma_w = float(groundwater.gamma_w)
    fy = gamma_w * area

    x_depth_moment = float(np.trapezoid(xs * depth, xs))
    x_fy_moment = gamma_w * x_depth_moment
    x_app_fy = x_fy_moment / fy if abs(fy) > _VERTICAL_TOL else x_mid

    # Horizontal hydrostatic resultant on sloping submerged top profile.
    fx_density = depth * slopes
    fx = -gamma_w * float(np.trapezoid(fx_density, xs))
    y_fx_moment = -gamma_w * float(np.trapezoid(y_ground * fx_density, xs))
    y_app_fx = y_fx_moment / fx if abs(fx) > _VERTICAL_TOL else y_mid

    x_app = float(x_app_fy)
    y_app = float(y_app_fx if abs(fx) > _VERTICAL_TOL else profile.y_ground(x_app))
    return float(fx), float(fy), x_app, y_app


def _water_surfaces_pore_resultant(
    groundwater: GroundwaterInput,
    x_left: float,
    x_right: float,
    y_base_left: float,
    y_base_right: float,
    base_length: float,
) -> tuple[float, float, float]:
    if groundwater.hu is None:
        raise GeometryError("Groundwater water_surfaces mode requires hu configuration.")
    hu_mode = groundwater.hu.mode
    if hu_mode not in {"custom", "auto"}:
        raise GeometryError(f"Unsupported groundwater hu.mode: {hu_mode}")
    if hu_mode == "custom" and groundwater.hu.value is None:
        raise GeometryError("Groundwater hu.value is required when hu.mode='custom'.")
    x_app = 0.5 * (x_left + x_right)
    y_app = _base_y_linear(x_app, x_left, x_right, y_base_left, y_base_right)
    y_water, slope = _water_surface_y_and_slope(groundwater.surface, x_app)
    h_eff = max(y_water - y_app, 0.0)

    if hu_mode == "custom":
        hu = float(groundwater.hu.value)
        if hu < 0.0 or hu > 1.0:
            raise GeometryError("Groundwater hu.value must be in [0, 1].")
    else:
        alpha_water = math.atan(slope)
        hu = math.cos(alpha_water) ** 2

    u_mid = groundwater.gamma_w * h_eff * hu
    pore_force = float(u_mid * base_length)
    return pore_force, float(x_app), float(y_app)


def _ru_pore_resultant(
    groundwater: GroundwaterInput,
    x_left: float,
    x_right: float,
    y_base_left: float,
    y_base_right: float,
    width: float,
    base_length: float,
    weight: float,
) -> tuple[float, float, float]:
    if groundwater.ru is None:
        raise GeometryError("Groundwater ru_coefficient mode requires ru value.")
    if groundwater.ru < 0.0 or groundwater.ru > 1.0:
        raise GeometryError("Groundwater ru must be in [0, 1].")
    if width <= 0.0:
        raise GeometryError("Slice width must be greater than zero for Ru pore-pressure calculations.")

    sigma_v = weight / width
    u = groundwater.ru * sigma_v
    pore_force = u * base_length
    x_app = 0.5 * (x_left + x_right)
    y_app = _base_y_linear(x_app, x_left, x_right, y_base_left, y_base_right)
    return float(pore_force), float(x_app), float(y_app)


def _groundwater_pore_resultant(
    groundwater: GroundwaterInput | None,
    *,
    x_left: float,
    x_right: float,
    y_base_left: float,
    y_base_right: float,
    width: float,
    base_length: float,
    weight: float,
) -> tuple[float, float, float]:
    x_mid = 0.5 * (x_left + x_right)
    y_mid = _base_y_linear(x_mid, x_left, x_right, y_base_left, y_base_right)
    if groundwater is None or groundwater.model == "none":
        return 0.0, x_mid, y_mid
    if groundwater.model == "water_surfaces":
        return _water_surfaces_pore_resultant(
            groundwater=groundwater,
            x_left=x_left,
            x_right=x_right,
            y_base_left=y_base_left,
            y_base_right=y_base_right,
            base_length=base_length,
        )
    if groundwater.model == "ru_coefficient":
        return _ru_pore_resultant(
            groundwater=groundwater,
            x_left=x_left,
            x_right=x_right,
            y_base_left=y_base_left,
            y_base_right=y_base_right,
            width=width,
            base_length=base_length,
            weight=weight,
        )
    raise GeometryError(f"Unsupported groundwater model: {groundwater.model}")


def _material_length_vector(
    *,
    soil_domain: SoilDomain,
    material_ids: tuple[str, ...],
    x: float,
    y_base: float,
    y_top: float,
) -> np.ndarray:
    lengths = soil_domain.vertical_material_lengths(x=x, y_bottom=y_base, y_top=y_top)
    vector = np.zeros(len(material_ids), dtype=float)
    for idx, material_id in enumerate(material_ids):
        vector[idx] = float(lengths.get(material_id, 0.0))
    return vector


def _integrate_material_areas(
    *,
    soil_domain: SoilDomain,
    material_ids: tuple[str, ...],
    x_nodes: np.ndarray,
    y_base_nodes: np.ndarray,
    y_top_nodes: np.ndarray,
) -> np.ndarray:
    n_nodes = x_nodes.size
    lengths = np.zeros((n_nodes, len(material_ids)), dtype=float)
    for idx in range(n_nodes):
        lengths[idx, :] = _material_length_vector(
            soil_domain=soil_domain,
            material_ids=material_ids,
            x=float(x_nodes[idx]),
            y_base=float(y_base_nodes[idx]),
            y_top=float(y_top_nodes[idx]),
        )
    dx = x_nodes[1:] - x_nodes[:-1]
    return 0.5 * (lengths[:-1, :] + lengths[1:, :]) * dx[:, np.newaxis]


def _slice_base_material(
    *,
    soil_domain: SoilDomain,
    x_left: float,
    y_base_left: float,
    x_right: float,
    y_base_right: float,
) -> tuple[str, float, float]:
    base_segments = soil_domain.base_material_segments(
        x_left=x_left,
        y_left=y_base_left,
        x_right=x_right,
        y_right=y_base_right,
    )
    if not base_segments:
        raise GeometryError("Unable to resolve base material for slice; no base segments found.")

    material_lengths: dict[str, float] = defaultdict(float)
    for item in base_segments:
        material_lengths[item.material_id] += item.length
    significant = [material_id for material_id, length in material_lengths.items() if length > 1e-7]
    if len(significant) != 1:
        raise GeometryError(
            "Slice base intersects multiple materials after boundary-edge insertion; "
            f"materials={sorted(significant)}."
        )

    material = soil_domain.materials[significant[0]]
    return material.id, material.c, material.phi_deg


def generate_vertical_slices(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    n_slices: int,
    x_left: float,
    x_right: float,
    gamma: float | None = None,
    soil_domain: SoilDomain | None = None,
    loads: LoadsInput | None = None,
) -> list[SliceGeometry]:
    if n_slices <= 0:
        raise GeometryError("n_slices must be greater than zero.")
    if x_right <= x_left:
        raise GeometryError("x_right must be greater than x_left.")
    if soil_domain is None and gamma is None:
        raise GeometryError("Either gamma or soil_domain must be provided for slice generation.")
    if soil_domain is not None and len(soil_domain.materials) == 0:
        raise GeometryError("Soil domain has no materials.")
    uniform_material = (
        next(iter(soil_domain.materials.values()))
        if soil_domain is not None and not soil_domain.is_non_uniform
        else None
    )

    groundwater = loads.groundwater if loads is not None else None
    seismic = loads.seismic if loads is not None else None
    x_edges = _resolve_slice_edges(
        profile=profile,
        surface=surface,
        groundwater=groundwater,
        soil_domain=soil_domain,
        x_left=x_left,
        x_right=x_right,
        n_slices=n_slices,
    )

    x_nodes = _integration_nodes(x_edges, profile, soil_domain)
    y_top_nodes = profile.y_ground_array(x_nodes)
    y_base_nodes = surface.y_base_array(x_nodes)
    heights_nodes = y_top_nodes - y_base_nodes

    if np.any(heights_nodes < -_NEG_HEIGHT_TOL):
        bad_idx = int(np.flatnonzero(heights_nodes < -_NEG_HEIGHT_TOL)[0])
        xa = float(x_nodes[max(0, bad_idx - 1)])
        xb = float(x_nodes[min(len(x_nodes) - 1, bad_idx)])
        raise GeometryError(
            f"Negative slice height while integrating area segment [{xa}, {xb}]."
        )

    segment_areas = 0.5 * (heights_nodes[:-1] + heights_nodes[1:]) * (x_nodes[1:] - x_nodes[:-1])
    cumulative_area = np.concatenate((np.array([0.0]), np.cumsum(segment_areas)))

    edge_indices = np.searchsorted(x_nodes, x_edges)
    slice_areas = cumulative_area[edge_indices[1:]] - cumulative_area[edge_indices[:-1]]

    material_ids: tuple[str, ...]
    material_gamma: np.ndarray
    if soil_domain is None or not soil_domain.is_non_uniform:
        if soil_domain is None:
            if gamma is None:
                raise GeometryError("Uniform gamma must be provided when soil_domain is not supplied.")
            material_ids = ("soil",)
            material_gamma = np.array([float(gamma)], dtype=float)
        else:
            if uniform_material is None:
                raise GeometryError("Uniform soil material could not be resolved.")
            material_ids = (uniform_material.id,)
            material_gamma = np.array([float(uniform_material.gamma)], dtype=float)
        material_segment_areas = segment_areas[:, np.newaxis]
    else:
        material_ids = tuple(sorted(soil_domain.materials.keys()))
        material_gamma = np.array([soil_domain.materials[m_id].gamma for m_id in material_ids], dtype=float)
        material_segment_areas = _integrate_material_areas(
            soil_domain=soil_domain,
            material_ids=material_ids,
            x_nodes=x_nodes,
            y_base_nodes=y_base_nodes,
            y_top_nodes=y_top_nodes,
        )

    material_cumulative_areas = np.vstack(
        [
            np.zeros((1, len(material_ids)), dtype=float),
            np.cumsum(material_segment_areas, axis=0),
        ]
    )
    material_slice_areas = material_cumulative_areas[edge_indices[1:], :] - material_cumulative_areas[edge_indices[:-1], :]

    y_top_edges = y_top_nodes[edge_indices]
    y_base_edges = y_base_nodes[edge_indices]

    h_left = y_top_edges[:-1] - y_base_edges[:-1]
    h_right = y_top_edges[1:] - y_base_edges[1:]
    if np.any(h_left < -_NEG_HEIGHT_TOL) or np.any(h_right < -_NEG_HEIGHT_TOL):
        bad_idx = int(np.flatnonzero((h_left < -_NEG_HEIGHT_TOL) | (h_right < -_NEG_HEIGHT_TOL))[0])
        raise GeometryError(
            f"Slice {bad_idx + 1} has negative height(s): h_left={float(h_left[bad_idx])}, h_right={float(h_right[bad_idx])}."
        )

    if np.any(slice_areas <= 0.0):
        bad_idx = int(np.flatnonzero(slice_areas <= 0.0)[0])
        raise GeometryError(f"Slice {bad_idx + 1} has non-positive area: {float(slice_areas[bad_idx])}.")

    widths = x_edges[1:] - x_edges[:-1]
    if np.any(widths <= 0.0):
        bad_idx = int(np.flatnonzero(widths <= 0.0)[0])
        raise GeometryError(f"Slice {bad_idx + 1} has non-positive width: {float(widths[bad_idx])}.")

    alpha = np.arctan2(y_base_edges[1:] - y_base_edges[:-1], widths)
    cos_alpha = np.cos(alpha)
    if np.any(np.abs(cos_alpha) < _VERTICAL_TOL):
        bad_idx = int(np.flatnonzero(np.abs(cos_alpha) < _VERTICAL_TOL)[0])
        raise GeometryError(f"Slice {bad_idx + 1} base angle is near vertical.")

    base_length = widths / cos_alpha
    if np.any(base_length <= 0.0):
        bad_idx = int(np.flatnonzero(base_length <= 0.0)[0])
        raise GeometryError(f"Slice {bad_idx + 1} has invalid base length: {float(base_length[bad_idx])}.")

    weights = material_slice_areas @ material_gamma

    surcharge = loads.uniform_surcharge if loads is not None else None
    slices: list[SliceGeometry] = []
    for i in range(n_slices):
        if soil_domain is None:
            base_material_id = ""
            base_cohesion = 0.0
            base_phi_deg = 0.0
        elif not soil_domain.is_non_uniform:
            if uniform_material is None:
                raise GeometryError("Uniform soil material could not be resolved.")
            base_material_id = uniform_material.id
            base_cohesion = float(uniform_material.c)
            base_phi_deg = float(uniform_material.phi_deg)
        else:
            base_material_id, base_cohesion, base_phi_deg = _slice_base_material(
                soil_domain=soil_domain,
                x_left=float(x_edges[i]),
                y_base_left=float(y_base_edges[i]),
                x_right=float(x_edges[i + 1]),
                y_base_right=float(y_base_edges[i + 1]),
            )

        weight_contributions = tuple(
            (
                material_ids[j],
                float(material_slice_areas[i, j] * material_gamma[j]),
            )
            for j in range(len(material_ids))
            if abs(float(material_slice_areas[i, j] * material_gamma[j])) > 1e-10
        )

        x_mid = float(0.5 * (x_edges[i] + x_edges[i + 1]))
        y_mid = float(0.5 * (y_top_edges[i] + y_top_edges[i + 1]))
        ext_resultants: list[tuple[float, float, float, float]] = []

        if surcharge is not None and surcharge.magnitude_kpa > 0.0:
            overlap_interval = _surcharge_overlap_interval(
                surcharge=surcharge,
                profile=profile,
                x_left=float(x_edges[i]),
                x_right=float(x_edges[i + 1]),
            )
            if overlap_interval is not None:
                overlap_left, overlap_right = overlap_interval
                overlap_width = overlap_right - overlap_left
                surcharge_fy = surcharge.magnitude_kpa * overlap_width
                surcharge_x_app = 0.5 * (overlap_left + overlap_right)
                surcharge_y_app = float(profile.y_ground(surcharge_x_app))
                ext_resultants.append((0.0, float(surcharge_fy), float(surcharge_x_app), float(surcharge_y_app)))

        if groundwater is not None and groundwater.model == "water_surfaces":
            ponded_fx, ponded_fy, ponded_x_app, ponded_y_app = _ponded_water_top_resultant(
                profile=profile,
                groundwater=groundwater,
                x_left=float(x_edges[i]),
                x_right=float(x_edges[i + 1]),
            )
            if abs(ponded_fx) > _VERTICAL_TOL or abs(ponded_fy) > _VERTICAL_TOL:
                ext_resultants.append((ponded_fx, ponded_fy, ponded_x_app, ponded_y_app))

        seismic_fx, seismic_fy, seismic_x_app, seismic_y_app = _seismic_inertial_resultant(
            seismic,
            weight=float(weights[i]),
            x_left=float(x_edges[i]),
            x_right=float(x_edges[i + 1]),
            y_top_left=float(y_top_edges[i]),
            y_top_right=float(y_top_edges[i + 1]),
            y_base_left=float(y_base_edges[i]),
            y_base_right=float(y_base_edges[i + 1]),
        )
        if abs(seismic_fx) > _VERTICAL_TOL or abs(seismic_fy) > _VERTICAL_TOL:
            ext_resultants.append((seismic_fx, seismic_fy, seismic_x_app, seismic_y_app))

        ext_force_x, ext_force_y, ext_x_app, ext_y_app = _combine_external_resultants(
            resultants=ext_resultants,
            x_mid=x_mid,
            y_mid=y_mid,
        )

        pore_force, pore_x_app, pore_y_app = _groundwater_pore_resultant(
            groundwater=groundwater,
            x_left=float(x_edges[i]),
            x_right=float(x_edges[i + 1]),
            y_base_left=float(y_base_edges[i]),
            y_base_right=float(y_base_edges[i + 1]),
            width=float(widths[i]),
            base_length=float(base_length[i]),
            weight=float(weights[i]),
        )

        slices.append(
            SliceGeometry(
                slice_id=i + 1,
                x_left=float(x_edges[i]),
                x_right=float(x_edges[i + 1]),
                y_top_left=float(y_top_edges[i]),
                y_top_right=float(y_top_edges[i + 1]),
                y_base_left=float(y_base_edges[i]),
                y_base_right=float(y_base_edges[i + 1]),
                width=float(widths[i]),
                area=float(slice_areas[i]),
                weight=float(weights[i]),
                alpha_rad=float(alpha[i]),
                base_length=float(base_length[i]),
                external_force_x=float(ext_force_x),
                external_force_y=float(ext_force_y),
                external_x_app=float(ext_x_app),
                external_y_app=float(ext_y_app),
                seismic_force_x=float(seismic_fx),
                seismic_force_y=float(seismic_fy),
                pore_force=float(pore_force),
                pore_x_app=float(pore_x_app),
                pore_y_app=float(pore_y_app),
                base_material_id=base_material_id,
                base_cohesion=float(base_cohesion),
                base_phi_deg=float(base_phi_deg),
                material_weight_contributions=weight_contributions,
            )
        )

    return slices
