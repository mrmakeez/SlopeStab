from __future__ import annotations

import math
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input


class AutoRefineIntegrationTests(unittest.TestCase):
    def test_case1_auto_refine_completes(self) -> None:
        project = load_project_input("tests/fixtures/auto_refine_case1.json")
        result = run_analysis(project, top_n=10)
        self.assertTrue(math.isfinite(result.fos))
        self.assertIsNotNone(result.search)
        assert result.search is not None
        self.assertIn("best_surface", result.search)
        self.assertIn("iteration_summaries", result.search)
        self.assertGreater(len(result.search["iteration_summaries"]), 0)

    def test_case2_auto_refine_completes(self) -> None:
        project = load_project_input("tests/fixtures/auto_refine_case2.json")
        result = run_analysis(project, top_n=10)
        self.assertTrue(math.isfinite(result.fos))
        self.assertIsNotNone(result.search)
        assert result.search is not None
        self.assertIn("best_surface", result.search)
        self.assertIn("iteration_summaries", result.search)
        self.assertGreater(len(result.search["iteration_summaries"]), 0)


if __name__ == "__main__":
    unittest.main()
