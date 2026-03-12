from __future__ import annotations

import json
import math
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.io.json_io import load_project_input
from slope_stab.search.auto_refine import (
    build_pair_indices,
    build_search_domain,
    build_surface_from_endpoints_and_radius,
    is_surface_below_ground,
)
from slope_stab.surfaces.circular import CircularSlipSurface


class AutoRefineUnitTests(unittest.TestCase):
    def test_domain_defaults_use_1h_toe_and_2h_crest(self) -> None:
        profile = UniformSlopeProfile(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0)
        project = load_project_input("tests/fixtures/auto_refine_defaults_case2.json")
        self.assertIsNotNone(project.auto_refine)
        x_min, x_max = build_search_domain(profile, project.auto_refine)
        self.assertAlmostEqual(x_min, 20.0)
        self.assertAlmostEqual(x_max, 70.0)

    def test_pair_count_for_20_divisions(self) -> None:
        pairs = build_pair_indices(20)
        self.assertEqual(len(pairs), 190)

    def test_circle_builder_uses_upper_center_branch(self) -> None:
        x_left, y_left = 10.0, 10.0
        x_right, y_right = 27.5, 17.5
        chord = math.hypot(x_right - x_left, y_right - y_left)
        r_min = 0.5 * chord * (1.0 + 1e-6)
        r = 1.2 * r_min

        surface = build_surface_from_endpoints_and_radius(x_left, y_left, x_right, y_right, r)
        self.assertIsNotNone(surface)
        assert surface is not None
        self.assertGreater(surface.yc, max(y_left, y_right))
        self.assertAlmostEqual((x_left - surface.xc) ** 2 + (y_left - surface.yc) ** 2, r**2, places=5)
        self.assertAlmostEqual((x_right - surface.xc) ** 2 + (y_right - surface.yc) ** 2, r**2, places=5)

    def test_invalid_surface_rejected_when_above_ground(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        surface = CircularSlipSurface(xc=20.0, yc=20.0, r=1.0)
        self.assertFalse(is_surface_below_ground(profile, surface, 19.0, 21.0, n_slices=7))

    def test_deterministic_result_with_fixed_seed(self) -> None:
        project = load_project_input("tests/fixtures/auto_refine_case2.json")
        r1 = run_analysis(project, top_n=5)
        r2 = run_analysis(project, top_n=5)
        self.assertAlmostEqual(r1.fos, r2.fos, places=12)
        self.assertIsNotNone(r1.search)
        self.assertIsNotNone(r2.search)
        assert r1.search is not None and r2.search is not None
        self.assertEqual(r1.search["best_surface"], r2.search["best_surface"])


if __name__ == "__main__":
    unittest.main()
