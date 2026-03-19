from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.verification.cases import PrescribedVerificationCase, VERIFICATION_CASES


class SpencerPrescribedBenchmarkRegressionTests(unittest.TestCase):
    def test_case2_case3_case4_prescribed_spencer_benchmarks(self) -> None:
        target_names = {
            "Case 2 (Spencer Prescribed Benchmark)",
            "Case 3 (Spencer Prescribed Benchmark)",
            "Case 4 (Spencer Prescribed Benchmark)",
        }
        selected = [
            case
            for case in VERIFICATION_CASES
            if isinstance(case, PrescribedVerificationCase)
            and case.analysis_method == "spencer"
            and case.name in target_names
        ]
        self.assertEqual(len(selected), 3)

        for case in selected:
            with self.subTest(case=case.name):
                result = run_analysis(case.project)
                self.assertTrue(result.converged)
                self.assertLessEqual(abs(result.fos - case.expected_fos), case.fos_tolerance)
                self.assertIn("spencer", result.metadata)


if __name__ == "__main__":
    unittest.main()
