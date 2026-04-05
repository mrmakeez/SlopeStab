from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.search.auto_refine import (
    _build_retained_path,
    _division_boundaries_and_midpoints_for_retained_path,
    _generate_pre_polish_pair_candidates,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUND_DIGITS = 12
SurfaceKey = tuple[float, float, float, float, float, float, float]


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


def _surface_key(surface) -> SurfaceKey:
    return (
        round(surface.xc, 6),
        round(surface.yc, 6),
        round(surface.r, 6),
        round(surface.x_left, 6),
        round(surface.y_left, 6),
        round(surface.x_right, 6),
        round(surface.y_right, 6),
    )


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
            radius, x_left, y_left, x_right, y_right = map(float, lines[line_idx + 1].split()[:5])
            surfaces.add(
                (
                    round(center[0], 6),
                    round(center[1], 6),
                    round(radius, 6),
                    round(x_left, 6),
                    round(y_left, 6),
                    round(x_right, 6),
                    round(y_right, 6),
                )
            )
            line_idx += 2
            continue
        line_idx += 1
    return surfaces


def _enumerate_ours(scenario: Scenario) -> dict[SurfaceKey, object]:
    retained_path = _build_retained_path(
        scenario.profile,
        scenario.search_x_min,
        scenario.search_x_max,
    )
    _, midpoints = _division_boundaries_and_midpoints_for_retained_path(
        retained_path,
        scenario.divisions_along_slope,
    )

    surfaces: dict[SurfaceKey, object] = {}
    for left_idx in range(scenario.divisions_along_slope):
        for right_idx in range(left_idx + 1, scenario.divisions_along_slope):
            candidates = _generate_pre_polish_pair_candidates(
                profile=scenario.profile,
                search_x_min=scenario.search_x_min,
                search_x_max=scenario.search_x_max,
                p_left=midpoints[left_idx],
                p_right=midpoints[right_idx],
                circles_per_division=scenario.circles_per_division,
                model_boundary_floor_y=scenario.model_boundary_floor_y,
            )
            for surface in candidates:
                if surface is None:
                    continue
                surfaces[_surface_key(surface)] = surface
    return surfaces


def _format_defined_surface_block(surfaces: list[object]) -> str:
    lines = ["centers:"]
    for idx, surface in enumerate(surfaces, start=1):
        lines.append(
            "  "
            f"{idx} x: {surface.xc:.{ROUND_DIGITS}f} "
            f"y: {surface.yc:.{ROUND_DIGITS}f} "
            f"r: {surface.r:.{ROUND_DIGITS}f} "
            f"unique_id: {{{str(uuid4()).upper()}}}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Slide2 defined-surface center blocks for our iteration-1 ours-only circles."
    )
    parser.add_argument(
        "--scenario",
        choices=[scenario.name for scenario in SCENARIOS],
        default="Case4_Iter1_Simple",
        help="Scenario to export.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to tmp/slide2_defined_surface_blocks/<scenario>_ours_only_centers.txt",
    )
    args = parser.parse_args()

    scenario = next(item for item in SCENARIOS if item.name == args.scenario)
    slide2_surfaces = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
    our_surfaces = _enumerate_ours(scenario)
    ours_only = [our_surfaces[key] for key in sorted(set(our_surfaces) - slide2_surfaces)]
    block = _format_defined_surface_block(ours_only)

    output_path = (
        Path(args.output)
        if args.output is not None
        else REPO_ROOT / "tmp" / "slide2_defined_surface_blocks" / f"{scenario.name.lower()}_ours_only_centers.txt"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(block)

    print(f"{scenario.name}: exported {len(ours_only)} ours-only circles to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
