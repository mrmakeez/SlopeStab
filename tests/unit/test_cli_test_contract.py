from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.cli import _cmd_test, build_parser
from slope_stab.testing import (
    UnittestExecution,
    UnittestRunResult,
    UnittestTargetOutcome,
)


def _fake_target(*, passed: bool = True) -> UnittestTargetOutcome:
    return UnittestTargetOutcome(
        target="tests.unit.test_geometry",
        passed=passed,
        returncode=0 if passed else 1,
        seconds=0.01,
        stdout="",
        stderr="",
    )


def _fake_run_result(*, passed: bool = True) -> UnittestRunResult:
    return UnittestRunResult(
        targets=[_fake_target(passed=passed)],
        execution=UnittestExecution(
            requested_mode="serial",
            resolved_mode="serial",
            decision_reason="forced_serial_mode",
            backend="serial",
            requested_workers=1,
            resolved_workers=1,
        ),
        start_directory="tests",
        pattern="test_*.py",
        top_level_directory=".",
    )


class CliTestContractTests(unittest.TestCase):
    def test_parser_test_defaults_to_auto_parallel(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test"])
        self.assertFalse(args.serial)
        self.assertIsNone(args.workers)
        self.assertEqual(args.start_directory, "tests")
        self.assertEqual(args.pattern, "test_*.py")
        self.assertIsInstance(args.top_level_directory, str)
        self.assertNotEqual(args.top_level_directory, "")

    def test_parser_rejects_serial_workers_conflict(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["test", "--serial", "--workers", "1"])

    def test_cmd_test_serial_uses_serial_contract(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test", "--serial"])

        with (
            patch("slope_stab.cli.run_unittest_suite_with_execution", return_value=_fake_run_result()) as mock_run,
            patch("slope_stab.cli._emit_stdout_text", return_value=True),
        ):
            code = _cmd_test(args)

        self.assertEqual(code, 0)
        mock_run.assert_called_once_with(
            requested_mode="serial",
            requested_workers=1,
            start_directory=args.start_directory,
            pattern=args.pattern,
            top_level_directory=args.top_level_directory,
        )

    def test_cmd_test_workers_negative_raises(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test", "--workers", "-1"])
        with self.assertRaises(ValueError):
            _cmd_test(args)

    def test_cmd_test_returns_zero_when_stdout_closed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test", "--serial"])

        with (
            patch("slope_stab.cli.run_unittest_suite_with_execution", return_value=_fake_run_result(passed=False)) as mock_run,
            patch("slope_stab.cli._emit_stdout_text", return_value=False) as mock_emit,
        ):
            code = _cmd_test(args)

        self.assertEqual(code, 0)
        mock_run.assert_called_once_with(
            requested_mode="serial",
            requested_workers=1,
            start_directory=args.start_directory,
            pattern=args.pattern,
            top_level_directory=args.top_level_directory,
        )
        mock_emit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
