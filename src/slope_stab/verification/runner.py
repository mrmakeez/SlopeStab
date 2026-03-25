from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
import math
import os
from typing import Any

from slope_stab.analysis import run_analysis
from slope_stab.models import AnalysisResult
from slope_stab.verification.cases import (
    AutoRefineVerificationCase,
    GlobalSearchBenchmarkVerificationCase,
    PrescribedVerificationCase,
    VERIFICATION_CASES,
)


@dataclass(frozen=True)
class VerificationOutcome:
    name: str
    case_type: str
    analysis_method: str
    result: AnalysisResult
    hard_checks: dict[str, Any]
    diagnostics: dict[str, Any]
    passed: bool


VERIFY_MODE_SERIAL = "serial"
VERIFY_MODE_AUTO_PARALLEL = "auto_parallel"
VERIFY_RESOLVED_MODE_SERIAL = "serial"
VERIFY_RESOLVED_MODE_PARALLEL = "parallel"

VERIFY_BACKEND_SERIAL = "serial"
VERIFY_BACKEND_PROCESS = "process"
VERIFY_BACKEND_THREAD = "thread"

VERIFY_DECISION_FORCED_SERIAL_MODE = "forced_serial_mode"
VERIFY_DECISION_WORKERS_LE_ONE_SERIAL = "workers_le_one_serial"
VERIFY_DECISION_PROCESS_BACKEND_PARALLEL = "process_backend_parallel"
VERIFY_DECISION_THREAD_BACKEND_DEFAULT_SERIAL = "thread_backend_default_serial"

VERIFY_EVIDENCE_VERSION = "verify-auto-v1"


@dataclass(frozen=True)
class VerificationExecution:
    requested_mode: str
    resolved_mode: str
    decision_reason: str
    backend: str
    requested_workers: int
    resolved_workers: int
    evidence_version: str = VERIFY_EVIDENCE_VERSION

    @property
    def run_parallel(self) -> bool:
        return self.resolved_mode == VERIFY_RESOLVED_MODE_PARALLEL and self.resolved_workers > 1


@dataclass(frozen=True)
class VerificationRunResult:
    outcomes: list[VerificationOutcome]
    execution: VerificationExecution


def effective_verify_cpu_count() -> int:
    try:
        if hasattr(os, "sched_getaffinity"):
            affinity_count = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
            if affinity_count > 0:
                return affinity_count
    except Exception:
        pass
    return max(1, int(os.cpu_count() or 1))


def resolve_verify_requested_workers(configured_workers: int, available_workers: int) -> int:
    if configured_workers == 0:
        return min(4, available_workers)
    return min(max(1, configured_workers), available_workers)


def _relative_error(actual: float, expected: float) -> float:
    if expected == 0.0:
        if actual == 0.0:
            return 0.0
        return float("inf")
    return abs(actual - expected) / abs(expected)


