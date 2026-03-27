from __future__ import annotations

import math
from bisect import bisect_right

import numpy as np

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import GroundwaterInput, LoadsInput, SliceGeometry, UniformSurchargeInput
from slope_stab.surfaces.circular import CircularSlipSurface


_NEG_HEIGHT_TOL = 1e-9
_VERTICAL_TOL = 1e-12
_WATER_SURFACE_X_TOL = 1e-9


def _integration_nodes(x_edges: np.ndarray, profile: UniformSlopeProfile) -> np.ndarray:
    breakpoints: list[float] = []
    for breakpoint_x in (profile.x_toe, profile.crest_x):
        if float(x_edges[0]) < breakpoint_x < float(x_edges[-1]):
            breakpoints.append(breakpoint_x)

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


def _water_surface_nodes_for_slice(
    surface_points: tuple[tuple[float, float], ...],
    x_left: float,
    x_right: float,
) -> list[float]:
    nodes = [x_left, x_right]
    for x_vertex, _ in surface_points[1:-1]:
        if x_left < x_vertex < x_right:
            nodes.append(x_vertex)
    return sorted(set(nodes))


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
        xs = [point[0] for point in surface_points]
        seg_idx = bisect_right(xs, x) - 1
        seg_idx = max(0, min(seg_idx, len(surface_points) - 2))

    x0, y0 = surface_points[seg_idx]
    x1, y1 = surface_points[seg_idx + 1]
    if abs(x1 - x0) <= _VERTICAL_TOL:
        raise GeometryError("Groundwater surface contains a vertical segment, which is not supported.")
    slope = (y1 - y0) / (x1 - x0)
    y = y0 + slope * (x - x0)
    return y, slope


def _water_surfaces_pore_resultant(
    groundwater: GroundwaterInput,
    x_left: float,
    x_right: float,
    y_base_left: float,
    y_base_right: float,
    alpha_rad: float,
) -> tuple[float, float, float]:
    if groundwater.hu is None:
        raise GeometryError("Groundwater water_surfaces mode requires hu configuration.")
    hu_mode = groundwater.hu.mode
    if hu_mode not in {"custom", "auto"}:
        raise GeometryError(f"Unsupported groundwater hu.mode: {hu_mode}")
    if hu_mode == "custom" and groundwater.hu.value is None:
        raise GeometryError("Groundwater hu.value is required when hu.mode='custom'.")

    nodes = _water_surface_nodes_for_slice(groundwater.surface, x_left, x_right)
    x_min = groundwater.surface[0][0]
    x_max = groundwater.surface[-1][0]
    for x_node in nodes:
        if x_node < x_min - _WATER_SURFACE_X_TOL or x_node > x_max + _WATER_SURFACE_X_TOL:
            raise GeometryError(
                "Groundwater water surface does not cover prescribed slice x-range."
            )

    cos_alpha = math.cos(alpha_rad)
    if abs(cos_alpha) < _VERTICAL_TOL:
        raise GeometryError("Slice base angle is near vertical during groundwater integration.")

    u_values: list[float] = []
    for x_node in nodes:
        y_base = _base_y_linear(x_node, x_left, x_right, y_base_left, y_base_right)
        y_water, slope = _water_surface_y_and_slope(groundwater.surface, x_node)
        h_eff = max(y_water - y_base, 0.0)

        if hu_mode == "custom":
            hu = float(groundwater.hu.value)
            if hu < 0.0 or hu > 1.0:
                raise GeometryError("Groundwater hu.value must be in [0, 1].")
        else:
            alpha_water = math.atan(slope)
            hu = math.cos(alpha_water) ** 2
        u_values.append(groundwater.gamma_w * h_eff * hu)

    segment_forces: list[float] = []
    segment_mid_x: list[float] = []
    for idx in range(len(nodes) - 1):
        x0 = nodes[idx]
        x1 = nodes[idx + 1]
        ds = (x1 - x0) / cos_alpha
        u_avg = 0.5 * (u_values[idx] + u_values[idx + 1])
        u_segment = u_avg * ds
        segment_forces.append(u_segment)
        segment_mid_x.append(0.5 * (x0 + x1))

    pore_force = float(sum(segment_forces))
    if pore_force <= 0.0:
        x_app = 0.5 * (x_left + x_right)
        y_app = _base_y_linear(x_app, x_left, x_right, y_base_left, y_base_right)
        return 0.0, x_app, y_app

    x_app = float(sum(force * x_mid for force, x_mid in zip(segment_forces, segment_mid_x)) / pore_force)
    y_app = _base_y_linear(x_app, x_left, x_right, y_base_left, y_base_right)
    return pore_force, x_app, y_app


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
    alpha_rad: float,
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
            alpha_rad=alpha_rad,
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


def generate_vertical_slices(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    n_slices: int,
    x_left: float,
    x_right: float,
    gamma: float,
    loads: LoadsInput | None = None,
) -> list[SliceGeometry]:
    if n_slices <= 0:
        raise GeometryError("n_slices must be greater than zero.")
    if x_right <= x_left:
        raise GeometryError("x_right must be greater than x_left.")

    dx = (x_right - x_left) / n_slices
    x_edges = np.linspace(x_left, x_right, n_slices + 1, dtype=float)

    x_nodes = _integration_nodes(x_edges, profile)
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

    alpha = np.arctan2(y_base_edges[1:] - y_base_edges[:-1], dx)
    cos_alpha = np.cos(alpha)
    if np.any(np.abs(cos_alpha) < _VERTICAL_TOL):
        bad_idx = int(np.flatnonzero(np.abs(cos_alpha) < _VERTICAL_TOL)[0])
        raise GeometryError(f"Slice {bad_idx + 1} base angle is near vertical.")

    base_length = dx / cos_alpha
    if np.any(base_length <= 0.0):
        bad_idx = int(np.flatnonzero(base_length <= 0.0)[0])
        raise GeometryError(f"Slice {bad_idx + 1} has invalid base length: {float(base_length[bad_idx])}.")

    weights = gamma * slice_areas

    surcharge = loads.uniform_surcharge if loads is not None else None
    groundwater = loads.groundwater if loads is not None else None
    slices: list[SliceGeometry] = []
    for i in range(n_slices):
        ext_force_y = 0.0
        ext_force_x = 0.0
        ext_x_app = float(0.5 * (x_edges[i] + x_edges[i + 1]))
        ext_y_app = float(0.5 * (y_top_edges[i] + y_top_edges[i + 1]))

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
                ext_force_y = surcharge.magnitude_kpa * overlap_width
                ext_x_app = 0.5 * (overlap_left + overlap_right)
                ext_y_app = float(profile.y_ground(ext_x_app))

        pore_force, pore_x_app, pore_y_app = _groundwater_pore_resultant(
            groundwater=groundwater,
            x_left=float(x_edges[i]),
            x_right=float(x_edges[i + 1]),
            y_base_left=float(y_base_edges[i]),
            y_base_right=float(y_base_edges[i + 1]),
            width=float(dx),
            alpha_rad=float(alpha[i]),
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
                width=dx,
                area=float(slice_areas[i]),
                weight=float(weights[i]),
                alpha_rad=float(alpha[i]),
                base_length=float(base_length[i]),
                external_force_x=float(ext_force_x),
                external_force_y=float(ext_force_y),
                external_x_app=float(ext_x_app),
                external_y_app=float(ext_y_app),
                pore_force=float(pore_force),
                pore_x_app=float(pore_x_app),
                pore_y_app=float(pore_y_app),
            )
        )

    return slices
