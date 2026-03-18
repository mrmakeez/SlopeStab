from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, PrescribedCircleInput
from slope_stab.search.common import (
    CACHE_ROUND,
    SurfaceEvaluator,
    Vector3,
    evaluate_surface_candidate,
    is_better_score,
    map_vector_to_surface,
    round_vector,
)


@dataclass(frozen=True)
class ObjectiveScoringPolicy:
    repair_vector: Callable[[Vector3], Vector3]
    invalid_geometry_score: float
    invalid_result_score: float | None = None
    evaluation_exception_score: float | None = None
    keep_invalid_payload: bool = False


@dataclass(frozen=True)
class ObjectiveEvaluation:
    score: float
    surface: PrescribedCircleInput | None
    result: AnalysisResult | None
    valid: bool
    reason: str
    vector: Vector3


def _identity_vector(vector: Vector3) -> Vector3:
    return vector


class CachedObjectiveEvaluator:
    def __init__(
        self,
        profile: UniformSlopeProfile,
        x_min: float,
        x_max: float,
        max_evaluations: int,
        evaluate_surface: SurfaceEvaluator,
        policy: ObjectiveScoringPolicy,
        driving_moment_tol: float = 1e-9,
    ) -> None:
        self.profile = profile
        self.x_min = x_min
        self.x_max = x_max
        self.max_evaluations = max_evaluations
        self.evaluate_surface = evaluate_surface
        self.policy = policy
        self.driving_moment_tol = driving_moment_tol

        self.cache: dict[Vector3, ObjectiveEvaluation] = {}
        self.total_evaluations = 0
        self.valid_evaluations = 0
        self.infeasible_evaluations = 0
        self.best_surface: PrescribedCircleInput | None = None
        self.best_result: AnalysisResult | None = None
        self.best_score = float("inf")
        self.best_vector: Vector3 | None = None

    def _score_for_reason(self, reason: str) -> float:
        if reason == "invalid_geometry":
            return self.policy.invalid_geometry_score
        if reason == "evaluation_exception":
            if self.policy.evaluation_exception_score is not None:
                return self.policy.evaluation_exception_score
            if self.policy.invalid_result_score is not None:
                return self.policy.invalid_result_score
            return self.policy.invalid_geometry_score
        if self.policy.invalid_result_score is not None:
            return self.policy.invalid_result_score
        return self.policy.invalid_geometry_score

    def _normalize(self, vector: Vector3) -> Vector3:
        return round_vector(self.policy.repair_vector(vector), digits=CACHE_ROUND)

    def evaluate_vector(self, vector: Vector3) -> ObjectiveEvaluation:
        key = self._normalize(vector)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if self.total_evaluations >= self.max_evaluations:
            evaluation = ObjectiveEvaluation(
                score=self.policy.invalid_geometry_score,
                surface=None,
                result=None,
                valid=False,
                reason="max_evaluations",
                vector=key,
            )
            self.cache[key] = evaluation
            return evaluation

        self.total_evaluations += 1
        surface = map_vector_to_surface(
            profile=self.profile,
            x_min=self.x_min,
            x_max=self.x_max,
            vector=key,
            repair_vector=_identity_vector,
        )
        candidate = evaluate_surface_candidate(
            surface,
            self.evaluate_surface,
            driving_moment_tol=self.driving_moment_tol,
        )

        if not candidate.valid or candidate.surface is None or candidate.result is None:
            self.infeasible_evaluations += 1
            payload_surface = candidate.surface if self.policy.keep_invalid_payload else None
            payload_result = candidate.result if self.policy.keep_invalid_payload else None
            evaluation = ObjectiveEvaluation(
                score=self._score_for_reason(candidate.reason),
                surface=payload_surface,
                result=payload_result,
                valid=False,
                reason=candidate.reason,
                vector=key,
            )
            self.cache[key] = evaluation
            return evaluation

        evaluation = ObjectiveEvaluation(
            score=candidate.result.fos,
            surface=candidate.surface,
            result=candidate.result,
            valid=True,
            reason="valid",
            vector=key,
        )
        self.cache[key] = evaluation
        self.valid_evaluations += 1
        self._update_incumbent(evaluation)
        return evaluation

    def _update_incumbent(self, evaluation: ObjectiveEvaluation) -> None:
        if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
            return
        if is_better_score(evaluation.score, evaluation.surface, self.best_score, self.best_surface):
            self.best_surface = evaluation.surface
            self.best_result = evaluation.result
            self.best_score = evaluation.score
            self.best_vector = evaluation.vector

    def valid_points(self) -> list[tuple[Vector3, ObjectiveEvaluation]]:
        return [
            (key, value)
            for key, value in self.cache.items()
            if value.valid and value.surface is not None and value.result is not None
        ]