def _evaluate_prescribed_case(
    case: PrescribedVerificationCase,
    result: AnalysisResult,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    fos_abs_error = abs(result.fos - case.expected_fos)
    hard_checks: dict[str, Any] = {
        "fos_abs_error": {
            "value": fos_abs_error,
            "tolerance": case.fos_tolerance,
            "expected": case.expected_fos,
            "passed": fos_abs_error <= case.fos_tolerance,
        }
    }

    if (
        case.expected_driving_moment is not None
        and case.expected_resisting_moment is not None
        and case.moment_rel_tolerance is not None
    ):
        driving_rel_error = _relative_error(result.driving_moment, case.expected_driving_moment)
        resisting_rel_error = _relative_error(result.resisting_moment, case.expected_resisting_moment)
        hard_checks["driving_rel_error"] = {
            "value": driving_rel_error,
            "tolerance": case.moment_rel_tolerance,
            "expected": case.expected_driving_moment,
            "passed": driving_rel_error <= case.moment_rel_tolerance,
        }
        hard_checks["resisting_rel_error"] = {
            "value": resisting_rel_error,
            "tolerance": case.moment_rel_tolerance,
            "expected": case.expected_resisting_moment,
            "passed": resisting_rel_error <= case.moment_rel_tolerance,
        }

    passed = all(check["passed"] for check in hard_checks.values())
    diagnostics: dict[str, Any] = {}
    return hard_checks, diagnostics, passed


def _evaluate_auto_refine_case(
    case: AutoRefineVerificationCase,
    result: AnalysisResult,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    surface = result.metadata.get("prescribed_surface", {})
    search_meta = result.metadata.get("search", {})

    x_left = float(surface.get("x_left", float("nan")))
    y_left = float(surface.get("y_left", float("nan")))
    x_right = float(surface.get("x_right", float("nan")))
    y_right = float(surface.get("y_right", float("nan")))
    radius = float(surface.get("r", float("nan")))
    xc = float(surface.get("xc", float("nan")))
    yc = float(surface.get("yc", float("nan")))

    fos_abs_error = abs(result.fos - case.expected_fos)
    endpoint_errors = {
        "x_left": abs(x_left - case.expected_left[0]),
        "y_left": abs(y_left - case.expected_left[1]),
        "x_right": abs(x_right - case.expected_right[0]),
        "y_right": abs(y_right - case.expected_right[1]),
    }
    radius_rel_error = _relative_error(radius, case.expected_radius)

    hard_checks = {
        "fos_abs_error": {
            "value": fos_abs_error,
            "tolerance": case.fos_tolerance,
            "expected": case.expected_fos,
            "passed": fos_abs_error <= case.fos_tolerance,
        },
        "endpoint_abs_error": {
            key: {
                "value": value,
                "tolerance": case.endpoint_abs_tolerance,
                "expected": (
                    case.expected_left[0]
                    if key == "x_left"
                    else case.expected_left[1]
                    if key == "y_left"
                    else case.expected_right[0]
                    if key == "x_right"
                    else case.expected_right[1]
                ),
                "passed": value <= case.endpoint_abs_tolerance,
            }
            for key, value in endpoint_errors.items()
        },
        "radius_rel_error": {
            "value": radius_rel_error,
            "tolerance": case.radius_rel_tolerance,
            "expected": case.expected_radius,
            "passed": radius_rel_error <= case.radius_rel_tolerance,
        },
    }

    endpoint_passed = all(item["passed"] for item in hard_checks["endpoint_abs_error"].values())
    passed = (
        hard_checks["fos_abs_error"]["passed"]
        and endpoint_passed
        and hard_checks["radius_rel_error"]["passed"]
    )

    center_distance = math.hypot(xc - case.expected_center[0], yc - case.expected_center[1])
    diagnostics = {
        "center_distance": center_distance,
        "valid_surfaces": search_meta.get("valid_surfaces"),
        "invalid_surfaces": search_meta.get("invalid_surfaces"),
        "generated_surfaces": search_meta.get("generated_surfaces"),
        "iteration_diagnostics_count": len(search_meta.get("iteration_diagnostics", [])),
    }

    return hard_checks, diagnostics, passed


def _evaluate_global_search_benchmark_case(
    case: GlobalSearchBenchmarkVerificationCase,
    result: AnalysisResult,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    threshold = case.benchmark_fos + case.margin
    hard_checks = {
        "fos_vs_benchmark_plus_margin": {
            "value": result.fos,
            "threshold": threshold,
            "benchmark": case.benchmark_fos,
            "margin": case.margin,
            "passed": result.fos <= threshold,
        }
    }
    diagnostics = {
        "delta_vs_benchmark": result.fos - case.benchmark_fos,
        "delta_vs_threshold": result.fos - threshold,
    }
    passed = hard_checks["fos_vs_benchmark_plus_margin"]["passed"]
    return hard_checks, diagnostics, passed


def _evaluate_case(case_index: int) -> VerificationOutcome:
    case = VERIFICATION_CASES[case_index]
    result = run_analysis(case.project, forced_parallel_mode="serial", forced_parallel_workers=1)
    if isinstance(case, PrescribedVerificationCase):
        hard_checks, diagnostics, passed = _evaluate_prescribed_case(case, result)
    elif isinstance(case, AutoRefineVerificationCase):
        hard_checks, diagnostics, passed = _evaluate_auto_refine_case(case, result)
    elif isinstance(case, GlobalSearchBenchmarkVerificationCase):
        hard_checks, diagnostics, passed = _evaluate_global_search_benchmark_case(case, result)
    else:
        raise TypeError(f"Unsupported verification case type: {type(case)!r}")

    return VerificationOutcome(
        name=case.name,
        case_type=case.case_type,
        analysis_method=case.analysis_method,
        result=result,
        hard_checks=hard_checks,
        diagnostics=diagnostics,
        passed=passed,
    )


def _evaluate_cases_serial() -> list[VerificationOutcome]:
    return [_evaluate_case(case_index) for case_index in range(len(VERIFICATION_CASES))]


def _evaluate_cases_parallel(executor_cm: Any) -> list[VerificationOutcome]:
    outcomes: list[VerificationOutcome | None] = [None] * len(VERIFICATION_CASES)
    with executor_cm as executor:
        futures = [executor.submit(_evaluate_case, idx) for idx in range(len(VERIFICATION_CASES))]
        for idx, future in enumerate(futures):
            try:
                outcomes[idx] = future.result()
            except Exception as exc:
                raise RuntimeError(f"Verification worker failed for case index {idx}.") from exc
    return [outcome for outcome in outcomes if outcome is not None]


def run_verification_suite_with_execution(
    *,
    requested_mode: str = VERIFY_MODE_AUTO_PARALLEL,
    requested_workers: int = 0,
) -> VerificationRunResult:
    if requested_workers < 0:
        raise ValueError("requested_workers must be greater than or equal to zero.")
    if requested_mode not in {VERIFY_MODE_AUTO_PARALLEL, VERIFY_MODE_SERIAL}:
        raise ValueError(f"Unsupported verify requested_mode: {requested_mode!r}")

    if requested_mode == VERIFY_MODE_SERIAL:
        execution = VerificationExecution(
            requested_mode=VERIFY_MODE_SERIAL,
            resolved_mode=VERIFY_RESOLVED_MODE_SERIAL,
            decision_reason=VERIFY_DECISION_FORCED_SERIAL_MODE,
            backend=VERIFY_BACKEND_SERIAL,
            requested_workers=1,
            resolved_workers=1,
        )
        return VerificationRunResult(outcomes=_evaluate_cases_serial(), execution=execution)

    available_workers = effective_verify_cpu_count()
    normalized_requested_workers = resolve_verify_requested_workers(requested_workers, available_workers)
    if normalized_requested_workers <= 1:
        execution = VerificationExecution(
            requested_mode=VERIFY_MODE_AUTO_PARALLEL,
            resolved_mode=VERIFY_RESOLVED_MODE_SERIAL,
            decision_reason=VERIFY_DECISION_WORKERS_LE_ONE_SERIAL,
            backend=VERIFY_BACKEND_SERIAL,
            requested_workers=normalized_requested_workers,
            resolved_workers=1,
        )
        return VerificationRunResult(outcomes=_evaluate_cases_serial(), execution=execution)

    try:
        executor_cm = ProcessPoolExecutor(max_workers=normalized_requested_workers)
    except (OSError, PermissionError):
        execution = VerificationExecution(
            requested_mode=VERIFY_MODE_AUTO_PARALLEL,
            resolved_mode=VERIFY_RESOLVED_MODE_SERIAL,
            decision_reason=VERIFY_DECISION_THREAD_BACKEND_DEFAULT_SERIAL,
            backend=VERIFY_BACKEND_THREAD,
            requested_workers=normalized_requested_workers,
            resolved_workers=1,
        )
        return VerificationRunResult(outcomes=_evaluate_cases_serial(), execution=execution)

    execution = VerificationExecution(
        requested_mode=VERIFY_MODE_AUTO_PARALLEL,
        resolved_mode=VERIFY_RESOLVED_MODE_PARALLEL,
        decision_reason=VERIFY_DECISION_PROCESS_BACKEND_PARALLEL,
        backend=VERIFY_BACKEND_PROCESS,
        requested_workers=normalized_requested_workers,
        resolved_workers=normalized_requested_workers,
    )
    return VerificationRunResult(outcomes=_evaluate_cases_parallel(executor_cm), execution=execution)


def run_verification_suite(workers: int = 1) -> list[VerificationOutcome]:
    workers = max(1, int(workers))
    if workers <= 1:
        return _evaluate_cases_serial()

    try:
        executor_cm = ProcessPoolExecutor(max_workers=workers)
    except (OSError, PermissionError):
        executor_cm = ThreadPoolExecutor(max_workers=workers)

    return _evaluate_cases_parallel(executor_cm)
