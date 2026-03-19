from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult
from slope_stab.search.common import repair_vector_clip
from slope_stab.search.objective_evaluator import CachedObjectiveEvaluator, ObjectiveScoringPolicy


def _fake_evaluate_surface(score_shift: float):
    def _eval(surface):
        fos = score_shift + surface.x_left + 0.01 * surface.x_right
        return AnalysisResult(
            fos=fos,
            converged=True,
            iterations=1,
            residual=0.0,
            driving_moment=10.0,
            resisting_moment=10.0 * fos,
        )

    return _eval


class ObjectiveEvaluatorBatchTests(unittest.TestCase):
    def test_batch_semantics_match_serial(self) -> None:
        profile = UniformSlopeProfile(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0)
        policy = ObjectiveScoringPolicy(
            repair_vector=repair_vector_clip,
            invalid_geometry_score=float("inf"),
            invalid_result_score=float("inf"),
            evaluation_exception_score=float("inf"),
            keep_invalid_payload=False,
        )
        vectors = [
            (0.10, 0.20, 0.30),
            (0.50, 0.10, 0.80),
            (0.10, 0.20, 0.30),  # duplicate key
            (0.70, 0.60, 0.50),
            (0.90, 0.90, 0.10),  # budget overflow
        ]

        serial = CachedObjectiveEvaluator(
            profile=profile,
            x_min=20.0,
            x_max=70.0,
            max_evaluations=3,
            evaluate_surface=_fake_evaluate_surface(1.0),
            policy=policy,
        )
        serial_results = [serial.evaluate_vector(v) for v in vectors]

        batch = CachedObjectiveEvaluator(
            profile=profile,
            x_min=20.0,
            x_max=70.0,
            max_evaluations=3,
            evaluate_surface=_fake_evaluate_surface(1.0),
            policy=policy,
        )
        batch_results = batch.evaluate_vectors_batch(vectors)

        self.assertEqual([r.reason for r in serial_results], [r.reason for r in batch_results])
        self.assertEqual([r.valid for r in serial_results], [r.valid for r in batch_results])
        self.assertEqual([r.score for r in serial_results], [r.score for r in batch_results])
        self.assertEqual(serial.total_evaluations, batch.total_evaluations)
        self.assertEqual(serial.valid_evaluations, batch.valid_evaluations)
        self.assertEqual(serial.infeasible_evaluations, batch.infeasible_evaluations)
        self.assertEqual(serial.best_score, batch.best_score)
        self.assertEqual(serial.best_vector, batch.best_vector)

    def test_batch_callback_payload_count_mismatch_fails(self) -> None:
        profile = UniformSlopeProfile(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0)
        policy = ObjectiveScoringPolicy(
            repair_vector=repair_vector_clip,
            invalid_geometry_score=float("inf"),
            invalid_result_score=float("inf"),
            evaluation_exception_score=float("inf"),
            keep_invalid_payload=False,
        )

        evaluator = CachedObjectiveEvaluator(
            profile=profile,
            x_min=20.0,
            x_max=70.0,
            max_evaluations=5,
            evaluate_surface=_fake_evaluate_surface(0.0),
            policy=policy,
            batch_evaluate_surfaces=lambda surfaces, _tol: [],
            min_batch_size=1,
        )

        with self.assertRaises(RuntimeError):
            evaluator.evaluate_vectors_batch([(0.1, 0.2, 0.3), (0.2, 0.3, 0.4)])


if __name__ == "__main__":
    unittest.main()
