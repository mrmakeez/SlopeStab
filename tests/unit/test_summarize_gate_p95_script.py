from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import shutil
import unittest
from uuid import uuid4


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "benchmarks" / "summarize_gate_p95.py"
    spec = importlib.util.spec_from_file_location("summarize_gate_p95", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load summarize_gate_p95 module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SummarizeGateP95ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_module()

    def test_percentile_basic(self) -> None:
        self.assertEqual(self.mod._percentile([5.0], 95.0), 5.0)
        self.assertEqual(self.mod._percentile([1.0, 3.0, 5.0], 50.0), 3.0)
        self.assertTrue(math.isnan(self.mod._percentile([], 95.0)))

    def test_summarize_stage_seconds_supports_seconds_total(self) -> None:
        manifests = [
            {"stages": {"verify": {"seconds": 10.0}}},
            {"stages": {"verify": {"seconds_total": 20.0}}},
            {"stages": {"verify": {"seconds": 30.0}}},
        ]
        summary = self.mod._summarize_stage_seconds(manifests, "verify")
        self.assertEqual(summary["count"], 3)
        self.assertAlmostEqual(summary["p50_seconds"], 20.0)
        self.assertAlmostEqual(summary["max_seconds"], 30.0)

    def test_summarize_total_seconds(self) -> None:
        manifests = [
            {"stages": {"verify": {"seconds": 10.0}, "test": {"seconds_total": 40.0}}},
            {"stages": {"verify": {"seconds_total": 20.0}, "test": {"seconds": 30.0}}},
        ]
        summary = self.mod._summarize_total_seconds(manifests)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["values_seconds"], [50.0, 50.0])
        self.assertAlmostEqual(summary["p95_seconds"], 50.0)

    def test_collect_manifest_files_sorted(self) -> None:
        tmp_root = Path(__file__).resolve().parents[2] / "tmp"
        root = tmp_root / "unit_test_scratch" / f"gate_p95_{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        try:
            for run_id in ("20260331T090000Z", "20260330T090000Z", "20260401T090000Z"):
                run_dir = root / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "manifest.json").write_text(json.dumps({"stages": {}}), encoding="utf-8")
            manifests = self.mod._collect_manifest_files(root)
            names = [path.parent.name for path in manifests]
            self.assertEqual(names, sorted(names))
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
