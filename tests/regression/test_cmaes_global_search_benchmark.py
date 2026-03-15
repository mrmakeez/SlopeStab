from __future__ import annotations

import math
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input


BENCHMARK_FOS = {
    "case2_cmaes_global.json": 2.11283,
    "case3_cmaes_global.json": 0.986442,
    "case4_cmaes_global.json": 1.234670,
}
MARGIN = 0.01


def _assert_valid_result(testcase: unittest.TestCase, result) -> None:
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
    testcase.assertEqual(search_meta.get("method"), "cmaes_global_circular")
    testcase.assertIn("cmaes_global_circular", search_meta)
    testcase.assertIn("total_evaluations", search_meta)
    testcase.assertIn("valid_evaluations", search_meta)
    testcase.assertIn("infeasible_evaluations", search_meta)
    testcase.assertIn("termination_reason", search_meta)
    testcase.assertIn("iteration_diagnostics", search_meta)
    testcase.assertGreater(search_meta["total_evaluations"], 0)
    testcase.assertGreaterEqual(search_meta["valid_evaluations"], 1)
    testcase.assertGreaterEqual(search_meta["infeasible_evaluations"], 0)
    testcase.assertIsInstance(search_meta["iteration_diagnostics"], list)
    testcase.assertTrue(search_meta["iteration_diagnostics"])


class CmaesGlobalSearchBenchmarkRegressionTests(unittest.TestCase):
    def test_case2_case3_case4_within_benchmark_margin_and_repeatable_per_seed(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]

        for fixture_name, benchmark in BENCHMARK_FOS.items():
            with self.subTest(fixture=fixture_name):
                project = load_project_input(root / "tests" / "fixtures" / fixture_name)
                result1 = run_analysis(project)
                result2 = run_analysis(project)

                _assert_valid_result(self, result1)
                _assert_valid_result(self, result2)

                self.assertLessEqual(abs(result1.fos - result2.fos), 1e-4)
                surf1 = result1.metadata["prescribed_surface"]
                surf2 = result2.metadata["prescribed_surface"]
                for key in ("x_left", "y_left", "x_right", "y_right"):
                    self.assertLessEqual(abs(float(surf1[key]) - float(surf2[key])), 0.05)

                threshold = benchmark + MARGIN
                delta = result1.fos - threshold
                self.assertLessEqual(
                    result1.fos,
                    threshold,
                    msg=(
                        f"{fixture_name}: fos={result1.fos:.12f}, benchmark={benchmark:.12f}, "
                        f"margin={MARGIN:.6f}, threshold={threshold:.12f}, delta={delta:.12f}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
