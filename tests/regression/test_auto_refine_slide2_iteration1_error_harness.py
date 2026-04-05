from __future__ import annotations

from collections import Counter
from pathlib import Path
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from scripts.diagnostics.compare_slide2_iteration1_error_harness import (
    REPO_ROOT,
    SCENARIOS,
    _parse_slide2_s01_records,
    _summarize_scenario,
)


EXPECTED_STATUS_COUNTS = {
    "Case2_Search_Iter_1": {
        "bishop simplified": {"valid": 1562},
        "spencer": {"valid": 1534, "error_-108": 17, "error_-111": 11},
    },
    "Case4_Iter1": {
        "bishop simplified": {"valid": 4536},
        "spencer": {"valid": 3936, "error_-108": 73, "error_-111": 527},
    },
    "Case4_Iter1_Simple": {
        "bishop simplified": {"valid": 38},
        "spencer": {"valid": 33, "error_-111": 5},
    },
}


class Slide2Iteration1ErrorHarnessTests(unittest.TestCase):
    def test_s01_parser_extracts_expected_per_method_status_counts(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(case=scenario.name):
                analysis_names, records = _parse_slide2_s01_records(REPO_ROOT / scenario.s01_relpath)
                expected = EXPECTED_STATUS_COUNTS[scenario.name]
                self.assertEqual(set(analysis_names), set(expected.keys()))

                for method_name in analysis_names:
                    counter = Counter()
                    for statuses in records.values():
                        status_value = statuses[method_name]
                        if status_value < 0:
                            counter[f"error_{int(status_value)}"] += 1
                        else:
                            counter["valid"] += 1
                    self.assertEqual(dict(sorted(counter.items())), expected[method_name])

    def test_iteration1_s01_files_store_only_subset_of_theoretical_slots(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(case=scenario.name):
                _, records = _parse_slide2_s01_records(REPO_ROOT / scenario.s01_relpath)
                self.assertLess(len(records), scenario.theoretical_slot_count)

    def test_simple_case_status_harness_smoke(self) -> None:
        scenario = next(item for item in SCENARIOS if item.name == "Case4_Iter1_Simple")
        summary = _summarize_scenario(scenario)

        self.assertEqual(summary["slide2_stored_geometry_count"], 38)
        self.assertEqual(summary["slide2_unstored_slot_gap"], 12)
        self.assertEqual(summary["analysis_names"], ["bishop simplified", "spencer"])
        self.assertIn("stored_status_counts", summary["slide2_per_method"]["spencer"])
        self.assertIn("shared_geometry_alignment", summary["ours_per_method"]["spencer"])

