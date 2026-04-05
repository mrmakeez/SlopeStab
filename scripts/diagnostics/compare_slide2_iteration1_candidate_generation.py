from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import PrescribedCircleInput
from slope_stab.search.auto_refine import (
    _build_retained_path,
    _division_boundaries_and_midpoints_for_retained_path,
    _generate_pre_polish_pair_candidates,
    _surface_has_reverse_curvature,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUND_DIGITS = 6


@dataclass(frozen=True)
class Scenario:
    name: str
    profile: UniformSlopeProfile
    search_x_min: float
    search_x_max: float
    divisions_along_slope: int
    circles_per_division: int
    model_boundary_floor_y: float
    s01_relpath: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="Case2_Search_Iter_1",
        profile=UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
        search_x_min=0.0,
        search_x_max=35.0,
        divisions_along_slope=20,
        circles_per_division=10,
        model_boundary_floor_y=0.0,
        s01_relpath="Verification/Bishop/Case 2/Case2_Search_Iter_1/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01",
    ),
    Scenario(
        name="Case4_Iter1",
        profile=UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=30,
        circles_per_division=15,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
    Scenario(
        name="Case4_Iter1_Simple",
        profile=UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=5,
        circles_per_division=5,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
)


SurfaceKey = tuple[float, float, float, float, float, float, float]


def _parse_slide2_s01_surfaces(path: Path) -> set[SurfaceKey]:
    lines = path.read_text().splitlines()
    surfaces: set[SurfaceKey] = set()
    center: tuple[float, float] | None = None
    line_idx = 0
    while line_idx < len(lines):
        line = lines[line_idx].strip()
        if line == "* surface center":
            center = tuple(map(float, lines[line_idx + 1].split()))
            line_idx += 2
            continue
        if line.startswith("* surface ") and "data" in line:
            if center is None:
                raise ValueError(f"Encountered surface data before a center in {path}.")
            values = list(map(float, lines[line_idx + 1].split()[:5]))
            radius, x_left, y_left, x_right, y_right = values
            surfaces.add(
                (
                    round(center[0], ROUND_DIGITS),
                    round(center[1], ROUND_DIGITS),
                    round(radius, ROUND_DIGITS),
                    round(x_left, ROUND_DIGITS),
                    round(y_left, ROUND_DIGITS),
                    round(x_right, ROUND_DIGITS),
                    round(y_right, ROUND_DIGITS),
                )
            )
            line_idx += 2
            continue
        line_idx += 1
    return surfaces


def _surface_key(surface) -> SurfaceKey:
    return (
        round(surface.xc, ROUND_DIGITS),
        round(surface.yc, ROUND_DIGITS),
        round(surface.r, ROUND_DIGITS),
        round(surface.x_left, ROUND_DIGITS),
        round(surface.y_left, ROUND_DIGITS),
        round(surface.x_right, ROUND_DIGITS),
        round(surface.y_right, ROUND_DIGITS),
    )


def _surface_key_to_dict(surface: SurfaceKey) -> dict[str, float]:
    return {
        "xc": surface[0],
        "yc": surface[1],
        "r": surface[2],
        "x_left": surface[3],
        "y_left": surface[4],
        "x_right": surface[5],
        "y_right": surface[6],
    }


def _surface_from_key(surface: SurfaceKey) -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=surface[0],
        yc=surface[1],
        r=surface[2],
        x_left=surface[3],
        y_left=surface[4],
        x_right=surface[5],
        y_right=surface[6],
    )


def _reverse_curvature_count(surfaces: set[SurfaceKey]) -> int:
    return sum(1 for surface in surfaces if _surface_has_reverse_curvature(_surface_from_key(surface)))


def _enumerate_ours(scenario: Scenario) -> tuple[set[SurfaceKey], dict[SurfaceKey, dict[str, object]]]:
    retained_path = _build_retained_path(
        scenario.profile,
        scenario.search_x_min,
        scenario.search_x_max,
    )
    _, midpoints = _division_boundaries_and_midpoints_for_retained_path(
        retained_path,
        scenario.divisions_along_slope,
    )

    surfaces: set[SurfaceKey] = set()
    metadata: dict[SurfaceKey, dict[str, object]] = {}
    for left_idx in range(scenario.divisions_along_slope):
        for right_idx in range(left_idx + 1, scenario.divisions_along_slope):
            pair_candidates = _generate_pre_polish_pair_candidates(
                profile=scenario.profile,
                search_x_min=scenario.search_x_min,
                search_x_max=scenario.search_x_max,
                p_left=midpoints[left_idx],
                p_right=midpoints[right_idx],
                circles_per_division=scenario.circles_per_division,
                model_boundary_floor_y=scenario.model_boundary_floor_y,
            )
            for beta_idx, surface in enumerate(pair_candidates, start=1):
                if surface is None:
                    continue
                key = _surface_key(surface)
                surfaces.add(key)
                metadata[key] = {
                    "pair": [left_idx, right_idx],
                    "beta_index": beta_idx,
                    "left_construction_point": [
                        round(midpoints[left_idx][0], ROUND_DIGITS),
                        round(midpoints[left_idx][1], ROUND_DIGITS),
                    ],
                    "right_construction_point": [
                        round(midpoints[right_idx][0], ROUND_DIGITS),
                        round(midpoints[right_idx][1], ROUND_DIGITS),
                    ],
                    "entry_exit_delta_y": round(abs(surface.y_right - surface.y_left), ROUND_DIGITS),
                    "reverse_curvature": _surface_has_reverse_curvature(surface),
                    "left_point_location": (
                        "toe"
                        if abs(midpoints[left_idx][1] - scenario.profile.y_toe) <= 1e-9
                        else "slope"
                    ),
                }
    return surfaces, metadata


