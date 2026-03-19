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

    def test_case3_spencer_matches_expected_fos(self) -> None:
        case = self._prescribed_spencer_case("Case 3 (Spencer Prescribed Benchmark)")
        result = run_analysis(case.project)
        self.assertTrue(result.converged)
        self.assertLessEqual(abs(result.fos - case.expected_fos), case.fos_tolerance)
        self.assertIn("spencer", result.metadata)


if __name__ == "__main__":
    unittest.main()
