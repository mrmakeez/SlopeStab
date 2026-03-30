from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "benchmarks" / "run_guarded_gate.py"
    spec = importlib.util.spec_from_file_location("run_guarded_gate", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_guarded_gate module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunGuardedGateScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_module()

    def test_build_verify_cli_args_workers(self) -> None:
        output = Path("tmp/gate_guarded/example/verify.json")
        args = self.mod._build_verify_cli_args(serial=False, workers=4, output_path=output)
        self.assertEqual(args[:3], ["verify", "--workers", "4"])
        self.assertEqual(args[-2:], ["--output", str(output)])

    def test_build_test_cli_args_serial(self) -> None:
        output = Path("tmp/gate_guarded/example/test.json")
        args = self.mod._build_test_cli_args(
            serial=True,
            workers=4,
            output_path=output,
            start_directory="tests",
            pattern="test_*.py",
            top_level_directory=None,
        )
        self.assertIn("--serial", args)
        self.assertNotIn("--workers", args)
        self.assertIn("--output", args)

    def test_build_stage_argv_nonfork(self) -> None:
        argv = self.mod._build_stage_argv(["verify", "--output", "tmp/verify.json"], force_fork_start_method=False)
        self.assertEqual(argv[:3], [self.mod.sys.executable, "-m", "slope_stab.cli"])
        self.assertEqual(argv[-3:], ["verify", "--output", "tmp/verify.json"])

    def test_build_stage_argv_fork_wrapper(self) -> None:
        argv = self.mod._build_stage_argv(["verify"], force_fork_start_method=True)
        self.assertEqual(argv[0], self.mod.sys.executable)
        self.assertEqual(argv[1], "-c")
        self.assertIn("set_start_method('fork'", argv[2])
        self.assertIn("main(['verify'])", argv[2])

    def test_next_timeout_ms_scales_up(self) -> None:
        self.assertEqual(self.mod._next_timeout_ms(100, 1.5), 150)
        self.assertEqual(self.mod._next_timeout_ms(101, 1.01), 102)

    def test_read_all_passed_contract(self) -> None:
        tmp_root = Path(__file__).resolve().parents[2] / "tmp"
        base = tmp_root / "unit_test_scratch" / f"guarded_gate_{uuid4().hex}"
        base.mkdir(parents=True, exist_ok=True)
        try:
            missing = base / "missing.json"
            passed, err = self.mod._read_all_passed(missing)
            self.assertIsNone(passed)
            self.assertEqual(err, "output_file_missing")

            invalid = base / "invalid.json"
            invalid.write_text("{not-json", encoding="utf-8")
            passed, err = self.mod._read_all_passed(invalid)
            self.assertIsNone(passed)
            self.assertIsNotNone(err)

            good = base / "good.json"
            good.write_text(json.dumps({"all_passed": True}), encoding="utf-8")
            passed, err = self.mod._read_all_passed(good)
            self.assertTrue(passed)
            self.assertIsNone(err)

            bad = base / "bad.json"
            bad.write_text(json.dumps({"all_passed": "yes"}), encoding="utf-8")
            passed, err = self.mod._read_all_passed(bad)
            self.assertIsNone(passed)
            self.assertEqual(err, "output_all_passed_missing_or_non_bool")
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
