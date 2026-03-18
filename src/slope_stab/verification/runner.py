from __future__ import annotations

from dataclasses import dataclass
import math
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
    result: AnalysisResult
    hard_checks: dict[str, Any]
    diagnostics: dict[str, Any]
    passed: bool


def _relative_error(actual: float, expected: float) -> float:
    if expected == 0.0:
        return float("inf")
    return abs(actual - expected) / abs(expected)


def _evaluate_prescribed_case(
    case: PrescribedVerificationCase,
    result: AnalysisResult,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    fos_abs_error = abs(result.fos - case.expected_fos)
    driving_rel_error = _relative_error(result.driving_moment, case.expected_driving_moment)
    resisting_rel_error = _relative_error(result.resisting_moment, case.expected_resisting_moment)

    hard_checks = {
        "fos_abs_error": {
            "value": fos_abs_error,
            "tolerance": case.fos_tolerance,
            "expected": case.expected_fos,
            "passed": fos_abs_error <= case.fos_tolerance,
        },
        "driving_rel_error": {
            "value": driving_rel_error,
            "tolerance": case.moment_rel_tolerance,
            "expected": case.expected_driving_moment,
            "passed": driving_rel_error <= case.moment_rel_tolerance,
        },
        "resisting_rel_error": {
            "value": resisting_rel_error,
            "tolerance": case.moment_rel_tolerance,
            "expected": case.expected_resisting_moment,
            "passed": resisting_rel_error <= case.moment_rel_tolerance,
        },
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


def run_verification_suite() -> list[VerificationOutcome]:
    outcomes: list[VerificationOutcome] = []

    for case in VERIFICATION_CASES:
        result = run_analysis(case.project)
        if isinstance(case, PrescribedVerificationCase):
            hard_checks, diagnostics, passed = _evaluate_prescribed_case(case, result)
        elif isinstance(case, AutoRefineVerificationCase):
            hard_checks, diagnostics, passed = _evaluate_auto_refine_case(case, result)
        elif isinstance(case, GlobalSearchBenchmarkVerificationCase):
            hard_checks, diagnostics, passed = _evaluate_global_search_benchmark_case(case, result)
        else:
            raise TypeError(f"Unsupported verification case type: {type(case)!r}")

        outcomes.append(
            VerificationOutcome(
                name=case.name,
                case_type=case.case_type,
                result=result,
                hard_checks=hard_checks,
                diagnostics=diagnostics,
                passed=passed,
            )
        )

    return outcomes
