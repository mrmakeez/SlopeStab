from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.verification.runner import run_verification_suite


class VerificationIntegrationTests(unittest.TestCase):
    def test_built_in_cases_pass(self) -> None:
        outcomes = run_verification_suite()
        self.assertEqual(len(outcomes), 2)
        for outcome in outcomes:
            self.assertTrue(outcome.passed, msg=f"{outcome.name} failed verification")


if __name__ == "__main__":
    unittest.main()
