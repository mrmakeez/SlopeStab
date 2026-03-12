from __future__ import annotations

from dataclasses import dataclass
import math
import random
from statistics import fmean

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisInput, AnalysisResult, AutoRefineInput
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


@dataclass(frozen=True)
class CandidateOutcome:
    pair: tuple[int, int]
    x_left: float
    y_left: float
    x_right: float
    y_right: float
    xc: float
    yc: float
    r: float
    result: AnalysisResult


def build_search_domain(profile: UniformSlopeProfile, settings: AutoRefineInput) -> tuple[float, float]:
    x_min = profile.x_toe - settings.toe_extension_h * profile.h
    x_max = profile.crest_x + settings.crest_extension_h * profile.h
    return x_min, x_max


def build_pair_indices(divisions: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(divisions) for j in range(i + 1, divisions)]


def build_surface_from_endpoints_and_radius(
    x_left: float,
    y_left: float,
    x_right: float,
    y_right: float,
    r: float,
) -> CircularSlipSurface | None:
    dx = x_right - x_left
    dy = y_right - y_left
    chord = math.hypot(dx, dy)
    if chord <= 0 or r <= 0.5 * chord:
        return None

    mx = 0.5 * (x_left + x_right)
    my = 0.5 * (y_left + y_right)

    half = 0.5 * chord
    h = math.sqrt(max(r * r - half * half, 0.0))
    nx = -dy / chord
    ny = dx / chord

    c1 = (mx + h * nx, my + h * ny)
    c2 = (mx - h * nx, my - h * ny)

    y_cap = max(y_left, y_right)
    viable = [c for c in (c1, c2) if c[1] > y_cap]
    if not viable:
        return None

    xc, yc = max(viable, key=lambda c: c[1])
    return CircularSlipSurface(xc=xc, yc=yc, r=r)


def is_surface_below_ground(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    x_left: float,
    x_right: float,
    n_slices: int,
) -> bool:
    for i in range(n_slices + 1):
        x = x_left + (x_right - x_left) * i / n_slices
        try:
            yb = surface.y_base(x)
        except GeometryError:
            return False
        if yb > profile.y_ground(x) + 1e-9:
            return False
    return True


def _evaluate_candidate(
    profile: UniformSlopeProfile,
    material: MohrCoulombMaterial,
    analysis: AnalysisInput,
    surface: CircularSlipSurface,
    x_left: float,
    x_right: float,
) -> AnalysisResult:
    slices = generate_vertical_slices(
        profile=profile,
        surface=surface,
        n_slices=analysis.n_slices,
        x_left=x_left,
        x_right=x_right,
        gamma=material.gamma,
    )
    solver = BishopSimplifiedSolver(material=material, analysis=analysis, surface=surface)
    return solver.solve(slices)


