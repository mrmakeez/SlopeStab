from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest
def _run_analyze_from_fixture(fixture_name: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    root = pathlib.Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    input_path = root / "tests" / "fixtures" / fixture_name
    return subprocess.run(
        [sys.executable, "-m", "slope_stab.cli", "analyze", "--input", str(input_path), "--compact", *extra_args],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class CliAnalyzeParallelRegressionTests(unittest.TestCase):
    def test_cli_parallel_mode_override_takes_precedence(self) -> None:
        proc = _run_analyze_from_fixture("case3_auto_refine_parallel_config.json", "--parallel-mode", "serial")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        parsed = json.loads(proc.stdout)
        parallel_meta = parsed["metadata"]["search"]["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "serial")
        self.assertEqual(parallel_meta["resolved_mode"], "serial")
        self.assertEqual(parallel_meta["decision_reason"], "forced_serial_mode")

    def test_cli_parallel_workers_override_is_reflected_in_metadata(self) -> None:
        proc = _run_analyze_from_fixture(
            "case3_auto_refine_parallel_config.json",
            "--parallel-mode",
            "serial",
            "--parallel-workers",
            "1",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        parsed = json.loads(proc.stdout)
        parallel_meta = parsed["metadata"]["search"]["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "serial")
        self.assertEqual(parallel_meta["requested_workers"], 1)
        self.assertEqual(parallel_meta["decision_reason"], "forced_serial_mode")


if __name__ == "__main__":
    unittest.main()
