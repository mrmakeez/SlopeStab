from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest


class CliRegressionTests(unittest.TestCase):
    def test_verify_command(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "src")
        proc = subprocess.run(
            [sys.executable, "-m", "slope_stab.cli", "verify"],
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["all_passed"])
        self.assertEqual(len(payload["cases"]), 27)
        self.assertIn("execution", payload)

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

        cases = {item["name"]: item for item in payload["cases"]}
        self.assertIn("Case 1", cases)
        self.assertIn("Case 2 (Spencer Prescribed Benchmark)", cases)
        self.assertIn("Case 4 (Spencer CMAES Global Search Benchmark)", cases)

        self.assertEqual(cases["Case 1"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 2"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 3"]["case_type"], "auto_refine_parity")
        self.assertEqual(cases["Case 4"]["case_type"], "auto_refine_parity")
        self.assertEqual(cases["Case 2 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")
        self.assertEqual(cases["Case 3 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")
        self.assertEqual(cases["Case 4 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")
        self.assertEqual(cases["Case 2 (Cuckoo Global Search Benchmark)"]["case_type"], "cuckoo_global_search_benchmark")
        self.assertEqual(cases["Case 3 (Cuckoo Global Search Benchmark)"]["case_type"], "cuckoo_global_search_benchmark")
        self.assertEqual(cases["Case 4 (Cuckoo Global Search Benchmark)"]["case_type"], "cuckoo_global_search_benchmark")
        self.assertEqual(cases["Case 2 (CMAES Global Search Benchmark)"]["case_type"], "cmaes_global_search_benchmark")
        self.assertEqual(cases["Case 3 (CMAES Global Search Benchmark)"]["case_type"], "cmaes_global_search_benchmark")
        self.assertEqual(cases["Case 4 (CMAES Global Search Benchmark)"]["case_type"], "cmaes_global_search_benchmark")
        self.assertEqual(cases["Case 2 (Spencer Prescribed Benchmark)"]["analysis_method"], "spencer")
        self.assertEqual(cases["Case 4 (Spencer CMAES Global Search Benchmark)"]["analysis_method"], "spencer")

        global_check = cases["Case 2 (Global Search Benchmark)"]["hard_checks"]["fos_vs_benchmark_plus_margin"]
        self.assertIn("value", global_check)
        self.assertIn("threshold", global_check)
        self.assertIn("benchmark", global_check)
        self.assertIn("margin", global_check)
        self.assertIn("passed", global_check)

        for item in payload["cases"]:
            self.assertIn("solver", item)
            self.assertIn("hard_checks", item)
            self.assertIn("diagnostics", item)
            self.assertIn("analysis_method", item)

    def test_verify_serial_workers_conflict(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "src")
        proc = subprocess.run(
            [sys.executable, "-m", "slope_stab.cli", "verify", "--serial", "--workers", "1"],
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not allowed", proc.stderr)


if __name__ == "__main__":
    unittest.main()
