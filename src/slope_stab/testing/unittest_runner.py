from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
import time
import unittest
from typing import Any, Iterator

from slope_stab.errors.contracts import (
    ERROR_CODE_DISCOVERY_IMPORT,
    ERROR_CODE_DISCOVERY_UNEXPECTED,
    STAGE_DISCOVERY,
    error_payload,
)
from slope_stab.execution.worker_policy import effective_cpu_count, resolve_requested_workers


TEST_MODE_SERIAL = "serial"
TEST_MODE_AUTO_PARALLEL = "auto_parallel"
TEST_RESOLVED_MODE_SERIAL = "serial"
TEST_RESOLVED_MODE_PARALLEL = "parallel"

TEST_BACKEND_SERIAL = "serial"
TEST_BACKEND_PROCESS = "process"

TEST_DECISION_FORCED_SERIAL_MODE = "forced_serial_mode"
TEST_DECISION_WORKERS_LE_ONE_SERIAL = "workers_le_one_serial"
TEST_DECISION_PROCESS_BACKEND_PARALLEL = "process_backend_parallel"
TEST_DECISION_THREAD_BACKEND_DEFAULT_SERIAL = "thread_backend_default_serial"
TEST_DECISION_NO_TARGETS_DISCOVERED = "no_test_targets_discovered"
TEST_DECISION_DISCOVERY_ERROR = "discovery_error_serial"

TEST_EVIDENCE_VERSION = "unittest-auto-v1"


class _ParallelStartupError(RuntimeError):
    pass


class _ParallelRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class UnittestExecution:
    requested_mode: str
    resolved_mode: str
    decision_reason: str
    backend: str
    requested_workers: int
    resolved_workers: int
    evidence_version: str = TEST_EVIDENCE_VERSION

    @property
    def run_parallel(self) -> bool:
        return self.resolved_mode == TEST_RESOLVED_MODE_PARALLEL and self.resolved_workers > 1


@dataclass(frozen=True)
class UnittestTargetOutcome:
    target: str
    passed: bool
    returncode: int
    seconds: float
    stdout: str
    stderr: str


@dataclass(frozen=True)
class UnittestRunResult:
    targets: list[UnittestTargetOutcome]
    execution: UnittestExecution
    start_directory: str
    pattern: str
    top_level_directory: str
    discovery_error: dict[str, str] | None = None
    error: dict[str, str] | None = None

    @property
    def all_passed(self) -> bool:
        return self.error is None and self.discovery_error is None and bool(self.targets) and all(item.passed for item in self.targets)


def effective_unittest_cpu_count() -> int:
    return effective_cpu_count()


def resolve_unittest_requested_workers(configured_workers: int, available_workers: int) -> int:
    return resolve_requested_workers(configured_workers, available_workers)


def _iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.case.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _extract_target_module_name(test: unittest.case.TestCase) -> str:
    test_id = test.id()
    failed_prefix = "unittest.loader._FailedTest."
    if test_id.startswith(failed_prefix):
        return test_id[len(failed_prefix) :]
    return test_id.rsplit(".", 2)[0]


def _discover_target_modules(start_directory: str, pattern: str, top_level_directory: str) -> list[str]:
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=start_directory,
        pattern=pattern,
        top_level_dir=top_level_directory,
    )

    ordered_targets: list[str] = []
    seen: set[str] = set()
    for test in _iter_tests(suite):
        module_name = _extract_target_module_name(test)
        if module_name not in seen:
            seen.add(module_name)
            ordered_targets.append(module_name)
    return ordered_targets


def _compose_pythonpath(extra_entries: list[str]) -> str:
    existing = os.environ.get("PYTHONPATH", "")
    values: list[str] = []
    for entry in extra_entries:
        if entry and entry not in values:
            values.append(entry)
    if existing:
        for entry in existing.split(os.pathsep):
            if entry and entry not in values:
                values.append(entry)
    return os.pathsep.join(values)


