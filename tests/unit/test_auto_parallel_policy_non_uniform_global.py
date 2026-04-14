from __future__ import annotations

import json
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.io.json_io import parse_project_input
from slope_stab.search.auto_parallel_policy import classify_workload, process_policy_allows_parallel


def _load_fixture_payload(name: str) -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    return json.loads((root / "tests" / "fixtures" / "non_uniform" / name).read_text(encoding="utf-8"))


class NonUniformGlobalAutoParallelPolicyTests(unittest.TestCase):
    def test_non_uniform_direct_global_policy_allows_parallel(self) -> None:
        project = parse_project_input(_load_fixture_payload("case11_direct_global_bishop.json"))
        self.assertIsNotNone(project.search)
        workload = classify_workload(project.search, project.analysis.method)
        self.assertTrue(
            process_policy_allows_parallel(
                search_method=project.search.method,
                analysis_method=project.analysis.method,
                workload_class=workload,
                batching_class="default_batching",
                is_non_uniform=True,
            )
        )
        self.assertFalse(
            process_policy_allows_parallel(
                search_method=project.search.method,
                analysis_method=project.analysis.method,
                workload_class=workload,
                batching_class="default_batching",
                is_non_uniform=False,
            )
        )

    def test_non_uniform_cuckoo_global_policy_allows_parallel(self) -> None:
        project = parse_project_input(_load_fixture_payload("case12_water_surcharge_cuckoo_global_spencer_seed0.json"))
        self.assertIsNotNone(project.search)
        workload = classify_workload(project.search, project.analysis.method)
        self.assertTrue(
            process_policy_allows_parallel(
                search_method=project.search.method,
                analysis_method=project.analysis.method,
                workload_class=workload,
                batching_class="default_batching",
                is_non_uniform=True,
            )
        )

    def test_non_uniform_cmaes_global_policy_allows_parallel(self) -> None:
        project = parse_project_input(_load_fixture_payload("case11_cmaes_global_bishop_seed1.json"))
        self.assertIsNotNone(project.search)
        workload = classify_workload(project.search, project.analysis.method)
        self.assertTrue(
            process_policy_allows_parallel(
                search_method=project.search.method,
                analysis_method=project.analysis.method,
                workload_class=workload,
                batching_class="default_batching",
                is_non_uniform=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
