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
        self.assertEqual(len(payload["cases"]), 4)

        cases = {item["name"]: item for item in payload["cases"]}
        self.assertEqual(set(cases), {"Case 1", "Case 2", "Case 3", "Case 4"})

        self.assertEqual(cases["Case 1"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 2"]["case_type"], "prescribed_benchmark")
        self.assertEqual(cases["Case 3"]["case_type"], "auto_refine_parity")
        self.assertEqual(cases["Case 4"]["case_type"], "auto_refine_parity")

        for item in payload["cases"]:
            self.assertIn("solver", item)
            self.assertIn("hard_checks", item)
            self.assertIn("diagnostics", item)


if __name__ == "__main__":
    unittest.main()
