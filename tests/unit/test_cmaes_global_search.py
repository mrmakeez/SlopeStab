from __future__ import annotations

from dataclasses import dataclass, field, replace
import sys
import types
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, CmaesGlobalSearchInput, PrescribedCircleInput, SearchLimitsInput
from slope_stab.search.cmaes_global import _run_cmaes_stage, _run_direct_prescan, _toe_locked_sweep
from slope_stab.search.objective_evaluator import ObjectiveEvaluation


def _make_config() -> CmaesGlobalSearchInput:
    return CmaesGlobalSearchInput(
        max_evaluations=200,
        direct_prescan_evaluations=50,
        cmaes_population_size=8,
        cmaes_max_iterations=2,
        cmaes_restarts=0,
        cmaes_sigma0=0.15,
        polish_max_evaluations=10,
        min_improvement=1e-4,
        stall_iterations=5,
        seed=1,
        post_polish=False,
        invalid_penalty=1e6,
        nonconverged_penalty=1e5,
        search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
    )


def _fake_surface(vector: tuple[float, float, float]) -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=10.0 + vector[0],
        yc=20.0 + vector[1],
        r=30.0 + vector[2],
        x_left=1.0 + vector[0],
        y_left=2.0 + vector[1],
        x_right=3.0 + vector[2],
        y_right=4.0 + vector[0],
    )


def _fake_result(score: float) -> AnalysisResult:
    return AnalysisResult(
        fos=score,
        converged=True,
        iterations=1,
        residual=0.0,
        driving_moment=1.0,
        resisting_moment=max(score, 1e-9),
    )


@dataclass
class _FakePrescanEvaluator:
    total_evaluations: int = 0
    valid_evaluations: int = 0
    infeasible_evaluations: int = 0
    best_vector: tuple[float, float, float] | None = None
    best_result: AnalysisResult | None = None

    def __post_init__(self) -> None:
        self._points: dict[tuple[float, float, float], ObjectiveEvaluation] = {}

    def evaluate_vectors_batch(self, vectors: list[tuple[float, float, float]]) -> list[ObjectiveEvaluation]:
        evaluations: list[ObjectiveEvaluation] = []
        for index, vector in enumerate(vectors, start=1):
            self.total_evaluations += 1
            self.valid_evaluations += 1
            result = _fake_result(float(index))
            evaluation = ObjectiveEvaluation(
                score=result.fos,
                surface=_fake_surface(vector),
                result=result,
                valid=True,
                reason="valid",
                vector=vector,
            )
            self._points[vector] = evaluation
            if self.best_result is None or result.fos < self.best_result.fos:
                self.best_result = result
                self.best_vector = vector
            evaluations.append(evaluation)
        return evaluations

    def valid_points(self):
        return list(self._points.items())


@dataclass
class _FakeBudgetEvaluator:
    total_evaluations: int = 27
    best_score: float = 1.0
    valid_evaluations: int = 1
    infeasible_evaluations: int = 0
    best_vector: tuple[float, float, float] | None = (0.5, 0.5, 0.5)
    best_surface: PrescribedCircleInput | None = field(
        default_factory=lambda: PrescribedCircleInput(0.0, 2.0, 3.0, 0.0, 0.0, 1.0, 0.0)
    )
    best_result: AnalysisResult | None = field(
        default_factory=lambda: AnalysisResult(
            fos=1.0,
            converged=True,
            iterations=1,
            residual=0.0,
            driving_moment=1.0,
            resisting_moment=1.0,
        )
    )

    def evaluate_vectors_batch(self, vectors: list[tuple[float, float, float]]) -> list[ObjectiveEvaluation]:
        evaluations: list[ObjectiveEvaluation] = []
        for index, vector in enumerate(vectors, start=1):
            if self.total_evaluations < 28:
                self.total_evaluations += 1
            evaluations.append(
                ObjectiveEvaluation(
                    score=float(index),
                    surface=self.best_surface,
                    result=self.best_result,
                    valid=True,
                    reason="valid",
                    vector=vector,
                )
            )
        return evaluations


