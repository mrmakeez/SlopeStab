from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.cli import _cmd_verify, build_parser
from slope_stab.models import AnalysisResult
from slope_stab.verification.runner import VerificationExecution, VerificationOutcome, VerificationRunResult


def _fake_result() -> AnalysisResult:
    return AnalysisResult(
        fos=1.0,
        converged=True,
        iterations=1,
        residual=0.0,
        driving_moment=1.0,
        resisting_moment=1.0,
    )


def _fake_run_result(*, passed: bool = True) -> VerificationRunResult:
    outcome = VerificationOutcome(
        name="Fake Case",
        case_type="prescribed_benchmark",
        analysis_method="bishop_simplified",
        result=_fake_result(),
        hard_checks={},
        diagnostics={},
        passed=passed,
    )
    execution = VerificationExecution(
        requested_mode="serial",
        resolved_mode="serial",
        decision_reason="forced_serial_mode",
        backend="serial",
        requested_workers=1,
        resolved_workers=1,
    )
    return VerificationRunResult(outcomes=[outcome], execution=execution)


class CliVerifyContractTests(unittest.TestCase):
    def test_parser_verify_defaults_to_auto_parallel(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify"])
        self.assertFalse(args.serial)
        self.assertIsNone(args.workers)

    def test_cmd_verify_serial_uses_serial_contract(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "--serial"])

        with (
            patch("slope_stab.cli.run_verification_suite_with_execution", return_value=_fake_run_result()) as mock_run,
            patch("slope_stab.cli._emit_stdout_text", return_value=True),
        ):
            code = _cmd_verify(args)

        self.assertEqual(code, 0)
        mock_run.assert_called_once_with(requested_mode="serial", requested_workers=1)

    def test_cmd_verify_returns_zero_when_stdout_closed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "--serial"])

        with (
            patch(
                "slope_stab.cli.run_verification_suite_with_execution",
                return_value=_fake_run_result(passed=False),
            ) as mock_run,
            patch("slope_stab.cli._emit_stdout_text", return_value=False) as mock_emit,
        ):
            code = _cmd_verify(args)

        self.assertEqual(code, 0)
        mock_run.assert_called_once_with(requested_mode="serial", requested_workers=1)
        mock_emit.assert_called_once()

    def test_cmd_verify_workers_negative_raises(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "--workers", "-1"])
        with self.assertRaises(ValueError):
            _cmd_verify(args)


if __name__ == "__main__":
    unittest.main()
