from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.cli import _cmd_verify, build_parser
from slope_stab.models import AnalysisResult
from slope_stab.verification.runner import VerificationExecution, VerificationOutcome, VerificationRunResult


def _fake_result(*, fos: float) -> AnalysisResult:
    return AnalysisResult(
        fos=fos,
        converged=True,
        iterations=5,
        residual=0.0,
        driving_moment=10.0,
        resisting_moment=12.0,
    )


def _fake_run_result() -> VerificationRunResult:
    outcomes = [
        VerificationOutcome(
            name="Case 1",
            case_type="prescribed_benchmark",
            analysis_method="bishop_simplified",
            result=_fake_result(fos=1.0),
            hard_checks={"fos_abs_error": {"value": 0.0, "tolerance": 0.001, "expected": 1.0, "passed": True}},
            diagnostics={},
            passed=True,
        ),
        VerificationOutcome(
            name="Case 11 (Non-Uniform Direct Global Search Benchmark)",
            case_type="non_uniform_search_benchmark",
            analysis_method="bishop_simplified",
            result=_fake_result(fos=0.42),
            hard_checks={
                "fos_vs_slide2_plus_margin": {
                    "value": 0.42,
                    "threshold": 0.43,
                    "slide2_fos": 0.42,
                    "margin": 0.01,
                    "passed": True,
                }
            },
            diagnostics={"radius": 30.0},
            passed=True,
        ),
    ]
    execution = VerificationExecution(
        requested_mode="auto_parallel",
        resolved_mode="parallel",
        decision_reason="process_backend_parallel",
        backend="process",
        requested_workers=4,
        resolved_workers=4,
    )
    return VerificationRunResult(outcomes=outcomes, execution=execution, error=None)


class CliRegressionTests(unittest.TestCase):
    def test_verify_command_contract(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify"])
        with (
            patch("slope_stab.cli.run_verification_suite_with_execution", return_value=_fake_run_result()),
            patch("slope_stab.cli._emit_stdout_text", return_value=True) as mock_emit,
        ):
            code = _cmd_verify(args)

        self.assertEqual(code, 0)
        payload = json.loads(mock_emit.call_args.args[0])
        self.assertTrue(payload["all_passed"])
        self.assertEqual(len(payload["cases"]), 2)
        self.assertIn("execution", payload)

        execution = payload["execution"]
        self.assertEqual(execution["requested_mode"], "auto_parallel")
        self.assertEqual(execution["resolved_mode"], "parallel")
        self.assertEqual(execution["decision_reason"], "process_backend_parallel")
        self.assertEqual(execution["backend"], "process")
        self.assertEqual(execution["requested_workers"], 4)
        self.assertEqual(execution["resolved_workers"], 4)

        cases = {item["name"]: item for item in payload["cases"]}
        self.assertIn("Case 1", cases)
        self.assertIn("Case 11 (Non-Uniform Direct Global Search Benchmark)", cases)
        self.assertEqual(cases["Case 1"]["case_type"], "prescribed_benchmark")
        self.assertEqual(
            cases["Case 11 (Non-Uniform Direct Global Search Benchmark)"]["case_type"],
            "non_uniform_search_benchmark",
        )
        self.assertEqual(cases["Case 11 (Non-Uniform Direct Global Search Benchmark)"]["analysis_method"], "bishop_simplified")

        non_uniform_check = cases["Case 11 (Non-Uniform Direct Global Search Benchmark)"]["hard_checks"][
            "fos_vs_slide2_plus_margin"
        ]
        self.assertIn("value", non_uniform_check)
        self.assertIn("threshold", non_uniform_check)
        self.assertIn("slide2_fos", non_uniform_check)
        self.assertIn("margin", non_uniform_check)
        self.assertIn("passed", non_uniform_check)

        for item in payload["cases"]:
            self.assertIn("solver", item)
            self.assertIn("hard_checks", item)
            self.assertIn("diagnostics", item)
            self.assertIn("analysis_method", item)

    def test_verify_serial_workers_conflict(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["verify", "--serial", "--workers", "1"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
