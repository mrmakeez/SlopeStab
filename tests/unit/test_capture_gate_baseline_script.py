from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "benchmarks" / "capture_gate_baseline.py"
    spec = importlib.util.spec_from_file_location("capture_gate_baseline", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load capture_gate_baseline module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CaptureGateBaselineScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_module()

    def test_build_verify_argv_serial(self) -> None:
        argv = self.mod._build_verify_argv(serial=True, workers=4)
        self.assertEqual(argv[-1], "--serial")
        self.assertNotIn("--workers", argv)

    def test_build_verify_argv_workers(self) -> None:
        argv = self.mod._build_verify_argv(serial=False, workers=0)
        self.assertEqual(argv, [self.mod.sys.executable, "-m", "slope_stab.cli", "verify", "--workers", "0"])

    def test_build_test_argv_top_level_optional(self) -> None:
        argv = self.mod._build_test_argv(
            serial=False,
            workers=2,
            start_directory="tests",
            pattern="test_*.py",
            top_level_directory=None,
        )
        self.assertIn("--start-directory", argv)
        self.assertIn("--pattern", argv)
        self.assertNotIn("--top-level-directory", argv)

    def test_build_test_argv_with_top_level(self) -> None:
        argv = self.mod._build_test_argv(
            serial=False,
            workers=2,
            start_directory="tests",
            pattern="test_*.py",
            top_level_directory="C:/repo",
        )
        self.assertIn("--top-level-directory", argv)
        self.assertIn("C:/repo", argv)

    def test_executed_run_passed_requires_clean_contract(self) -> None:
        good = {"returncode": 0, "all_passed": True, "json_parse_error": None}
        bad_return = {"returncode": 1, "all_passed": True, "json_parse_error": None}
        bad_all_passed = {"returncode": 0, "all_passed": False, "json_parse_error": None}
        bad_parse = {"returncode": 0, "all_passed": True, "json_parse_error": "err"}
        self.assertTrue(self.mod._executed_run_passed(good))
        self.assertFalse(self.mod._executed_run_passed(bad_return))
        self.assertFalse(self.mod._executed_run_passed(bad_all_passed))
        self.assertFalse(self.mod._executed_run_passed(bad_parse))

    def test_stage_is_process_parallel(self) -> None:
        parallel = {
            "execution": {
                "backend": "process",
                "resolved_mode": "parallel",
                "resolved_workers": 4,
            }
        }
        serial = {
            "execution": {
                "backend": "thread",
                "resolved_mode": "serial",
                "resolved_workers": 1,
            }
        }
        missing = {}
        self.assertTrue(self.mod._stage_is_process_parallel(parallel))
        self.assertFalse(self.mod._stage_is_process_parallel(serial))
        self.assertFalse(self.mod._stage_is_process_parallel(missing))

    def test_normalize_optional_path(self) -> None:
        self.assertIsNone(self.mod._normalize_optional_path(None))
        rel = self.mod._normalize_optional_path("tests")
        self.assertIsNotNone(rel)
        assert rel is not None
        self.assertTrue(Path(rel).is_absolute())
        abs_path = str(Path(rel).resolve())
        self.assertEqual(self.mod._normalize_optional_path(abs_path), abs_path)


if __name__ == "__main__":
    unittest.main()
