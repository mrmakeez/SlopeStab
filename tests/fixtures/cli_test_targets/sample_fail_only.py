from __future__ import annotations

import unittest


class SampleFailOnlyTests(unittest.TestCase):
    def test_failure(self) -> None:
        self.assertEqual(1, 2)


if __name__ == "__main__":
    unittest.main()
