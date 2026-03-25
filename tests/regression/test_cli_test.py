from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest


def _fixture_directory() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "cli_test_targets"


def _run_cli_test(*args: str) -> subprocess.CompletedProcess[str]:
    root = pathlib.Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.run(
        [sys.executable, "-m", "slope_stab.cli", "test", *args],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class CliTestRegressionTests(unittest.TestCase):
    def test_cli_test_parallel_default_contract(self) -> None:
        fixtures = _fixture_directory()
        proc = _run_cli_test(
            "--start-directory",
            str(fixtures),
            "--top-level-directory",
            str(fixtures),
            "--pattern",
            "sample_pass_*.py",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["all_passed"])
        self.assertEqual([item["target"] for item in payload["targets"]], ["sample_pass_alpha", "sample_pass_beta"])

        execution = payload["execution"]
        self.assertEqual(execution["requested_mode"], "auto_parallel")
        self.assertGreaterEqual(execution["requested_workers"], 1)
        self.assertLessEqual(execution["requested_workers"], 4)
        self.assertIn(
            execution["decision_reason"],
            {
                "workers_le_one_serial",
                "process_backend_parallel",
                "thread_backend_default_serial",
            },
        )
        if execution["backend"] == "process":
            self.assertEqual(execution["resolved_mode"], "parallel")
            self.assertGreater(execution["resolved_workers"], 1)
        else:
            self.assertIn(execution["backend"], {"thread", "serial"})
            self.assertEqual(execution["resolved_mode"], "serial")
            self.assertEqual(execution["resolved_workers"], 1)

    def test_cli_test_serial_flag_contract(self) -> None:
        fixtures = _fixture_directory()
        proc = _run_cli_test(
            "--serial",
            "--start-directory",
            str(fixtures),
            "--top-level-directory",
            str(fixtures),
            "--pattern",
            "sample_pass_*.py",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["all_passed"])
        execution = payload["execution"]
        self.assertEqual(execution["requested_mode"], "serial")
        self.assertEqual(execution["resolved_mode"], "serial")
        self.assertEqual(execution["backend"], "serial")
        self.assertEqual(execution["decision_reason"], "forced_serial_mode")
        self.assertEqual(execution["requested_workers"], 1)
        self.assertEqual(execution["resolved_workers"], 1)

    def test_cli_test_failure_exit_code(self) -> None:
        fixtures = _fixture_directory()
        proc = _run_cli_test(
            "--serial",
            "--start-directory",
            str(fixtures),
            "--top-level-directory",
            str(fixtures),
            "--pattern",
            "sample_fail_*.py",
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["all_passed"])
        self.assertEqual(len(payload["targets"]), 1)
        self.assertFalse(payload["targets"][0]["passed"])
        self.assertNotEqual(payload["targets"][0]["returncode"], 0)

    def test_cli_test_no_targets_discovered_fails(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        proc = _run_cli_test(
            "--serial",
            "--start-directory",
            str(root / "tests"),
            "--top-level-directory",
            str(root),
            "--pattern",
            "definitely_no_tests_*.py",
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["all_passed"])
        self.assertEqual(payload["targets"], [])
        self.assertEqual(payload["discovery"]["error"], "no_test_targets_discovered")
        self.assertEqual(payload["execution"]["decision_reason"], "no_test_targets_discovered")


if __name__ == "__main__":
    unittest.main()
