from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from scripts.diagnostics.capture_slide2_auto_refine_iteration_ladders import capture_rows


REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_BASELINE_PATH = REPO_ROOT / "docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json"
RETAINED_PATH_BASELINE_PATH = REPO_ROOT / "docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json"


def _group_rows(rows: list[dict[str, object]]) -> dict[tuple[str, str], list[dict[str, object]]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["case_id"]), str(row["method"]))].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda item: int(item["iteration_count"]))
    return grouped


def _surface_signature(row: dict[str, object]) -> tuple[float, float, float]:
    observed = row["observed"]
    assert isinstance(observed, dict)
    before_stage = observed["before_post_polish"]
    assert isinstance(before_stage, dict)
    surface = before_stage["surface"]
    assert isinstance(surface, dict)
    return (
        round(float(surface["x_left"]), 9),
        round(float(surface["x_right"]), 9),
        round(float(surface["r"]), 9),
    )


def _mean_before_ladder_error(rows: list[dict[str, object]]) -> float:
    total = 0.0
    for row in rows:
        deltas = row["deltas"]
        assert isinstance(deltas, dict)
        before_stage = deltas["before_post_polish"]
        assert isinstance(before_stage, dict)
        total += float(before_stage["ladder_error"])
    return total / len(rows)


class AutoRefineSlide2IterationLadderPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.current_baseline = json.loads(CURRENT_BASELINE_PATH.read_text(encoding="utf-8"))
        cls.retained_path_baseline = json.loads(RETAINED_PATH_BASELINE_PATH.read_text(encoding="utf-8"))
        cls.live_rows = capture_rows()
        cls.current_grouped = _group_rows(cls.current_baseline["rows"])
        cls.live_grouped = _group_rows(cls.live_rows)

    def test_iteration_ladder_artifacts_cover_all_case_method_rows(self) -> None:
        self.assertEqual(len(self.current_baseline["rows"]), 16)
        self.assertEqual(len(self.retained_path_baseline["rows"]), 16)
        self.assertEqual(set(self.current_grouped), set(self.live_grouped))
        self.assertEqual(
            set(self.current_grouped),
            {
                ("Case2_Search", "bishop_simplified"),
                ("Case2_Search", "spencer"),
                ("Case4", "bishop_simplified"),
                ("Case4", "spencer"),
            },
        )

    @unittest.expectedFailure
    def test_before_post_polish_ladder_no_longer_freezes_when_slide2_changes(self) -> None:
        for key, rows in self.live_grouped.items():
            with self.subTest(case=key[0], method=key[1]):
                self.assertGreater(len({_surface_signature(row) for row in rows}), 1)

    @unittest.expectedFailure
    def test_before_post_polish_mean_ladder_error_improves_by_twenty_five_percent(self) -> None:
        for key, current_rows in self.current_grouped.items():
            with self.subTest(case=key[0], method=key[1]):
                live_rows = self.live_grouped[key]
                baseline_error = _mean_before_ladder_error(current_rows)
                live_error = _mean_before_ladder_error(live_rows)
                improvement = (baseline_error - live_error) / baseline_error
                self.assertGreaterEqual(improvement, 0.25)


if __name__ == "__main__":
    unittest.main()
