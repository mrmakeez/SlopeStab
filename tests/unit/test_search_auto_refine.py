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
    def test_parse_accepts_spencer_method(self) -> None:
        payload = _base_payload()
        payload["analysis"]["method"] = "spencer"
        payload["prescribed_surface"] = {
            "xc": 13.689,
            "yc": 25.558,
            "r": 15.989,
            "x_left": 10.0005216402222,
            "y_left": 10.0002608201111,
            "x_right": 27.4990237870903,
            "y_right": 17.5,
        }

        project = parse_project_input(payload)
        self.assertEqual(project.analysis.method, "spencer")

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

    def test_parse_cuckoo_global_mode_defaults(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
            "cuckoo_global_circular": {},
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "cuckoo_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNone(project.search.direct_global_circular)
        self.assertIsNotNone(project.search.cuckoo_global_circular)

        cfg = project.search.cuckoo_global_circular
        self.assertEqual(cfg.population_size, 40)
        self.assertEqual(cfg.max_iterations, 200)
        self.assertEqual(cfg.max_evaluations, 4000)
        self.assertAlmostEqual(cfg.discovery_rate, 0.20)
        self.assertAlmostEqual(cfg.levy_beta, 1.5)
        self.assertAlmostEqual(cfg.alpha_max, 0.5)
        self.assertAlmostEqual(cfg.alpha_min, 0.05)
        self.assertAlmostEqual(cfg.min_improvement, 1e-4)
        self.assertEqual(cfg.stall_iterations, 25)
        self.assertEqual(cfg.seed, 0)
        self.assertTrue(cfg.post_polish)
        self.assertAlmostEqual(cfg.search_limits.x_min, 20.0)
        self.assertAlmostEqual(cfg.search_limits.x_max, 70.0)

    def test_parse_rejects_missing_cuckoo_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_cuckoo_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
            "cuckoo_global_circular": {
                "population_size": 1,
                "max_iterations": 0,
                "max_evaluations": 0,
                "discovery_rate": 1.0,
                "levy_beta": 2.1,
                "alpha_max": 0.0,
                "alpha_min": 0.0,
                "min_improvement": -1.0,
                "stall_iterations": 0,
                "seed": 0,
                "post_polish": True,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_cmaes_global_mode_defaults(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
            "cmaes_global_circular": {},
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "cmaes_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNone(project.search.direct_global_circular)
        self.assertIsNone(project.search.cuckoo_global_circular)
        self.assertIsNotNone(project.search.cmaes_global_circular)

        cfg = project.search.cmaes_global_circular
        self.assertEqual(cfg.max_evaluations, 5000)
        self.assertEqual(cfg.direct_prescan_evaluations, 300)
        self.assertEqual(cfg.cmaes_population_size, 8)
        self.assertEqual(cfg.cmaes_max_iterations, 200)
        self.assertEqual(cfg.cmaes_restarts, 2)
        self.assertAlmostEqual(cfg.cmaes_sigma0, 0.15)
        self.assertEqual(cfg.polish_max_evaluations, 80)
        self.assertAlmostEqual(cfg.min_improvement, 1e-4)
        self.assertEqual(cfg.stall_iterations, 25)
        self.assertEqual(cfg.seed, 1)
        self.assertTrue(cfg.post_polish)
        self.assertAlmostEqual(cfg.invalid_penalty, 1e6)
        self.assertAlmostEqual(cfg.nonconverged_penalty, 1e5)
        self.assertAlmostEqual(cfg.search_limits.x_min, 20.0)
        self.assertAlmostEqual(cfg.search_limits.x_max, 70.0)

    def test_parse_rejects_missing_cmaes_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_cmaes_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
            "cmaes_global_circular": {
                "max_evaluations": 10,
                "direct_prescan_evaluations": 10,
                "cmaes_population_size": 1,
                "cmaes_max_iterations": 0,
                "cmaes_restarts": -1,
                "cmaes_sigma0": 0.0,
                "polish_max_evaluations": 0,
                "min_improvement": -1.0,
                "stall_iterations": 0,
                "seed": 0,
                "post_polish": True,
                "invalid_penalty": 1e4,
                "nonconverged_penalty": 1e5
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_parallel_defaults(self) -> None:
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
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "auto")
        self.assertEqual(project.search.parallel.workers, 0)
        self.assertEqual(project.search.parallel.min_batch_size, 1)
        self.assertIsNone(project.search.parallel.timeout_seconds)

    def test_parse_parallel_custom_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "parallel",
                "workers": 2,
                "min_batch_size": 8,
                "timeout_seconds": 30.0,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "parallel")
        self.assertEqual(project.search.parallel.workers, 2)
        self.assertEqual(project.search.parallel.min_batch_size, 8)
        self.assertAlmostEqual(project.search.parallel.timeout_seconds, 30.0)

    def test_parse_rejects_invalid_parallel_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "parallel",
                "workers": -1,
                "min_batch_size": 0,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_parallel_legacy_enabled_mapping(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": True,
                "workers": 3,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "parallel")
        self.assertEqual(project.search.parallel.workers, 3)

    def test_parse_parallel_legacy_enabled_false_maps_to_serial(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": False,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "serial")
        self.assertEqual(project.search.parallel.workers, 0)

    def test_parse_rejects_parallel_enabled_mode_conflict(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": False,
                "mode": "parallel",
                "workers": 2,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_parallel_mode(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "turbo",
                "workers": 2,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
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
