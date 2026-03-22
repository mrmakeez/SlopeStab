from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


ROOT = _repo_root()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from slope_stab.analysis import run_analysis  # noqa: E402
from slope_stab.io.json_io import parse_project_input  # noqa: E402
from slope_stab.search.auto_parallel_policy import EVIDENCE_VERSION, effective_cpu_count  # noqa: E402


DEFAULT_FIXTURES: tuple[str, ...] = (
    "tests/fixtures/case3_auto_refine.json",
    "tests/fixtures/case3_auto_refine_spencer.json",
    "tests/fixtures/case2_cmaes_global.json",
    "tests/fixtures/case2_cmaes_global_spencer.json",
)
DEFAULT_MODES: tuple[str, ...] = ("serial", "auto", "parallel")
MODE_WORKERS: dict[str, int] = {"serial": 1, "auto": 0, "parallel": 0}


def _load_payload(path: str) -> dict[str, Any]:
    fixture_path = ROOT / path
    with fixture_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Fixture root must be a JSON object: {path}")
    return payload


def _with_parallel_mode(payload: dict[str, Any], mode: str, workers: int) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    search = out.get("search")
    if not isinstance(search, dict):
        raise ValueError("Benchmark fixture must contain a search object.")
    parallel = search.get("parallel")
    if not isinstance(parallel, dict):
        parallel = {}
        search["parallel"] = parallel
    parallel["mode"] = mode
    parallel["workers"] = workers
    return out


def _run_single(fixture: str, mode: str, workers: int) -> dict[str, Any]:
    payload = _load_payload(fixture)
    configured_payload = _with_parallel_mode(payload, mode=mode, workers=workers)
    started = time.perf_counter()
    project = parse_project_input(configured_payload)
    result = run_analysis(project)
    elapsed = time.perf_counter() - started
    search_meta = result.metadata.get("search", {})
    parallel_meta = search_meta.get("parallel", {})
    return {
        "fixture": fixture,
        "analysis_method": configured_payload.get("analysis", {}).get("method"),
        "search_method": configured_payload.get("search", {}).get("method"),
        "requested_mode": mode,
        "requested_workers_input": workers,
        "elapsed_seconds": elapsed,
        "fos": result.fos,
        "resolved_mode": parallel_meta.get("resolved_mode"),
        "decision_reason": parallel_meta.get("decision_reason"),
        "backend": parallel_meta.get("backend"),
        "requested_workers_resolved": parallel_meta.get("requested_workers"),
        "resolved_workers": parallel_meta.get("resolved_workers"),
        "workload_class": parallel_meta.get("workload_class"),
        "batching_class": parallel_meta.get("batching_class"),
        "evidence_version": parallel_meta.get("evidence_version"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark serial/auto/parallel mode matrix for search fixtures.")
    parser.add_argument(
        "--fixtures",
        nargs="*",
        default=list(DEFAULT_FIXTURES),
        help="Fixture paths relative to repo root.",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        choices=list(DEFAULT_MODES),
        default=list(DEFAULT_MODES),
        help="Parallel mode matrix to execute.",
    )
    parser.add_argument("--iterations", type=int, default=1, help="Number of repeats per fixture/mode.")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path.")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise ValueError("--iterations must be greater than zero.")

    machine = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "os_cpu_count": os.cpu_count(),
        "effective_cpu_count": effective_cpu_count(),
        "evidence_version": EVIDENCE_VERSION,
    }

    runs: list[dict[str, Any]] = []
    for fixture in args.fixtures:
        for mode in args.modes:
            workers = MODE_WORKERS[mode]
            for iteration in range(1, args.iterations + 1):
                row = _run_single(fixture=fixture, mode=mode, workers=workers)
                row["iteration"] = iteration
                runs.append(row)

    payload = {"machine": machine, "runs": runs}
    text = json.dumps(payload, indent=2)
    if args.output:
        output_path = ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
