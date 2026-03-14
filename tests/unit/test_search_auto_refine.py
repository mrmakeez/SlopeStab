from __future__ import annotations

import math
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.exceptions import InputValidationError
from slope_stab.io.json_io import parse_project_input


def _base_payload() -> dict:
    return {
        "units": "metric",
        "geometry": {"h": 10.0, "l": 20.0, "x_toe": 30.0, "y_toe": 25.0},
        "material": {"gamma": 20.0, "c": 3.0, "phi_deg": 19.6},
        "analysis": {
            "method": "bishop_simplified",
            "n_slices": 25,
            "tolerance": 0.0001,
            "max_iter": 100,
            "f_init": 1.0,
        },
    }


class SearchInputParsingTests(unittest.TestCase):
    def test_search_limits_default_from_geometry(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        limits = project.search.auto_refine_circular.search_limits
        self.assertAlmostEqual(limits.x_min, 20.0)
        self.assertAlmostEqual(limits.x_max, 70.0)

    def test_parse_rejects_missing_mode(self) -> None:
        payload = _base_payload()
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_both_modes(self) -> None:
        payload = _base_payload()
        payload["prescribed_surface"] = {
            "xc": 29.07,
            "yc": 55.495,
            "r": 30.4956368485163,
            "x_left": 30.02888427029,
            "y_left": 25.014442135145,
            "x_right": 51.6518254752929,
            "y_right": 35.0,
        }
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_direct_global_mode(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "direct_global_circular": {
                "max_iterations": 40,
                "max_evaluations": 500,
                "min_improvement": 1e-4,
                "stall_iterations": 8,
                "min_rectangle_half_size": 1e-3,
            },
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "direct_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNotNone(project.search.direct_global_circular)
        self.assertEqual(project.search.direct_global_circular.max_iterations, 40)
        self.assertEqual(project.search.direct_global_circular.max_evaluations, 500)
        self.assertEqual(project.search.direct_global_circular.stall_iterations, 8)
        limits = project.search.direct_global_circular.search_limits
        self.assertAlmostEqual(limits.x_min, 20.0)
        self.assertAlmostEqual(limits.x_max, 70.0)

    def test_parse_rejects_missing_direct_global_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }

        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_direct_global_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "direct_global_circular": {
                "max_iterations": 0,
                "max_evaluations": 100,
                "min_improvement": -1e-4,
                "stall_iterations": 0,
                "min_rectangle_half_size": 0.0,
            },
        }

        with self.assertRaises(InputValidationError):
            parse_project_input(payload)


class AutoRefineSearchTests(unittest.TestCase):
    def test_generated_surfaces_per_iteration_matches_formula(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 3,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        result = run_analysis(project)

        search_meta = result.metadata["search"]
        diagnostics = search_meta["iteration_diagnostics"]
        expected_generated = 3 * 6 * (6 - 1) // 2

        self.assertEqual(len(diagnostics), 3)
        for item in diagnostics:
            self.assertEqual(item["generated_surfaces"], expected_generated)

    def test_auto_refine_repeatable_for_same_input(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)

        result1 = run_analysis(project)
        result2 = run_analysis(project)

        self.assertAlmostEqual(result1.fos, result2.fos, places=12)
        self.assertEqual(result1.metadata["prescribed_surface"], result2.metadata["prescribed_surface"])
        self.assertEqual(result1.metadata["search"]["iteration_diagnostics"], result2.metadata["search"]["iteration_diagnostics"])
        self.assertTrue(math.isfinite(result1.fos))


if __name__ == "__main__":
    unittest.main()