def _run_unittest_target(target: str, cwd: str, pythonpath: str) -> UnittestTargetOutcome:
    started = time.perf_counter()
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", target],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = round(time.perf_counter() - started, 3)
    return UnittestTargetOutcome(
        target=target,
        passed=completed.returncode == 0,
        returncode=completed.returncode,
        seconds=elapsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _evaluate_targets_serial(targets: list[str], cwd: str, pythonpath: str) -> list[UnittestTargetOutcome]:
    return [_run_unittest_target(target, cwd, pythonpath) for target in targets]


def _evaluate_targets_parallel(
    targets: list[str],
    executor_cm: Any,
    cwd: str,
    pythonpath: str,
) -> list[UnittestTargetOutcome]:
    outcomes: list[UnittestTargetOutcome | None] = [None] * len(targets)

    try:
        with executor_cm as executor:
            futures = []
            for target in targets:
                try:
                    futures.append(executor.submit(_run_unittest_target, target, cwd, pythonpath))
                except (OSError, PermissionError) as exc:
                    raise _ParallelStartupError("Unittest process backend failed during worker startup.") from exc

            for idx, future in enumerate(futures):
                target = targets[idx]
                try:
                    outcomes[idx] = future.result()
                except Exception as exc:
                    raise _ParallelRuntimeError(
                        f"Unittest worker failed for target '{target}' (index={idx})."
                    ) from exc
    except (OSError, PermissionError) as exc:
        raise _ParallelStartupError("Unittest process backend failed during worker startup.") from exc

    return [outcome for outcome in outcomes if outcome is not None]


def _resolve_discovery_paths(
    *,
    start_directory: str,
    top_level_directory: str | None,
) -> tuple[str, str]:
    top = Path(top_level_directory).resolve() if top_level_directory is not None else Path.cwd().resolve()
    start_path = Path(start_directory)
    if not start_path.is_absolute():
        start_path = (top / start_path).resolve()
    else:
        start_path = start_path.resolve()
    return str(start_path), str(top)


def run_unittest_suite_with_execution(
    *,
    requested_mode: str = TEST_MODE_AUTO_PARALLEL,
    requested_workers: int = 0,
    start_directory: str = "tests",
    pattern: str = "test_*.py",
    top_level_directory: str | None = None,
) -> UnittestRunResult:
    if requested_workers < 0:
        raise ValueError("requested_workers must be greater than or equal to zero.")
    if requested_mode not in {TEST_MODE_AUTO_PARALLEL, TEST_MODE_SERIAL}:
        raise ValueError(f"Unsupported unittest requested_mode: {requested_mode!r}")

    resolved_start_directory, resolved_top_level_directory = _resolve_discovery_paths(
        start_directory=start_directory,
        top_level_directory=top_level_directory,
    )
    src_directory = str((Path(resolved_top_level_directory) / "src").resolve())
    pythonpath = _compose_pythonpath([src_directory])

    try:
        targets = _discover_target_modules(
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
        )
    except ImportError as exc:
        requested_workers_for_discovery = (
            1
            if requested_mode == TEST_MODE_SERIAL
            else resolve_unittest_requested_workers(requested_workers, effective_unittest_cpu_count())
        )
        discovery_error = error_payload(
            code=ERROR_CODE_DISCOVERY_IMPORT,
            message=str(exc),
            stage=STAGE_DISCOVERY,
        )
        execution = UnittestExecution(
            requested_mode=requested_mode,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_DISCOVERY_ERROR,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=requested_workers_for_discovery,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=[],
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
            discovery_error=discovery_error,
            error=discovery_error,
        )
    except Exception as exc:
        requested_workers_for_discovery = (
            1
            if requested_mode == TEST_MODE_SERIAL
            else resolve_unittest_requested_workers(requested_workers, effective_unittest_cpu_count())
        )
        discovery_error = error_payload(
            code=ERROR_CODE_DISCOVERY_UNEXPECTED,
            message=f"{exc.__class__.__name__}: {exc}",
            stage=STAGE_DISCOVERY,
        )
        execution = UnittestExecution(
            requested_mode=requested_mode,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_DISCOVERY_ERROR,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=requested_workers_for_discovery,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=[],
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
            discovery_error=discovery_error,
            error=discovery_error,
        )

    if not targets:
        requested_workers_for_discovery = (
            1
            if requested_mode == TEST_MODE_SERIAL
            else resolve_unittest_requested_workers(requested_workers, effective_unittest_cpu_count())
        )
        discovery_error = error_payload(
            code=ERROR_CODE_DISCOVERY_UNEXPECTED,
            message="No test targets discovered for the provided discovery inputs.",
            stage=STAGE_DISCOVERY,
        )
        execution = UnittestExecution(
            requested_mode=requested_mode,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_NO_TARGETS_DISCOVERED,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=requested_workers_for_discovery,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=[],
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
            discovery_error=discovery_error,
            error=discovery_error,
        )

    if requested_mode == TEST_MODE_SERIAL:
        execution = UnittestExecution(
            requested_mode=TEST_MODE_SERIAL,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_FORCED_SERIAL_MODE,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=1,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=_evaluate_targets_serial(targets, resolved_top_level_directory, pythonpath),
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
        )

    available_workers = effective_unittest_cpu_count()
    normalized_requested_workers = resolve_unittest_requested_workers(requested_workers, available_workers)
    if normalized_requested_workers <= 1:
        execution = UnittestExecution(
            requested_mode=TEST_MODE_AUTO_PARALLEL,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_WORKERS_LE_ONE_SERIAL,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=normalized_requested_workers,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=_evaluate_targets_serial(targets, resolved_top_level_directory, pythonpath),
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
        )

    try:
        executor_cm = ProcessPoolExecutor(max_workers=normalized_requested_workers)
    except (OSError, PermissionError):
        execution = UnittestExecution(
            requested_mode=TEST_MODE_AUTO_PARALLEL,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_THREAD_BACKEND_DEFAULT_SERIAL,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=normalized_requested_workers,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=_evaluate_targets_serial(targets, resolved_top_level_directory, pythonpath),
            execution=execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
        )

    execution = UnittestExecution(
        requested_mode=TEST_MODE_AUTO_PARALLEL,
        resolved_mode=TEST_RESOLVED_MODE_PARALLEL,
        decision_reason=TEST_DECISION_PROCESS_BACKEND_PARALLEL,
        backend=TEST_BACKEND_PROCESS,
        requested_workers=normalized_requested_workers,
        resolved_workers=normalized_requested_workers,
    )
    try:
        outcomes = _evaluate_targets_parallel(targets, executor_cm, resolved_top_level_directory, pythonpath)
    except _ParallelStartupError:
        fallback_execution = UnittestExecution(
            requested_mode=TEST_MODE_AUTO_PARALLEL,
            resolved_mode=TEST_RESOLVED_MODE_SERIAL,
            decision_reason=TEST_DECISION_THREAD_BACKEND_DEFAULT_SERIAL,
            backend=TEST_BACKEND_SERIAL,
            requested_workers=normalized_requested_workers,
            resolved_workers=1,
        )
        return UnittestRunResult(
            targets=_evaluate_targets_serial(targets, resolved_top_level_directory, pythonpath),
            execution=fallback_execution,
            start_directory=resolved_start_directory,
            pattern=pattern,
            top_level_directory=resolved_top_level_directory,
        )
    return UnittestRunResult(
        targets=outcomes,
        execution=execution,
        start_directory=resolved_start_directory,
        pattern=pattern,
        top_level_directory=resolved_top_level_directory,
    )
