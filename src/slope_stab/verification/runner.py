from __future__ import annotations

from dataclasses import dataclass

from slope_stab.analysis import run_analysis
from slope_stab.models import AnalysisResult
from slope_stab.verification.cases import VERIFICATION_CASES


@dataclass(frozen=True)
class VerificationOutcome:
    name: str
    result: AnalysisResult
    fos_abs_error: float
    driving_rel_error: float
    resisting_rel_error: float
    passed: bool


def run_verification_suite() -> list[VerificationOutcome]:
    outcomes: list[VerificationOutcome] = []

    for case in VERIFICATION_CASES:
        result = run_analysis(case.project)
        fos_abs_error = abs(result.fos - case.expected_fos)
        driving_rel_error = abs(result.driving_moment - case.expected_driving_moment) / case.expected_driving_moment
        resisting_rel_error = abs(result.resisting_moment - case.expected_resisting_moment) / case.expected_resisting_moment

        passed = (
            fos_abs_error <= case.fos_tolerance
            and driving_rel_error <= case.moment_rel_tolerance
            and resisting_rel_error <= case.moment_rel_tolerance
        )

        outcomes.append(
            VerificationOutcome(
                name=case.name,
                result=result,
                fos_abs_error=fos_abs_error,
                driving_rel_error=driving_rel_error,
                resisting_rel_error=resisting_rel_error,
                passed=passed,
            )
        )

    return outcomes
