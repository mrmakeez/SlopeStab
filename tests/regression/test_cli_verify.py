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
        self.assertEqual(len(payload["cases"]), 7)

        cases = {item["name"]: item for item in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "Case 1",
                "Case 2",
                "Case 3",
                "Case 4",
                "Case 2 (Global Search Benchmark)",
                "Case 3 (Global Search Benchmark)",
                "Case 4 (Global Search Benchmark)",
            },
        )

        self.assertEqual(cases["Case 1"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 2"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 3"]["case_type"], "auto_refine_parity")
        self.assertEqual(cases["Case 4"]["case_type"], "auto_refine_parity")
        self.assertEqual(cases["Case 2 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")
        self.assertEqual(cases["Case 3 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")
        self.assertEqual(cases["Case 4 (Global Search Benchmark)"]["case_type"], "global_search_benchmark")

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


if __name__ == "__main__":
    unittest.main()
