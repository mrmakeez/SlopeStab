from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import PrescribedCircleInput
from slope_stab.search.auto_refine import (
    _build_retained_path,
    _division_boundaries_and_midpoints_for_retained_path,
    _generate_pre_polish_pair_candidates,
    _surface_has_reverse_curvature,
)


ROUND_DIGITS = 6
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Iteration1Scenario:
    name: str
    profile: UniformSlopeProfile
    search_x_min: float
    search_x_max: float
    divisions_along_slope: int
    circles_per_division: int
    model_boundary_floor_y: float
    s01_relpath: str


SCENARIOS: tuple[Iteration1Scenario, ...] = (
    Iteration1Scenario(
        name="Case2_Search_Iter_1",
        profile=UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
        search_x_min=0.0,
        search_x_max=35.0,
        divisions_along_slope=20,
        circles_per_division=10,
        model_boundary_floor_y=0.0,
        s01_relpath="Verification/Bishop/Case 2/Case2_Search_Iter_1/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01",
    ),
    Iteration1Scenario(
        name="Case4_Iter1",
        profile=UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=30,
        circles_per_division=15,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
    Iteration1Scenario(
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
            assert center is not None
            radius, x_left, y_left, x_right, y_right = map(float, lines[line_idx + 1].split()[:5])
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


def _enumerate_ours(scenario: Iteration1Scenario) -> set[SurfaceKey]:
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
                surfaces.add(
                    (
                        round(surface.xc, ROUND_DIGITS),
                        round(surface.yc, ROUND_DIGITS),
                        round(surface.r, ROUND_DIGITS),
                        round(surface.x_left, ROUND_DIGITS),
                        round(surface.y_left, ROUND_DIGITS),
                        round(surface.x_right, ROUND_DIGITS),
                        round(surface.y_right, ROUND_DIGITS),
                    )
                )
    return surfaces


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


class Slide2Iteration1CandidateCoverageTests(unittest.TestCase):
    def test_iteration1_generator_covers_every_slide2_surface(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(case=scenario.name):
                slide2 = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
                ours = _enumerate_ours(scenario)
                self.assertEqual(slide2 - ours, set())

    def test_iteration1_surfaces_contain_no_reverse_curvature_arcs(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(case=scenario.name):
                slide2 = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
                ours = _enumerate_ours(scenario)
                ours_only = ours - slide2
                self.assertEqual(
                    sum(1 for surface in slide2 if _surface_has_reverse_curvature(_surface_from_key(surface))),
                    0,
                )
                self.assertEqual(
                    sum(1 for surface in ours if _surface_has_reverse_curvature(_surface_from_key(surface))),
                    0,
                )
                self.assertEqual(
                    sum(1 for surface in ours_only if _surface_has_reverse_curvature(_surface_from_key(surface))),
                    0,
                )

    @unittest.expectedFailure
    def test_iteration1_generator_matches_slide2_exact_surface_set(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(case=scenario.name):
                slide2 = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
                ours = _enumerate_ours(scenario)
                self.assertEqual(ours - slide2, set())
