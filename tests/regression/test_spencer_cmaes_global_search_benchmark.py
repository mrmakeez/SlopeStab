from __future__ import annotations

import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input
from tests.regression.global_search_benchmark_helpers import assert_global_search_result_shape


BENCHMARK_FOS = {
    # Slide2 Case2_Search (spencer) global minimum.
    "case2_cmaes_global_spencer.json": 2.09717,
    "case3_cmaes_global_spencer.json": 0.985334,
    "case4_cmaes_global_spencer.json": 1.23141,
}
MARGIN = 0.01


class SpencerCmaesGlobalSearchBenchmarkRegressionTests(unittest.TestCase):
    def test_case2_case3_case4_within_benchmark_margin_and_repeatable_per_seed(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]

        for fixture_name, benchmark in BENCHMARK_FOS.items():
            with self.subTest(fixture=fixture_name):
                project = load_project_input(root / "tests" / "fixtures" / fixture_name)
                result1 = run_analysis(project)
                result2 = run_analysis(project)

                assert_global_search_result_shape(self, result1, "cmaes_global_circular", "cmaes_global_circular")
                assert_global_search_result_shape(self, result2, "cmaes_global_circular", "cmaes_global_circular")

                self.assertLessEqual(abs(result1.fos - result2.fos), 1e-4)
                surf1 = result1.metadata["prescribed_surface"]
                surf2 = result2.metadata["prescribed_surface"]
                for key in ("x_left", "y_left", "x_right", "y_right"):
                    self.assertLessEqual(abs(float(surf1[key]) - float(surf2[key])), 0.05)

                threshold = benchmark + MARGIN
                self.assertLessEqual(result1.fos, threshold)


if __name__ == "__main__":
    unittest.main()
