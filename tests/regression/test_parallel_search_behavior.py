from __future__ import annotations

import copy
import json
import pathlib
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.exceptions import ParallelExecutionError
from slope_stab.io.json_io import parse_project_input
from slope_stab.search.common import evaluate_surface_candidate
from slope_stab.search.surface_solver import solve_surface_for_context


def _load_fixture_payload(name: str) -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    return json.loads((root / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


def _set_parallel(
    payload: dict,
    *,
    mode: str,
    workers: int,
    min_batch_size: int,
    timeout_seconds: float | None = None,
) -> dict:
    out = copy.deepcopy(payload)
    out.setdefault("search", {})
    out["search"]["parallel"] = {
        "mode": mode,
        "workers": workers,
        "min_batch_size": min_batch_size,
    }
    if timeout_seconds is not None:
        out["search"]["parallel"]["timeout_seconds"] = timeout_seconds
    return out


class _FakeProcessExecutor:
    backend = "process"

    def __init__(self, *, context, workers, timeout_seconds=None):
        self._context = context
        self._timeout_seconds = timeout_seconds

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def evaluate_surfaces(self, surfaces, driving_moment_tol):
        if self._timeout_seconds is not None and self._timeout_seconds < 1e-9:
            raise ParallelExecutionError("Parallel worker timed out while evaluating task 0.")
        evaluations = []
        for surface in surfaces:
            evaluations.append(
                evaluate_surface_candidate(
                    surface,
                    lambda current: solve_surface_for_context(self._context, current),
                    driving_moment_tol=driving_moment_tol,
                )
            )
        return evaluations


class ParallelSearchBehaviorTests(unittest.TestCase):
    def test_auto_refine_parallel_matches_serial(self) -> None:
        payload = _load_fixture_payload("case3_auto_refine.json")
        serial_project = parse_project_input(_set_parallel(payload, mode="serial", workers=1, min_batch_size=1))
        parallel_project = parse_project_input(_set_parallel(payload, mode="parallel", workers=2, min_batch_size=8))

        serial = run_analysis(serial_project)
        with patch("slope_stab.analysis.ParallelSurfaceExecutor", _FakeProcessExecutor):
            parallel = run_analysis(parallel_project)

        self.assertAlmostEqual(serial.fos, parallel.fos, places=12)
        self.assertEqual(serial.metadata["prescribed_surface"], parallel.metadata["prescribed_surface"])
        self.assertEqual(serial.metadata["search"]["iteration_diagnostics"], parallel.metadata["search"]["iteration_diagnostics"])
        self.assertEqual(serial.metadata["search"]["valid_surfaces"], parallel.metadata["search"]["valid_surfaces"])
        self.assertEqual(serial.metadata["search"]["invalid_surfaces"], parallel.metadata["search"]["invalid_surfaces"])
        self.assertEqual(serial.metadata["search"]["parallel"]["requested_mode"], "serial")
        self.assertEqual(serial.metadata["search"]["parallel"]["resolved_mode"], "serial")
        self.assertEqual(serial.metadata["search"]["parallel"]["decision_reason"], "forced_serial_mode")
        self.assertEqual(parallel.metadata["search"]["parallel"]["requested_mode"], "parallel")
        self.assertEqual(parallel.metadata["search"]["parallel"]["resolved_mode"], "parallel")
        self.assertEqual(parallel.metadata["search"]["parallel"]["decision_reason"], "forced_parallel_mode")

    def test_cmaes_parallel_matches_serial_for_fixed_seed(self) -> None:
        payload = _load_fixture_payload("case2_cmaes_global.json")
        serial_project = parse_project_input(_set_parallel(payload, mode="serial", workers=1, min_batch_size=1))
        parallel_project = parse_project_input(_set_parallel(payload, mode="parallel", workers=2, min_batch_size=4))

        serial = run_analysis(serial_project)
        with patch("slope_stab.analysis.ParallelSurfaceExecutor", _FakeProcessExecutor):
            parallel = run_analysis(parallel_project)

        self.assertAlmostEqual(serial.fos, parallel.fos, places=5)
        serial_surface = serial.metadata["prescribed_surface"]
        parallel_surface = parallel.metadata["prescribed_surface"]
        for key in ("x_left", "y_left", "x_right", "y_right", "xc", "yc", "r"):
            self.assertLessEqual(abs(float(serial_surface[key]) - float(parallel_surface[key])), 0.01)
        # Slide2 Case2_Search (bishop simplified) global minimum + benchmark margin.
        self.assertLessEqual(serial.fos, 2.10296 + 0.01)
        self.assertLessEqual(parallel.fos, 2.10296 + 0.01)
        self.assertEqual(serial.metadata["search"]["parallel"]["decision_reason"], "forced_serial_mode")
        self.assertEqual(parallel.metadata["search"]["parallel"]["decision_reason"], "forced_parallel_mode")

    def test_parallel_worker_timeout_raises_error(self) -> None:
        payload = _load_fixture_payload("case3_auto_refine.json")
        timeout_project = parse_project_input(
            _set_parallel(
                payload,
                mode="parallel",
                workers=2,
                min_batch_size=1,
                timeout_seconds=1e-12,
            )
        )

        with patch("slope_stab.analysis.ParallelSurfaceExecutor", _FakeProcessExecutor):
            with self.assertRaises(ParallelExecutionError):
                run_analysis(timeout_project)


if __name__ == "__main__":
    unittest.main()
