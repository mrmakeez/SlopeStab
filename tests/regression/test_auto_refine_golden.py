from __future__ import annotations

import json
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input


class AutoRefineRegressionTests(unittest.TestCase):
    def _assert_case_matches_golden(self, case_name: str) -> None:
        project = load_project_input(f"tests/fixtures/auto_refine_{case_name}.json")
        result = run_analysis(project, top_n=5)

        with open(f"tests/fixtures/golden_auto_refine_{case_name}.json", "r", encoding="utf-8") as f:
            golden = json.load(f)

        self.assertAlmostEqual(result.fos, golden["fos"], places=12)
        self.assertAlmostEqual(result.driving_moment, golden["driving_moment"], places=9)
        self.assertAlmostEqual(result.resisting_moment, golden["resisting_moment"], places=9)

        self.assertIsNotNone(result.search)
        assert result.search is not None

        self.assertEqual(result.search["total_surfaces_generated"], golden["search"]["total_surfaces_generated"])
        self.assertEqual(result.search["total_valid_surfaces"], golden["search"]["total_valid_surfaces"])
        self.assertEqual(result.search["best_surface"], golden["search"]["best_surface"])
        self.assertEqual(result.search["iteration_summaries"], golden["search"]["iteration_summaries"])

    def test_case1_golden(self) -> None:
        self._assert_case_matches_golden("case1")

    def test_case2_golden(self) -> None:
        self._assert_case_matches_golden("case2")


if __name__ == "__main__":
    unittest.main()
