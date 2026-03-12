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


if __name__ == "__main__":
    unittest.main()
