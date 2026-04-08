from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.models import AnalysisResult
from slope_stab.verification.runner import (
    VERIFY_MODE_AUTO_PARALLEL,
    VERIFY_MODE_SERIAL,
    VerificationOutcome,
    resolve_verify_requested_workers,
    run_verification_suite_with_execution,
)


def _fake_outcome() -> VerificationOutcome:
    return VerificationOutcome(
        name="Fake Case",
        case_type="prescribed_benchmark",
        analysis_method="bishop_simplified",
        result=AnalysisResult(
            fos=1.0,
            converged=True,
            iterations=1,
            residual=0.0,
            driving_moment=1.0,
            resisting_moment=1.0,
        ),
        hard_checks={},
        diagnostics={},
        passed=True,
    )


class _FakeFuture:
    def __init__(self, value: VerificationOutcome | None = None, exc: Exception | None = None) -> None:
        self._value = value
        self._exc = exc

    def result(self) -> VerificationOutcome:
        if self._exc is not None:
            raise self._exc
        assert self._value is not None
        return self._value


class _FakeExecutorSuccess:
    def __enter__(self) -> _FakeExecutorSuccess:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        _ = fn, args
        return _FakeFuture(value=_fake_outcome())


class _FakeExecutorEnterFails:
    def __enter__(self):  # type: ignore[no-untyped-def]
        raise PermissionError("enter denied")

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        _ = fn, args
        return _FakeFuture(value=_fake_outcome())


class _FakeExecutorSubmitFails:
    def __enter__(self) -> _FakeExecutorSubmitFails:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        _ = fn, args
        raise PermissionError("submit denied")


class _FakeExecutorRuntimeFails:
    def __enter__(self) -> _FakeExecutorRuntimeFails:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        _ = fn, args
        return _FakeFuture(exc=RuntimeError("worker exploded"))


class VerificationRunnerWorkerPolicyTests(unittest.TestCase):
    def test_resolve_verify_requested_workers_rules(self) -> None:
        self.assertEqual(resolve_verify_requested_workers(0, 8), 4)
        self.assertEqual(resolve_verify_requested_workers(0, 3), 3)
        self.assertEqual(resolve_verify_requested_workers(99, 6), 6)
        self.assertEqual(resolve_verify_requested_workers(1, 6), 1)

    def test_serial_mode_execution_contract(self) -> None:
        with patch("slope_stab.verification.runner._evaluate_cases_serial", return_value=[_fake_outcome()]):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_SERIAL,
                requested_workers=1,
            )
        self.assertEqual(run_result.execution.requested_mode, "serial")
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "forced_serial_mode")
        self.assertEqual(len(run_result.outcomes), 1)

    def test_auto_mode_workers_le_one_resolves_serial(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=1),
            patch("slope_stab.verification.runner._evaluate_cases_serial", return_value=[_fake_outcome()]),
        ):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                requested_workers=0,
            )

        self.assertEqual(run_result.execution.requested_mode, "auto_parallel")
        self.assertEqual(run_result.execution.requested_workers, 1)
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.resolved_workers, 1)
        self.assertEqual(run_result.execution.decision_reason, "workers_le_one_serial")

    def test_auto_mode_constructor_startup_failure_falls_back_serial(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=6),
            patch("slope_stab.verification.runner.ProcessPoolExecutor", side_effect=PermissionError("denied")),
            patch("slope_stab.verification.runner._evaluate_cases_serial", return_value=[_fake_outcome()]),
        ):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                requested_workers=0,
            )

        self.assertEqual(run_result.execution.requested_workers, 4)
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "thread_backend_default_serial")

    def test_auto_mode_context_startup_failure_falls_back_serial(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=4),
            patch("slope_stab.verification.runner.ProcessPoolExecutor", return_value=_FakeExecutorEnterFails()),
            patch("slope_stab.verification.runner._evaluate_cases_serial", return_value=[_fake_outcome()]),
        ):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                requested_workers=0,
            )
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "thread_backend_default_serial")

    def test_auto_mode_submit_startup_failure_falls_back_serial(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=4),
            patch("slope_stab.verification.runner.ProcessPoolExecutor", return_value=_FakeExecutorSubmitFails()),
            patch("slope_stab.verification.runner._evaluate_cases_serial", return_value=[_fake_outcome()]),
        ):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                requested_workers=0,
            )
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "thread_backend_default_serial")

    def test_auto_mode_process_backend_runs_parallel(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=5),
            patch("slope_stab.verification.runner.ProcessPoolExecutor", return_value=_FakeExecutorSuccess()),
        ):
            run_result = run_verification_suite_with_execution(
                requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                requested_workers=0,
            )

        self.assertEqual(run_result.execution.requested_workers, 4)
        self.assertEqual(run_result.execution.resolved_mode, "parallel")
        self.assertEqual(run_result.execution.resolved_workers, 4)
        self.assertEqual(run_result.execution.backend, "process")
        self.assertEqual(run_result.execution.decision_reason, "process_backend_parallel")

    def test_runtime_worker_failure_is_not_silently_fallback(self) -> None:
        with (
            patch("slope_stab.verification.runner.effective_verify_cpu_count", return_value=4),
            patch("slope_stab.verification.runner.ProcessPoolExecutor", return_value=_FakeExecutorRuntimeFails()),
        ):
            with self.assertRaises(RuntimeError):
                run_verification_suite_with_execution(
                    requested_mode=VERIFY_MODE_AUTO_PARALLEL,
                    requested_workers=0,
                )


if __name__ == "__main__":
    unittest.main()
