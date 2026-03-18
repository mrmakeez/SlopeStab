from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, PrescribedCircleInput


Vector3 = tuple[float, float, float]
SurfaceEvaluator = Callable[[PrescribedCircleInput], AnalysisResult]

X_SEP_MIN = 0.05
BETA_MIN_RAD = math.radians(0.5)
BETA_MAX_RAD = math.radians(89.5)
TIE_TOL = 1e-12
CACHE_ROUND = 15


@dataclass(frozen=True)
class CandidateEvaluation:
    surface: PrescribedCircleInput | None
    result: AnalysisResult | None
    valid: bool
    reason: str


def clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def reflect01(value: float) -> float:
    reflected = float(value)
    while reflected < 0.0 or reflected > 1.0:
        if reflected < 0.0:
            reflected = -reflected
        if reflected > 1.0:
            reflected = 2.0 - reflected
    return clip01(reflected)


def repair_vector_clip(vector: Vector3) -> Vector3:
    return (clip01(vector[0]), clip01(vector[1]), clip01(vector[2]))


def repair_vector_reflect(vector: Vector3) -> Vector3:
    return (reflect01(vector[0]), reflect01(vector[1]), reflect01(vector[2]))


def round_vector(vector: Vector3, digits: int = CACHE_ROUND) -> Vector3:
    return (round(vector[0], digits), round(vector[1], digits), round(vector[2], digits))


def surface_key(surface: PrescribedCircleInput) -> tuple[float, float, float]:
    return (surface.x_left, surface.x_right, surface.r)


def is_better_score(
    candidate_score: float,
    candidate_surface: PrescribedCircleInput,
    best_score: float,
    best_surface: PrescribedCircleInput | None,
) -> bool:
    if best_surface is None:
        return True
    if candidate_score < best_score - TIE_TOL:
        return True
    if abs(candidate_score - best_score) <= TIE_TOL and surface_key(candidate_surface) < surface_key(best_surface):
        return True
    return False


def circle_from_endpoints_and_tangent(
    p_left: tuple[float, float],
    p_right: tuple[float, float],
    beta: float,
) -> PrescribedCircleInput | None:
    x1, y1 = p_left
    x2, y2 = p_right
    if x2 <= x1:
        return None
    if beta <= 0.0 or beta >= 0.5 * math.pi:
        return None

    dx = x2 - x1
    dy = y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0.0:
        return None

    sin_beta = math.sin(beta)
    tan_beta = math.tan(beta)
    if abs(sin_beta) <= 1e-12 or abs(tan_beta) <= 1e-12:
        return None

    radius = chord / (2.0 * sin_beta)
    center_offset = chord / (2.0 * tan_beta)
    if radius <= 0.0 or not math.isfinite(radius) or not math.isfinite(center_offset):
        return None

    mid_x = 0.5 * (x1 + x2)
    mid_y = 0.5 * (y1 + y2)

    normal_x = -dy / chord
    normal_y = dx / chord
    if normal_y < 0.0:
        normal_x = -normal_x
        normal_y = -normal_y

    xc = mid_x + center_offset * normal_x
    yc = mid_y + center_offset * normal_y
    if not math.isfinite(xc) or not math.isfinite(yc):
        return None
    if yc <= max(y1, y2) + 1e-9:
        return None

    return PrescribedCircleInput(
        xc=xc,
        yc=yc,
        r=radius,
        x_left=x1,
        y_left=y1,
        x_right=x2,
        y_right=y2,
    )


def map_vector_to_surface(
    profile: UniformSlopeProfile,
    x_min: float,
    x_max: float,
    vector: Vector3,
    repair_vector: Callable[[Vector3], Vector3],
) -> PrescribedCircleInput | None:
    u_left, u_span, u_beta = repair_vector(vector)
    width = x_max - x_min
    if width <= X_SEP_MIN:
        return None

    left_range = width - X_SEP_MIN
    x_left = x_min + u_left * left_range
    right_range = x_max - x_left - X_SEP_MIN
    if right_range < 0.0:
        return None

    x_right = x_left + X_SEP_MIN + u_span * right_range
    if x_right <= x_left:
        return None

    y_left = profile.y_ground(x_left)
    y_right = profile.y_ground(x_right)
    beta = BETA_MIN_RAD + u_beta * (BETA_MAX_RAD - BETA_MIN_RAD)
    return circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)


def evaluate_surface_candidate(
    surface: PrescribedCircleInput | None,
    evaluate_surface: SurfaceEvaluator,
    driving_moment_tol: float = 1e-9,
) -> CandidateEvaluation:
    if surface is None:
        return CandidateEvaluation(surface=None, result=None, valid=False, reason="invalid_geometry")

    try:
        result = evaluate_surface(surface)
    except (ConvergenceError, GeometryError, ValueError):
        return CandidateEvaluation(surface=surface, result=None, valid=False, reason="evaluation_exception")

    if (
        (not result.converged)
        or (not math.isfinite(result.fos))
        or result.fos <= 0.0
        or (not math.isfinite(result.driving_moment))
        or abs(result.driving_moment) <= driving_moment_tol
        or (not math.isfinite(result.resisting_moment))
    ):
        return CandidateEvaluation(surface=surface, result=result, valid=False, reason="nonconverged_or_invalid_fos")

    return CandidateEvaluation(surface=surface, result=result, valid=True, reason="valid")
