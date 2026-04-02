from __future__ import annotations

import math
import unittest


def assert_global_search_result_shape(
    testcase: unittest.TestCase,
    result,
    method_name: str,
    method_key: str,
) -> None:
    testcase.assertTrue(math.isfinite(result.fos), "FOS must be finite.")
    testcase.assertGreater(result.fos, 0.0, "FOS must be positive.")
    testcase.assertTrue(result.converged, "Solver must converge.")
    testcase.assertTrue(math.isfinite(result.driving_moment), "Driving moment must be finite.")
    testcase.assertTrue(math.isfinite(result.resisting_moment), "Resisting moment must be finite.")

    surface = result.metadata.get("prescribed_surface")
    testcase.assertIsInstance(surface, dict, "Winning surface metadata is required.")
    for key in ("xc", "yc", "r", "x_left", "y_left", "x_right", "y_right"):
        testcase.assertIn(key, surface, f"Missing winning surface key: {key}")
        testcase.assertTrue(math.isfinite(float(surface[key])), f"Winning surface key '{key}' must be finite.")

    search_meta = result.metadata.get("search")
    testcase.assertIsInstance(search_meta, dict, "Search metadata is required.")
    testcase.assertEqual(search_meta.get("method"), method_name)
    testcase.assertIn(method_key, search_meta)
    testcase.assertIn("total_evaluations", search_meta)
    testcase.assertIn("valid_evaluations", search_meta)
    testcase.assertIn("infeasible_evaluations", search_meta)
    testcase.assertIn("post_refinement_total_evaluations", search_meta)
    testcase.assertIn("post_refinement_valid_evaluations", search_meta)
    testcase.assertIn("post_refinement_infeasible_evaluations", search_meta)
    testcase.assertIn("termination_reason", search_meta)
    testcase.assertIn("iteration_diagnostics", search_meta)
    testcase.assertGreater(search_meta["total_evaluations"], 0)
    testcase.assertGreaterEqual(search_meta["valid_evaluations"], 1)
    testcase.assertGreaterEqual(search_meta["infeasible_evaluations"], 0)
    testcase.assertGreaterEqual(search_meta["post_refinement_total_evaluations"], 0)
    testcase.assertGreaterEqual(search_meta["post_refinement_valid_evaluations"], 0)
    testcase.assertGreaterEqual(search_meta["post_refinement_infeasible_evaluations"], 0)
    testcase.assertEqual(
        search_meta["post_refinement_total_evaluations"],
        search_meta["post_refinement_valid_evaluations"] + search_meta["post_refinement_infeasible_evaluations"],
    )
    testcase.assertIsInstance(search_meta["iteration_diagnostics"], list)
    testcase.assertTrue(search_meta["iteration_diagnostics"])