def _summarize_scenario(scenario: Scenario) -> dict[str, object]:
    slide2_surfaces = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
    our_surfaces, our_metadata = _enumerate_ours(scenario)

    shared = slide2_surfaces & our_surfaces
    slide2_only = sorted(slide2_surfaces - our_surfaces)
    ours_only = sorted(our_surfaces - slide2_surfaces)

    beta_counter = Counter(str(our_metadata[surface]["beta_index"]) for surface in ours_only)
    left_location_counter = Counter(
        str(our_metadata[surface]["left_point_location"]) for surface in ours_only
    )
    small_delta_count = sum(
        1
        for surface in ours_only
        if float(our_metadata[surface]["entry_exit_delta_y"]) < 0.25
    )

    slide2_only_by_circle = {surface[:3] for surface in slide2_only}
    ours_only_by_circle = {surface[:3] for surface in ours_only}
    common_circle_mismatch_count = len(slide2_only_by_circle & ours_only_by_circle)
    slide2_reverse_curvature_count = _reverse_curvature_count(slide2_surfaces)
    ours_reverse_curvature_count = _reverse_curvature_count(our_surfaces)
    shared_reverse_curvature_count = _reverse_curvature_count(shared)
    slide2_only_reverse_curvature_count = _reverse_curvature_count(set(slide2_only))
    ours_only_reverse_curvature_count = _reverse_curvature_count(set(ours_only))

    return {
        "name": scenario.name,
        "s01": scenario.s01_relpath,
        "slide2_count": len(slide2_surfaces),
        "ours_count": len(our_surfaces),
        "shared_count": len(shared),
        "slide2_only_count": len(slide2_only),
        "ours_only_count": len(ours_only),
        "exact_parity": not slide2_only and not ours_only,
        "slide2_only_examples": [_surface_key_to_dict(surface) for surface in slide2_only[:10]],
        "ours_only_examples": [
            {
                **_surface_key_to_dict(surface),
                **our_metadata[surface],
            }
            for surface in ours_only[:10]
        ],
        "ours_only_beta_index_counts": dict(sorted(beta_counter.items(), key=lambda item: int(item[0]))),
        "ours_only_left_point_location_counts": dict(sorted(left_location_counter.items())),
        "ours_only_small_entry_exit_delta_count": small_delta_count,
        "common_circle_mismatch_count": common_circle_mismatch_count,
        "slide2_reverse_curvature_count": slide2_reverse_curvature_count,
        "ours_reverse_curvature_count": ours_reverse_curvature_count,
        "shared_reverse_curvature_count": shared_reverse_curvature_count,
        "slide2_only_reverse_curvature_count": slide2_only_reverse_curvature_count,
        "ours_only_reverse_curvature_count": ours_only_reverse_curvature_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare current auto-refine iteration-1 candidate generation against Slide2 .s01 files."
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "benchmarks" / "auto_refine_slide2_iteration1_candidate_generation_current.json"),
        help="Path to write the JSON summary.",
    )
    args = parser.parse_args()

    summaries = [_summarize_scenario(scenario) for scenario in SCENARIOS]
    output = {
        "round_digits": ROUND_DIGITS,
        "reverse_curvature_note": (
            "Counted as reverse curvature only when the stored endpoints or sampled lower-arc ordinates rise "
            "above the circle center. Slide2 auto-refine documentation says these surfaces are not possible "
            "for auto-refine because of the way the circles are generated."
        ),
        "scenarios": summaries,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")

    for summary in summaries:
        print(
            f"{summary['name']}: "
            f"shared={summary['shared_count']} "
            f"slide2_only={summary['slide2_only_count']} "
            f"ours_only={summary['ours_only_count']} "
            f"reverse_curvature(ours={summary['ours_reverse_curvature_count']}, "
            f"slide2={summary['slide2_reverse_curvature_count']})"
        )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
