from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.verification.runner import run_verification_suite


class VerificationIntegrationTests(unittest.TestCase):
    def test_built_in_cases_pass(self) -> None:
        outcomes = run_verification_suite()
        self.assertEqual(len(outcomes), 13)
        self.assertEqual(
            {outcome.name for outcome in outcomes},
            {
                "Case 1",
                "Case 2",
                "Case 3",
                "Case 4",
                "Case 2 (Global Search Benchmark)",
                "Case 3 (Global Search Benchmark)",
                "Case 4 (Global Search Benchmark)",
                "Case 2 (Cuckoo Global Search Benchmark)",
                "Case 3 (Cuckoo Global Search Benchmark)",
                "Case 4 (Cuckoo Global Search Benchmark)",
                "Case 2 (CMAES Global Search Benchmark)",
                "Case 3 (CMAES Global Search Benchmark)",
                "Case 4 (CMAES Global Search Benchmark)",
            },
        )
        for outcome in outcomes:
            self.assertTrue(outcome.passed, msg=f"{outcome.name} failed verification")


if __name__ == "__main__":
    unittest.main()
