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

    def test_cli_analyze_closed_stdout_pipe_exits_cleanly(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "src")
        input_path = root / "tests" / "fixtures" / "case1.json"

        proc = subprocess.Popen(
            [sys.executable, "-m", "slope_stab.cli", "analyze", "--input", str(input_path), "--compact"],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIsNotNone(proc.stdout)
        self.assertIsNotNone(proc.stderr)

        proc.stdout.close()
        stderr_text = proc.stderr.read()
        proc.stderr.close()
        returncode = proc.wait()

        self.assertEqual(returncode, 0, msg=stderr_text)
        self.assertNotIn("Exception ignored while flushing sys.stdout", stderr_text)
        self.assertNotIn("BrokenPipeError", stderr_text)


if __name__ == "__main__":
    unittest.main()
