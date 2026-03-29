from __future__ import annotations

import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input
from tests.regression.global_search_benchmark_helpers import assert_global_search_result_shape


BENCHMARK_FOS = {
    # Slide2 Case2_Search (bishop simplified) global minimum.
    "case2_cuckoo_global.json": 2.10296,
    "case3_cuckoo_global.json": 0.986442,
    "case4_cuckoo_global.json": 1.234670,
}
MARGIN = 0.01


class CuckooGlobalSearchBenchmarkRegressionTests(unittest.TestCase):
    def test_case2_case3_case4_within_benchmark_margin_and_repeatable_per_seed(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]

        for fixture_name, benchmark in BENCHMARK_FOS.items():
            with self.subTest(fixture=fixture_name):
                project = load_project_input(root / "tests" / "fixtures" / fixture_name)
                result1 = run_analysis(project)
                result2 = run_analysis(project)

                assert_global_search_result_shape(self, result1, "cuckoo_global_circular", "cuckoo_global_circular")
                assert_global_search_result_shape(self, result2, "cuckoo_global_circular", "cuckoo_global_circular")

                self.assertAlmostEqual(result1.fos, result2.fos, places=12)
                self.assertEqual(result1.metadata["prescribed_surface"], result2.metadata["prescribed_surface"])
                self.assertEqual(result1.metadata["search"]["iteration_diagnostics"], result2.metadata["search"]["iteration_diagnostics"])

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
