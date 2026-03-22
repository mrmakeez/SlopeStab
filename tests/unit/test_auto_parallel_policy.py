from __future__ import annotations

import json
import pathlib
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import parse_project_input
from slope_stab.search.auto_parallel_policy import (
    REASON_FORCED_PARALLEL_MODE,
    REASON_FORCED_SERIAL_MODE,
    REASON_POLICY_THRESHOLD_PARALLEL,
    REASON_POLICY_THRESHOLD_SERIAL,
    REASON_PRESCRIBED_ANALYSIS_SERIAL,
    REASON_THREAD_BACKEND_DEFAULT_SERIAL,
    REASON_THREAD_BACKEND_WHITELIST_PARALLEL,
    REASON_UNSUPPORTED_BATCHING_SERIAL,
    REASON_UNSUPPORTED_WORKLOAD_SERIAL,
    REASON_WORKERS_LE_ONE_SERIAL,
    classify_batching,
    classify_workload,
    effective_cpu_count,
    resolve_requested_workers,
)


def _load_fixture_payload(name: str) -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    return json.loads((root / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


def _set_parallel(payload: dict, *, mode: str, workers: int, min_batch_size: int = 1) -> dict:
    out = dict(payload)
    out["search"] = dict(payload["search"])
    out["search"]["parallel"] = {
        "mode": mode,
        "workers": workers,
        "min_batch_size": min_batch_size,
    }
    return out


class AutoParallelPolicyHelperTests(unittest.TestCase):
    def test_effective_cpu_count_is_at_least_one(self) -> None:
        self.assertGreaterEqual(effective_cpu_count(), 1)

    def test_resolve_requested_workers_rules(self) -> None:
        self.assertEqual(resolve_requested_workers(0, 8), 4)
        self.assertEqual(resolve_requested_workers(0, 3), 3)
        self.assertEqual(resolve_requested_workers(99, 6), 6)
        self.assertEqual(resolve_requested_workers(1, 6), 1)

    def test_classify_batching_threshold(self) -> None:
        self.assertEqual(classify_batching(8), "default_batching")
        self.assertEqual(classify_batching(9), "restricted_batching")

    def test_classify_workload_cmaes_composite_proxy(self) -> None:
        payload = _load_fixture_payload("case2_cmaes_global.json")
        payload["search"]["cmaes_global_circular"]["max_evaluations"] = 15000
        payload["search"]["cmaes_global_circular"]["cmaes_population_size"] = 20
        payload["search"]["cmaes_global_circular"]["cmaes_max_iterations"] = 300
        payload["search"]["cmaes_global_circular"]["cmaes_restarts"] = 3
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        workload = classify_workload(project.search, project.analysis.method)
        self.assertEqual(workload, "large")


class AutoParallelResolutionTests(unittest.TestCase):
    def test_prescribed_analysis_emits_serial_reason(self) -> None:
        project = parse_project_input(_load_fixture_payload("case1.json"))
        result = run_analysis(project)
        parallel_meta = result.metadata["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "serial")
        self.assertEqual(parallel_meta["resolved_mode"], "serial")
        self.assertEqual(parallel_meta["decision_reason"], REASON_PRESCRIBED_ANALYSIS_SERIAL)

    def test_single_core_auto_resolves_serial(self) -> None:
        payload = _load_fixture_payload("case3_auto_refine.json")
        project = parse_project_input(payload)
        with patch("slope_stab.analysis.effective_cpu_count", return_value=1):
            result = run_analysis(project)
        parallel_meta = result.metadata["search"]["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "auto")
        self.assertEqual(parallel_meta["resolved_mode"], "serial")
        self.assertEqual(parallel_meta["decision_reason"], REASON_WORKERS_LE_ONE_SERIAL)

    def test_workers_zero_rule_is_deterministic(self) -> None:
        payload = _set_parallel(_load_fixture_payload("case3_auto_refine.json"), mode="serial", workers=0)
        project = parse_project_input(payload)
        with patch("slope_stab.analysis.effective_cpu_count", return_value=6):
            result = run_analysis(project)
        parallel_meta = result.metadata["search"]["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "serial")
        self.assertEqual(parallel_meta["requested_workers"], 4)
        self.assertEqual(parallel_meta["decision_reason"], REASON_FORCED_SERIAL_MODE)

    def test_explicit_worker_overrequest_clamps(self) -> None:
        payload = _set_parallel(_load_fixture_payload("case3_auto_refine.json"), mode="parallel", workers=99)
        project = parse_project_input(payload)
        with patch("slope_stab.analysis.effective_cpu_count", return_value=3):
            result = run_analysis(project)
        parallel_meta = result.metadata["search"]["parallel"]
        self.assertEqual(parallel_meta["requested_mode"], "parallel")
        self.assertEqual(parallel_meta["requested_workers"], 3)
        self.assertEqual(parallel_meta["resolved_workers"], 3)
        self.assertEqual(parallel_meta["decision_reason"], REASON_FORCED_PARALLEL_MODE)

    def test_thread_backend_defaults_to_serial_for_auto_mode(self) -> None:
        class _ThreadExecutor:
            backend = "thread"

            def __init__(self, *args: object, **kwargs: object) -> None:
                _ = (args, kwargs)

            def __enter__(self) -> "_ThreadExecutor":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                _ = (exc_type, exc, tb)
                return False

            def evaluate_surfaces(self, *args: object, **kwargs: object) -> list[object]:
                raise AssertionError("Thread fallback in auto mode must resolve serial before batch evaluation.")

        payload = _set_parallel(_load_fixture_payload("case3_auto_refine.json"), mode="auto", workers=0)
        project = parse_project_input(payload)
        with (
            patch("slope_stab.analysis.effective_cpu_count", return_value=4),
            patch("slope_stab.analysis.process_policy_allows_parallel", return_value=True),
            patch("slope_stab.analysis.ParallelSurfaceExecutor", _ThreadExecutor),
        ):
            result = run_analysis(project)
        parallel_meta = result.metadata["search"]["parallel"]
        self.assertEqual(parallel_meta["resolved_mode"], "serial")
        self.assertEqual(parallel_meta["decision_reason"], REASON_THREAD_BACKEND_DEFAULT_SERIAL)
        self.assertEqual(parallel_meta["backend"], "thread")

    def test_parallel_metadata_contract_and_reason_enum(self) -> None:
        payload = _set_parallel(_load_fixture_payload("case3_auto_refine.json"), mode="auto", workers=0, min_batch_size=9)
        project = parse_project_input(payload)
        with patch("slope_stab.analysis.effective_cpu_count", return_value=6):
            result = run_analysis(project)

        parallel_meta = result.metadata["search"]["parallel"]
        required_fields = {
            "requested_mode",
            "resolved_mode",
            "decision_reason",
            "evidence_version",
            "backend",
            "requested_workers",
            "resolved_workers",
            "workload_class",
            "batching_class",
            "min_batch_size",
            "timeout_seconds",
        }
        self.assertTrue(required_fields.issubset(parallel_meta.keys()))
        self.assertEqual(parallel_meta["batching_class"], classify_batching(9))
        self.assertIn(
            parallel_meta["decision_reason"],
            {
                REASON_PRESCRIBED_ANALYSIS_SERIAL,
                REASON_FORCED_SERIAL_MODE,
                REASON_FORCED_PARALLEL_MODE,
                REASON_WORKERS_LE_ONE_SERIAL,
                REASON_THREAD_BACKEND_DEFAULT_SERIAL,
                REASON_THREAD_BACKEND_WHITELIST_PARALLEL,
                REASON_UNSUPPORTED_WORKLOAD_SERIAL,
                REASON_UNSUPPORTED_BATCHING_SERIAL,
                REASON_POLICY_THRESHOLD_PARALLEL,
                REASON_POLICY_THRESHOLD_SERIAL,
            },
        )


if __name__ == "__main__":
    unittest.main()
