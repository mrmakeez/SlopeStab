from __future__ import annotations

import unittest


class SamplePassBetaTests(unittest.TestCase):
    def test_beta(self) -> None:
        self.assertEqual(2 + 2, 4)


if __name__ == "__main__":
    unittest.main()