def run_auto_refine_search(
    *,
    profile: UniformSlopeProfile,
    material: MohrCoulombMaterial,
    analysis: AnalysisInput,
    settings: AutoRefineInput,
    top_n: int,
) -> tuple[AnalysisResult, dict]:
    rng = random.Random(settings.seed)

    x_min, x_max = build_search_domain(profile, settings)
    div_w = (x_max - x_min) / settings.divisions
    bins = [(x_min + i * div_w, x_min + (i + 1) * div_w) for i in range(settings.divisions)]

    current_pairs = build_pair_indices(settings.divisions)
    iteration_summaries: list[dict] = []
    all_valid: list[CandidateOutcome] = []
    total_generated = 0

    for it in range(1, settings.iterations + 1):
        if not current_pairs:
            break

        outcomes: list[CandidateOutcome] = []

        for pair in current_pairs:
            i, j = pair
            left_bin = bins[i]
            right_bin = bins[j]

            for _ in range(settings.circles_per_pair):
                total_generated += 1

                x_left = rng.uniform(left_bin[0], left_bin[1])
                x_right = rng.uniform(right_bin[0], right_bin[1])
                if x_right <= x_left:
                    continue
                if (x_right - x_left) < settings.min_span_h * profile.h:
                    continue

                y_left = profile.y_ground(x_left)
                y_right = profile.y_ground(x_right)

                chord = math.hypot(x_right - x_left, y_right - y_left)
                r_min = 0.5 * chord * (1.0 + 1e-6)
                r_max = max(settings.radius_max_h * profile.h, 1.05 * r_min)
                r = rng.uniform(r_min, r_max)

                surface = build_surface_from_endpoints_and_radius(
                    x_left=x_left,
                    y_left=y_left,
                    x_right=x_right,
                    y_right=y_right,
                    r=r,
                )
                if surface is None:
                    continue

                if not is_surface_below_ground(profile, surface, x_left, x_right, analysis.n_slices):
                    continue

                try:
                    result = _evaluate_candidate(
                        profile=profile,
                        material=material,
                        analysis=analysis,
                        surface=surface,
                        x_left=x_left,
                        x_right=x_right,
                    )
                except (GeometryError, ConvergenceError, ValueError):
                    continue

                outcomes.append(
                    CandidateOutcome(
                        pair=pair,
                        x_left=x_left,
                        y_left=y_left,
                        x_right=x_right,
                        y_right=y_right,
                        xc=surface.xc,
                        yc=surface.yc,
                        r=surface.r,
                        result=result,
                    )
                )

        if not outcomes:
            iteration_summaries.append(
                {
                    "iteration": it,
                    "pairs_evaluated": len(current_pairs),
                    "candidates_generated": len(current_pairs) * settings.circles_per_pair,
                    "valid_surfaces": 0,
                    "best_fos": None,
                    "mean_fos": None,
                    "retained_count": 0,
                }
            )
            break

        outcomes.sort(key=lambda c: c.result.fos)
        all_valid.extend(outcomes)

        retain_count = max(1, math.ceil(settings.retain_ratio * len(outcomes)))
        retained = outcomes[:retain_count]

        iteration_summaries.append(
            {
                "iteration": it,
                "pairs_evaluated": len(current_pairs),
                "candidates_generated": len(current_pairs) * settings.circles_per_pair,
                "valid_surfaces": len(outcomes),
                "best_fos": outcomes[0].result.fos,
                "mean_fos": fmean([o.result.fos for o in outcomes]),
                "retained_count": retain_count,
            }
        )

        current_pairs = sorted({o.pair for o in retained})

    if not all_valid:
        raise GeometryError("Auto-refine search produced no valid converged surfaces.")

    all_valid.sort(key=lambda c: c.result.fos)
    best = all_valid[0]
    top = all_valid[: max(1, top_n)]

    search_payload = {
        "mode": "auto_refine",
        "seed": settings.seed,
        "settings": {
            "divisions": settings.divisions,
            "circles_per_pair": settings.circles_per_pair,
            "iterations": settings.iterations,
            "retain_ratio": settings.retain_ratio,
            "toe_extension_h": settings.toe_extension_h,
            "crest_extension_h": settings.crest_extension_h,
            "min_span_h": settings.min_span_h,
            "radius_max_h": settings.radius_max_h,
        },
        "domain": {"x_min": x_min, "x_max": x_max},
        "total_surfaces_generated": total_generated,
        "total_valid_surfaces": len(all_valid),
        "iteration_summaries": iteration_summaries,
        "best_surface": {
            "xc": best.xc,
            "yc": best.yc,
            "r": best.r,
            "x_left": best.x_left,
            "y_left": best.y_left,
            "x_right": best.x_right,
            "y_right": best.y_right,
            "fos": best.result.fos,
        },
        "top_surfaces": [
            {
                "rank": idx + 1,
                "fos": c.result.fos,
                "xc": c.xc,
                "yc": c.yc,
                "r": c.r,
                "x_left": c.x_left,
                "y_left": c.y_left,
                "x_right": c.x_right,
                "y_right": c.y_right,
            }
            for idx, c in enumerate(top)
        ],
    }

    return best.result, search_payload
