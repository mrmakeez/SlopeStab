from __future__ import annotations

import math

import numpy as np

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import SliceGeometry
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


def _slice_area_piecewise(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    xl: float,
    xr: float,
) -> float:
    nodes = _integration_nodes(np.asarray([xl, xr], dtype=float), profile)
    y_top = profile.y_ground_array(nodes)
    y_base = surface.y_base_array(nodes)
    heights = y_top - y_base

    if np.any(heights < -_NEG_HEIGHT_TOL):
        bad_idx = int(np.flatnonzero(heights < -_NEG_HEIGHT_TOL)[0])
        xa = float(nodes[max(0, bad_idx - 1)])
        xb = float(nodes[min(len(nodes) - 1, bad_idx)])
        raise GeometryError(
            f"Negative slice height while integrating area segment [{xa}, {xb}]."
        )

    segment_areas = 0.5 * (heights[:-1] + heights[1:]) * (nodes[1:] - nodes[:-1])
    return float(np.sum(segment_areas))


def generate_vertical_slices(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    n_slices: int,
    x_left: float,
    x_right: float,
    gamma: float,
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
    slices: list[SliceGeometry] = []
    for i in range(n_slices):
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
            )
        )

    return slices
