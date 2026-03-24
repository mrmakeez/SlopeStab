from __future__ import annotations

import math

import numpy as np

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import LoadsInput, SliceGeometry, UniformSurchargeInput
from slope_stab.surfaces.circular import CircularSlipSurface


_NEG_HEIGHT_TOL = 1e-9
_VERTICAL_TOL = 1e-12


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
                pore_force=0.0,
                pore_x_app=float(ext_x_app),
                pore_y_app=float(ext_y_app),
            )
        )

    return slices
