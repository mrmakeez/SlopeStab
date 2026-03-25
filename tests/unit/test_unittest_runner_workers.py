from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.testing.unittest_runner import (
    TEST_DECISION_NO_TARGETS_DISCOVERED,
    TEST_MODE_AUTO_PARALLEL,
    TEST_MODE_SERIAL,
    UnittestTargetOutcome,
    _evaluate_targets_parallel,
    resolve_unittest_requested_workers,
    run_unittest_suite_with_execution,
)


def _fake_target(target: str = "tests.unit.test_geometry") -> UnittestTargetOutcome:
    return UnittestTargetOutcome(
        target=target,
        passed=True,
        returncode=0,
        seconds=0.01,
        stdout="",
        stderr="",
    )


class _FakeFuture:
    def __init__(self, value: UnittestTargetOutcome) -> None:
        self._value = value

    def result(self) -> UnittestTargetOutcome:
        return self._value


class _FakeExecutor:
    def __enter__(self) -> _FakeExecutor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        return _FakeFuture(fn(*args))


class UnittestRunnerWorkerPolicyTests(unittest.TestCase):
    def test_resolve_requested_workers_rules(self) -> None:
        self.assertEqual(resolve_unittest_requested_workers(0, 8), 4)
        self.assertEqual(resolve_unittest_requested_workers(0, 3), 3)
        self.assertEqual(resolve_unittest_requested_workers(99, 6), 6)
        self.assertEqual(resolve_unittest_requested_workers(1, 6), 1)

    def test_serial_mode_execution_contract(self) -> None:
        with (
            patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=["tests.unit.test_geometry"]),
            patch(
                "slope_stab.testing.unittest_runner._evaluate_targets_serial",
                return_value=[_fake_target()],
            ),
        ):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_SERIAL,
                requested_workers=1,
                start_directory="tests",
                pattern="test_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.execution.requested_mode, "serial")
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "forced_serial_mode")
        self.assertEqual(run_result.execution.requested_workers, 1)
        self.assertEqual(run_result.execution.resolved_workers, 1)

    def test_auto_mode_workers_le_one_resolves_serial(self) -> None:
        with (
            patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=["tests.unit.test_geometry"]),
            patch("slope_stab.testing.unittest_runner.effective_unittest_cpu_count", return_value=1),
            patch(
                "slope_stab.testing.unittest_runner._evaluate_targets_serial",
                return_value=[_fake_target()],
            ),
        ):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_AUTO_PARALLEL,
                requested_workers=0,
                start_directory="tests",
                pattern="test_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.execution.requested_mode, "auto_parallel")
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.backend, "serial")
        self.assertEqual(run_result.execution.decision_reason, "workers_le_one_serial")
        self.assertEqual(run_result.execution.requested_workers, 1)
        self.assertEqual(run_result.execution.resolved_workers, 1)

    def test_auto_mode_process_startup_failure_falls_back_serial(self) -> None:
        with (
            patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=["tests.unit.test_geometry"]),
            patch("slope_stab.testing.unittest_runner.effective_unittest_cpu_count", return_value=6),
            patch("slope_stab.testing.unittest_runner.ProcessPoolExecutor", side_effect=PermissionError("denied")),
            patch(
                "slope_stab.testing.unittest_runner._evaluate_targets_serial",
                return_value=[_fake_target()],
            ),
        ):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_AUTO_PARALLEL,
                requested_workers=0,
                start_directory="tests",
                pattern="test_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.execution.requested_workers, 4)
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.resolved_workers, 1)
        self.assertEqual(run_result.execution.backend, "thread")
        self.assertEqual(run_result.execution.decision_reason, "thread_backend_default_serial")

    def test_auto_mode_process_backend_runs_parallel(self) -> None:
        with (
            patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=["tests.unit.test_geometry"]),
            patch("slope_stab.testing.unittest_runner.effective_unittest_cpu_count", return_value=5),
            patch("slope_stab.testing.unittest_runner.ProcessPoolExecutor", return_value=object()),
            patch(
                "slope_stab.testing.unittest_runner._evaluate_targets_parallel",
                return_value=[_fake_target()],
            ),
        ):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_AUTO_PARALLEL,
                requested_workers=0,
                start_directory="tests",
                pattern="test_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.execution.requested_workers, 4)
        self.assertEqual(run_result.execution.resolved_mode, "parallel")
        self.assertEqual(run_result.execution.resolved_workers, 4)
        self.assertEqual(run_result.execution.backend, "process")
        self.assertEqual(run_result.execution.decision_reason, "process_backend_parallel")

    def test_auto_mode_submit_startup_failure_falls_back_serial(self) -> None:
        with (
            patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=["tests.unit.test_geometry"]),
            patch("slope_stab.testing.unittest_runner.effective_unittest_cpu_count", return_value=5),
            patch("slope_stab.testing.unittest_runner.ProcessPoolExecutor", return_value=object()),
            patch("slope_stab.testing.unittest_runner._evaluate_targets_parallel", side_effect=PermissionError("denied")),
            patch(
                "slope_stab.testing.unittest_runner._evaluate_targets_serial",
                return_value=[_fake_target()],
            ),
        ):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_AUTO_PARALLEL,
                requested_workers=0,
                start_directory="tests",
                pattern="test_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.execution.requested_workers, 4)
        self.assertEqual(run_result.execution.resolved_mode, "serial")
        self.assertEqual(run_result.execution.resolved_workers, 1)
        self.assertEqual(run_result.execution.backend, "thread")
        self.assertEqual(run_result.execution.decision_reason, "thread_backend_default_serial")

    def test_parallel_target_merge_preserves_input_order(self) -> None:
        with patch("slope_stab.testing.unittest_runner._run_unittest_target", side_effect=lambda target, *_: _fake_target(target)):
            outcomes = _evaluate_targets_parallel(
                targets=["sample_b", "sample_a"],
                executor_cm=_FakeExecutor(),
                cwd=".",
                pythonpath="src",
            )
        self.assertEqual([item.target for item in outcomes], ["sample_b", "sample_a"])

    def test_no_targets_discovered_is_a_failure(self) -> None:
        with patch("slope_stab.testing.unittest_runner._discover_target_modules", return_value=[]):
            run_result = run_unittest_suite_with_execution(
                requested_mode=TEST_MODE_SERIAL,
                requested_workers=1,
                start_directory="tests",
                pattern="definitely_no_tests_*.py",
                top_level_directory=".",
            )
        self.assertEqual(run_result.targets, [])
        self.assertFalse(run_result.all_passed)
        self.assertEqual(run_result.discovery_error, TEST_DECISION_NO_TARGETS_DISCOVERED)
        self.assertEqual(run_result.execution.decision_reason, TEST_DECISION_NO_TARGETS_DISCOVERED)
        self.assertEqual(run_result.execution.backend, "serial")


if __name__ == "__main__":
    unittest.main()
