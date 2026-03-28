from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.verification.cases import PrescribedVerificationCase, VERIFICATION_CASES


class SpencerSolverTests(unittest.TestCase):
    def _prescribed_spencer_case(self, name: str) -> PrescribedVerificationCase:
        for case in VERIFICATION_CASES:
            if isinstance(case, PrescribedVerificationCase) and case.name == name:
                return case
        raise AssertionError(f"Verification case not found: {name}")

    def test_case2_spencer_matches_expected_fos(self) -> None:
        case = self._prescribed_spencer_case("Case 2 (Spencer Prescribed Benchmark)")
        result = run_analysis(case.project)
        self.assertTrue(result.converged)
        self.assertLessEqual(abs(result.fos - case.expected_fos), case.fos_tolerance)
        self.assertIn("spencer", result.metadata)
        self.assertEqual(result.metadata["spencer"].get("solve_path"), "two_dimensional")

    def test_case3_spencer_matches_expected_fos(self) -> None:
        case = self._prescribed_spencer_case("Case 3 (Spencer Prescribed Benchmark)")
        result = run_analysis(case.project)
        self.assertTrue(result.converged)
        self.assertLessEqual(abs(result.fos - case.expected_fos), case.fos_tolerance)
        self.assertIn("spencer", result.metadata)
        self.assertEqual(result.metadata["spencer"].get("solve_path"), "two_dimensional")

    def test_case7_spencer_uses_lambda_zero_fallback_path(self) -> None:
        case = self._prescribed_spencer_case("Case 7 (Spencer Ponded Water Hu=Auto Benchmark)")
        result = run_analysis(case.project)
        self.assertTrue(result.converged)
        self.assertLessEqual(abs(result.fos - case.expected_fos), case.fos_tolerance)
        spencer_meta = result.metadata.get("spencer", {})
        self.assertEqual(spencer_meta.get("solve_path"), "lambda_zero_fallback")
        lambda_zero_meta = spencer_meta.get("lambda_zero", {})
        self.assertTrue(lambda_zero_meta.get("attempted"))
        self.assertTrue(lambda_zero_meta.get("accepted"))


if __name__ == "__main__":
    unittest.main()
