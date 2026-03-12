from __future__ import annotations

import math

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import SliceGeometry
from slope_stab.surfaces.circular import CircularSlipSurface


def _slice_area_piecewise(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    xl: float,
    xr: float,
) -> float:
    cuts = [xl, xr]
    for break_x in (profile.x_toe, profile.crest_x):
        if xl < break_x < xr:
            cuts.append(break_x)
    cuts.sort()

    area = 0.0
    for xa, xb in zip(cuts[:-1], cuts[1:]):
        ht_a = profile.y_ground(xa) - surface.y_base(xa)
        ht_b = profile.y_ground(xb) - surface.y_base(xb)
        if ht_a < -1e-9 or ht_b < -1e-9:
            raise GeometryError(
                f"Negative slice height while integrating area segment [{xa}, {xb}]."
            )
        area += 0.5 * (ht_a + ht_b) * (xb - xa)
    return area


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
    slices: list[SliceGeometry] = []

    for i in range(n_slices):
        xl = x_left + i * dx
        xr = x_left + (i + 1) * dx

        yt_l = profile.y_ground(xl)
        yt_r = profile.y_ground(xr)
        yb_l = surface.y_base(xl)
        yb_r = surface.y_base(xr)

        h_l = yt_l - yb_l
        h_r = yt_r - yb_r
        if h_l < -1e-9 or h_r < -1e-9:
            raise GeometryError(
                f"Slice {i + 1} has negative height(s): h_left={h_l}, h_right={h_r}."
            )

        area = _slice_area_piecewise(profile, surface, xl, xr)
        if area <= 0.0:
            raise GeometryError(f"Slice {i + 1} has non-positive area: {area}.")

        alpha = math.atan2(yb_r - yb_l, dx)
        cos_alpha = math.cos(alpha)
        if abs(cos_alpha) < 1e-12:
            raise GeometryError(f"Slice {i + 1} base angle is near vertical.")

        base_length = dx / cos_alpha
        if base_length <= 0:
            raise GeometryError(f"Slice {i + 1} has invalid base length: {base_length}.")

        slices.append(
            SliceGeometry(
                slice_id=i + 1,
                x_left=xl,
                x_right=xr,
                y_top_left=yt_l,
                y_top_right=yt_r,
                y_base_left=yb_l,
                y_base_right=yb_r,
                width=dx,
                area=area,
                weight=gamma * area,
                alpha_rad=alpha,
                base_length=base_length,
            )
        )

    return slices