class _FakeEvolutionStrategy:
    tell_called = False

    def __init__(self, x0, sigma0, opts):
        _ = (x0, sigma0, opts)
        self.sigma = 0.2

    def ask(self):
        return [[0.1, 0.2, 0.3] for _ in range(8)]

    def tell(self, repaired, scores):
        type(self).tell_called = True
        _ = (repaired, scores)


class CmaesGlobalSearchUnitTests(unittest.TestCase):
    def test_direct_prescan_honors_small_budget(self) -> None:
        evaluator = _FakePrescanEvaluator()
        diagnostics = []
        config = _make_config()
        config = replace(config, direct_prescan_evaluations=1)

        elites, reason = _run_direct_prescan(evaluator, config, diagnostics)

        self.assertEqual(reason, "direct_budget_reached")
        self.assertEqual(evaluator.total_evaluations, 1)
        self.assertEqual(len(elites), 1)
        self.assertTrue(diagnostics)
        self.assertEqual(diagnostics[0].stage, "direct")
        self.assertEqual(diagnostics[0].total_evaluations, 1)

    def test_cma_stage_stops_cleanly_when_budget_is_exhausted_mid_generation(self) -> None:
        evaluator = _FakeBudgetEvaluator()
        diagnostics = []
        config = _make_config()
        config = replace(config, max_evaluations=28, direct_prescan_evaluations=27)
        fake_cma = types.SimpleNamespace(CMAEvolutionStrategy=_FakeEvolutionStrategy)
        _FakeEvolutionStrategy.tell_called = False

        with patch.dict(sys.modules, {"cma": fake_cma}):
            reason = _run_cmaes_stage(evaluator, config, [(0.5, 0.5, 0.5)], diagnostics)

        self.assertEqual(reason, "max_evaluations")
        self.assertFalse(_FakeEvolutionStrategy.tell_called)
        self.assertTrue(diagnostics)
        self.assertTrue(diagnostics[0].extra["partial_generation"])
        self.assertEqual(diagnostics[0].extra["population_size"], 1)

    def test_toe_locked_sweep_tracks_beta_for_winning_candidate(self) -> None:
        profile = UniformSlopeProfile(h=10.0, l=20.0, x_toe=30.0, y_toe=0.0)
        best_surface = PrescribedCircleInput(xc=0.0, yc=10.0, r=9.0, x_left=30.0, y_left=0.0, x_right=50.0, y_right=10.0)
        best_result = AnalysisResult(
            fos=10.0,
            converged=True,
            iterations=1,
            residual=0.0,
            driving_moment=1.0,
            resisting_moment=10.0,
        )

        def evaluate_surface(surface: PrescribedCircleInput) -> AnalysisResult:
            fos_by_beta = {0.2: 2.0, 0.4: 1.0, 0.6: 3.0}
            fos = fos_by_beta[round(surface.r, 1)]
            return AnalysisResult(
                fos=fos,
                converged=True,
                iterations=1,
                residual=0.0,
                driving_moment=1.0,
                resisting_moment=fos,
            )

        with patch(
            "slope_stab.search.cmaes_global.circle_from_endpoints_and_tangent",
            side_effect=lambda p_left, p_right, beta: PrescribedCircleInput(
                xc=0.0,
                yc=10.0,
                r=beta,
                x_left=p_left[0],
                y_left=p_left[1],
                x_right=p_right[0],
                y_right=p_right[1],
            ),
        ):
            out_surface, out_result, improved_x, improved_beta = _toe_locked_sweep(
                profile=profile,
                evaluate_surface=evaluate_surface,
                batch_evaluate_surfaces=None,
                min_batch_size=1,
                best_surface=best_surface,
                best_result=best_result,
                x_left=30.0,
                y_left=0.0,
                right_values=[55.0],
                beta_values=[0.2, 0.4, 0.6],
            )

        self.assertEqual(improved_x, 55.0)
        self.assertAlmostEqual(improved_beta, 0.4)
        self.assertAlmostEqual(out_result.fos, 1.0)
        self.assertAlmostEqual(out_surface.r, 0.4)


if __name__ == "__main__":
    unittest.main()
