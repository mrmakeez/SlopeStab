from __future__ import annotations

import math
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input


class Case3AutoRefineParityTests(unittest.TestCase):
    def test_case3_auto_refine_parity(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        project = load_project_input(root / "tests" / "fixtures" / "case3_auto_refine.json")
        result = run_analysis(project)

        expected_fos = 0.986442
        expected_radius = 26.793
        expected_center = (30.259, 51.792)
        expected_left = (30.0, 25.0)
        expected_right = (51.137, 35.0)

        self.assertLessEqual(abs(result.fos - expected_fos), 0.001)

        surface = result.metadata["prescribed_surface"]
        self.assertLessEqual(abs(surface["x_left"] - expected_left[0]), 0.2)
        self.assertLessEqual(abs(surface["y_left"] - expected_left[1]), 0.2)
        self.assertLessEqual(abs(surface["x_right"] - expected_right[0]), 0.2)
        self.assertLessEqual(abs(surface["y_right"] - expected_right[1]), 0.2)

        radius_rel_error = abs(surface["r"] - expected_radius) / expected_radius
        self.assertLessEqual(radius_rel_error, 0.10)

        center_distance = math.hypot(surface["xc"] - expected_center[0], surface["yc"] - expected_center[1])
        self.assertTrue(math.isfinite(center_distance))

        search_meta = result.metadata["search"]
        self.assertIn("valid_surfaces", search_meta)
        self.assertIn("invalid_surfaces", search_meta)
        self.assertGreater(search_meta["valid_surfaces"], 0)
        self.assertGreaterEqual(search_meta["invalid_surfaces"], 0)
        self.assertTrue(search_meta["iteration_diagnostics"])


if __name__ == "__main__":
    unittest.main()
