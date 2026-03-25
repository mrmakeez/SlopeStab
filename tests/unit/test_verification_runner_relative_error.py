from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.verification.runner import _relative_error


class VerificationRunnerRelativeErrorTests(unittest.TestCase):
    def test_zero_actual_and_zero_expected_is_exact_match(self) -> None:
        self.assertEqual(_relative_error(0.0, 0.0), 0.0)

    def test_nonzero_actual_against_zero_expected_is_infinite(self) -> None:
        self.assertEqual(_relative_error(1.0, 0.0), float("inf"))


if __name__ == "__main__":
    unittest.main()
