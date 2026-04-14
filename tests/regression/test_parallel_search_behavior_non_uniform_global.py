from __future__ import annotations

import copy
import json
import pathlib
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import parse_project_input
from slope_stab.search.common import evaluate_surface_candidate
from slope_stab.search.surface_solver import solve_surface_for_context


def _load_fixture_payload(name: str) -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    return json.loads((root / "tests" / "fixtures" / "non_uniform" / name).read_text(encoding="utf-8"))


def _set_parallel(
    payload: dict,
    *,
    mode: str,
    workers: int,
    min_batch_size: int = 1,
) -> dict:
    out = copy.deepcopy(payload)
    out.setdefault("search", {})
    out["search"]["parallel"] = {
        "mode": mode,
        "workers": workers,
        "min_batch_size": min_batch_size,
    }
    return out


class _FakeProcessExecutor:
    backend = "process"

    def __init__(self, *, context, workers, timeout_seconds=None):
        self._context = context
        _ = (workers, timeout_seconds)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def evaluate_surfaces(self, surfaces, driving_moment_tol):
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


class NonUniformGlobalParallelBehaviorTests(unittest.TestCase):
    def test_non_uniform_global_auto_mode_parallel_matches_serial(self) -> None:
        cases = (
            ("case11_direct_global_bishop.json", True),
            ("case11_cmaes_global_bishop_seed1.json", False),
            ("case12_water_surcharge_cuckoo_global_spencer_seed0.json", False),
        )
        for fixture_name, deterministic in cases:
            with self.subTest(fixture=fixture_name):
                payload = _load_fixture_payload(fixture_name)
                serial_project = parse_project_input(_set_parallel(payload, mode="serial", workers=1))
                auto_project = parse_project_input(_set_parallel(payload, mode="auto", workers=0))

                serial = run_analysis(serial_project)
                with (
                    patch("slope_stab.analysis.effective_cpu_count", return_value=6),
                    patch("slope_stab.analysis.ParallelSurfaceExecutor", _FakeProcessExecutor),
                ):
                    auto_mode = run_analysis(auto_project)

                if deterministic:
                    self.assertAlmostEqual(serial.fos, auto_mode.fos, places=12)
                else:
                    self.assertAlmostEqual(serial.fos, auto_mode.fos, delta=1e-9)
                self.assertEqual(serial.metadata["prescribed_surface"], auto_mode.metadata["prescribed_surface"])
                self.assertEqual(auto_mode.metadata["search"]["parallel"]["requested_mode"], "auto")
                self.assertEqual(auto_mode.metadata["search"]["parallel"]["resolved_mode"], "parallel")
                self.assertEqual(auto_mode.metadata["search"]["parallel"]["decision_reason"], "policy_threshold_parallel")
                self.assertEqual(auto_mode.metadata["search"]["parallel"]["backend"], "process")

    def test_non_uniform_seeded_global_repeatability_is_pinned(self) -> None:
        for fixture_name in (
            "case11_cmaes_global_bishop_seed1.json",
            "case12_water_surcharge_cuckoo_global_spencer_seed0.json",
        ):
            with self.subTest(fixture=fixture_name):
                payload = _load_fixture_payload(fixture_name)
                project = parse_project_input(_set_parallel(payload, mode="serial", workers=1))
                first = run_analysis(project)
                second = run_analysis(project)
                self.assertAlmostEqual(first.fos, second.fos, delta=1e-9)
                self.assertEqual(first.metadata["prescribed_surface"], second.metadata["prescribed_surface"])


if __name__ == "__main__":
    unittest.main()
