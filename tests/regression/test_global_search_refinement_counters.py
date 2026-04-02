from __future__ import annotations

import json
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import parse_project_input


def _load_fixture_payload(name: str) -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    fixture_path = root / "tests" / "fixtures" / name
    with fixture_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class GlobalSearchRefinementCounterTests(unittest.TestCase):
    def test_cuckoo_post_refinement_fields_present_and_zero_when_post_polish_disabled(self) -> None:
        payload = _load_fixture_payload("case2_cuckoo_global.json")
        cfg = payload["search"]["cuckoo_global_circular"]
        cfg["population_size"] = 8
        cfg["max_iterations"] = 6
        cfg["max_evaluations"] = 80
        cfg["post_polish"] = False

        result = run_analysis(parse_project_input(payload), forced_parallel_mode="serial", forced_parallel_workers=1)
        search_meta = result.metadata["search"]
        self.assertIn("post_refinement_total_evaluations", search_meta)
        self.assertIn("post_refinement_valid_evaluations", search_meta)
        self.assertIn("post_refinement_infeasible_evaluations", search_meta)
        self.assertEqual(search_meta["post_refinement_total_evaluations"], 0)
        self.assertEqual(search_meta["post_refinement_valid_evaluations"], 0)
        self.assertEqual(search_meta["post_refinement_infeasible_evaluations"], 0)

    def test_cmaes_post_refinement_fields_present_and_zero_when_post_polish_disabled(self) -> None:
        payload = _load_fixture_payload("case2_cmaes_global.json")
        cfg = payload["search"]["cmaes_global_circular"]
        cfg["max_evaluations"] = 100
        cfg["direct_prescan_evaluations"] = 30
        cfg["cmaes_population_size"] = 8
        cfg["cmaes_max_iterations"] = 8
        cfg["cmaes_restarts"] = 0
        cfg["polish_max_evaluations"] = 20
        cfg["post_polish"] = False

        result = run_analysis(parse_project_input(payload), forced_parallel_mode="serial", forced_parallel_workers=1)
        search_meta = result.metadata["search"]
        self.assertIn("post_refinement_total_evaluations", search_meta)
        self.assertIn("post_refinement_valid_evaluations", search_meta)
        self.assertIn("post_refinement_infeasible_evaluations", search_meta)
        self.assertEqual(search_meta["post_refinement_total_evaluations"], 0)
        self.assertEqual(search_meta["post_refinement_valid_evaluations"], 0)
        self.assertEqual(search_meta["post_refinement_infeasible_evaluations"], 0)

    def test_cmaes_post_polish_objective_evaluations_are_counted_in_post_refinement(self) -> None:
        payload = _load_fixture_payload("case2_cmaes_global.json")
        cfg = payload["search"]["cmaes_global_circular"]
        cfg["max_evaluations"] = 120
        cfg["direct_prescan_evaluations"] = 30
        cfg["cmaes_population_size"] = 8
        cfg["cmaes_max_iterations"] = 10
        cfg["cmaes_restarts"] = 0
        cfg["polish_max_evaluations"] = 40
        cfg["post_polish"] = True
        # Exclude toe/crest deterministic refinement windows so non-zero
        # post-refinement accounting must come from Nelder-Mead objective calls.
        cfg["search_limits"] = {"x_min": 20.0, "x_max": 35.0}

        result = run_analysis(parse_project_input(payload), forced_parallel_mode="serial", forced_parallel_workers=1)
        search_meta = result.metadata["search"]
        self.assertIn("post_refinement_total_evaluations", search_meta)
        self.assertIn("post_refinement_valid_evaluations", search_meta)
        self.assertIn("post_refinement_infeasible_evaluations", search_meta)
        self.assertGreater(search_meta["post_refinement_total_evaluations"], 0)
        self.assertEqual(
            search_meta["post_refinement_total_evaluations"],
            search_meta["post_refinement_valid_evaluations"] + search_meta["post_refinement_infeasible_evaluations"],
        )

        polish_diagnostics = [item for item in search_meta["iteration_diagnostics"] if item.get("stage") == "polish"]
        self.assertTrue(polish_diagnostics)
        self.assertGreater(polish_diagnostics[0]["extra"].get("nfev", 0), 0)


if __name__ == "__main__":
    unittest.main()
