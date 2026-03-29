from __future__ import annotations

import argparse
import copy
import json
import pathlib
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


ROOT = _repo_root()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from slope_stab.analysis import run_analysis  # noqa: E402
from slope_stab.io.json_io import parse_project_input  # noqa: E402


ALL_CUCKOO_FIXTURES: tuple[str, ...] = (
    "tests/fixtures/case2_cuckoo_global.json",
    "tests/fixtures/case3_cuckoo_global.json",
    "tests/fixtures/case4_cuckoo_global.json",
    "tests/fixtures/case2_cuckoo_global_spencer.json",
    "tests/fixtures/case3_cuckoo_global_spencer.json",
    "tests/fixtures/case4_cuckoo_global_spencer.json",
    "tests/fixtures/case2_cuckoo_oracle.json",
    "tests/fixtures/case3_cuckoo_oracle.json",
    "tests/fixtures/case2_cuckoo_oracle_spencer.json",
    "tests/fixtures/case3_cuckoo_oracle_spencer.json",
)

COARSE_SPENCER_FIXTURES: tuple[str, ...] = (
    "tests/fixtures/case2_cuckoo_global_spencer.json",
    "tests/fixtures/case3_cuckoo_global_spencer.json",
    "tests/fixtures/case4_cuckoo_global_spencer.json",
    "tests/fixtures/case2_cuckoo_oracle_spencer.json",
    "tests/fixtures/case3_cuckoo_oracle_spencer.json",
)

# Keep benchmark gates frozen during tuning.
BENCHMARK_THRESHOLD_BY_FIXTURE: dict[str, float] = {
    "tests/fixtures/case2_cuckoo_global.json": 2.10296 + 0.01,
    "tests/fixtures/case3_cuckoo_global.json": 0.986442 + 0.01,
    "tests/fixtures/case4_cuckoo_global.json": 1.234670 + 0.01,
    "tests/fixtures/case2_cuckoo_global_spencer.json": 2.09717 + 0.01,
    "tests/fixtures/case3_cuckoo_global_spencer.json": 0.985334 + 0.01,
    "tests/fixtures/case4_cuckoo_global_spencer.json": 1.23141 + 0.01,
}

FIXED_PROFILE_VALUES: dict[str, Any] = {
    "levy_beta": 1.5,
    "alpha_max": 0.5,
    "alpha_min": 0.05,
    "seed": 0,
    "post_polish": True,
}


@dataclass(frozen=True)
class CuckooProfile:
    population_size: int
    max_iterations: int
    max_evaluations: int
    discovery_rate: float
    min_improvement: float
    stall_iterations: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_size": self.population_size,
            "max_iterations": self.max_iterations,
            "max_evaluations": self.max_evaluations,
            "discovery_rate": self.discovery_rate,
            "min_improvement": self.min_improvement,
            "stall_iterations": self.stall_iterations,
            **FIXED_PROFILE_VALUES,
            "name": self.name,
        }

    def label(self) -> str:
        if self.name:
            return self.name
        return (
            f"pop{self.population_size}_iter{self.max_iterations}_eval{self.max_evaluations}_"
            f"disc{self.discovery_rate}_imp{self.min_improvement}_stall{self.stall_iterations}"
        )


def _load_payload(fixture_relpath: str) -> dict[str, Any]:
    payload = json.loads((ROOT / fixture_relpath).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Fixture root must be a JSON object: {fixture_relpath}")
    return payload


def _apply_profile(payload: dict[str, Any], profile: CuckooProfile) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    search = out.get("search")
    if not isinstance(search, dict):
        raise ValueError("Fixture does not include a search object.")
    method = str(search.get("method"))
    if method != "cuckoo_global_circular":
        raise ValueError(f"Fixture search.method must be cuckoo_global_circular, got {method!r}")
    cuckoo = search.get("cuckoo_global_circular")
    if not isinstance(cuckoo, dict):
        raise ValueError("Fixture search.cuckoo_global_circular must be an object.")

    cuckoo["population_size"] = profile.population_size
    cuckoo["max_iterations"] = profile.max_iterations
    cuckoo["max_evaluations"] = profile.max_evaluations
    cuckoo["discovery_rate"] = profile.discovery_rate
    cuckoo["min_improvement"] = profile.min_improvement
    cuckoo["stall_iterations"] = profile.stall_iterations
    for key, value in FIXED_PROFILE_VALUES.items():
        cuckoo[key] = value
    return out


def _threshold_for_fixture(fixture_relpath: str, payload: dict[str, Any]) -> tuple[float, str]:
    oracle = payload.get("oracle")
    if isinstance(oracle, dict):
        return float(oracle["benchmark_fos"]) + float(oracle["margin"]), "oracle"
    if fixture_relpath not in BENCHMARK_THRESHOLD_BY_FIXTURE:
        raise ValueError(f"No benchmark threshold mapping for fixture: {fixture_relpath}")
    return float(BENCHMARK_THRESHOLD_BY_FIXTURE[fixture_relpath]), "benchmark"


def _endpoint_gate_ok(payload: dict[str, Any], result_metadata: dict[str, Any]) -> bool:
    oracle = payload.get("oracle")
    if not isinstance(oracle, dict):
        return True

    expected = oracle.get("benchmark_surface")
    if not isinstance(expected, dict):
        return False
    endpoint_tol = float(oracle.get("endpoint_abs_tolerance", 0.0))

    actual = result_metadata.get("prescribed_surface")
    if not isinstance(actual, dict):
        return False

    for key in ("x_left", "y_left", "x_right", "y_right"):
        if key not in actual or key not in expected:
            return False
        if abs(float(actual[key]) - float(expected[key])) > endpoint_tol:
            return False
    return True


def _run_fixture(profile: CuckooProfile, fixture_relpath: str) -> dict[str, Any]:
    raw = _load_payload(fixture_relpath)
    configured = _apply_profile(raw, profile)
    project = parse_project_input(configured)

    started = time.perf_counter()
    result = run_analysis(project)
    elapsed = time.perf_counter() - started

    threshold, gate_type = _threshold_for_fixture(fixture_relpath, raw)
    fos_pass = float(result.fos) <= threshold
    endpoint_pass = _endpoint_gate_ok(raw, result.metadata)
    passed = fos_pass and endpoint_pass

    search_meta = result.metadata.get("search", {})
    total_evals = int(search_meta.get("total_evaluations", -1))
    termination_reason = str(search_meta.get("termination_reason", ""))
    slack = threshold - float(result.fos)

    return {
        "fixture": fixture_relpath,
        "analysis_method": configured.get("analysis", {}).get("method"),
        "gate_type": gate_type,
        "threshold": threshold,
        "fos": float(result.fos),
        "slack": slack,
        "fos_pass": fos_pass,
        "endpoint_pass": endpoint_pass,
        "passed": passed,
        "elapsed_seconds": elapsed,
        "total_evaluations": total_evals,
        "termination_reason": termination_reason,
    }


def _evaluate_profile(
    profile: CuckooProfile,
    fixtures: tuple[str, ...],
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, Any]:
    for _ in range(warmup_runs):
        for fixture in fixtures:
            _run_fixture(profile, fixture)

    measured: list[dict[str, Any]] = []
    run_aggregates: list[float] = []
    eval_aggregates: list[int] = []
    all_passed = True
    worst_slack = float("inf")

    for run_index in range(measured_runs):
        run_rows: list[dict[str, Any]] = []
        aggregate_seconds = 0.0
        aggregate_evals = 0
        for fixture in fixtures:
            row = _run_fixture(profile, fixture)
            run_rows.append(row)
            aggregate_seconds += float(row["elapsed_seconds"])
            aggregate_evals += int(row["total_evaluations"])
            all_passed = all_passed and bool(row["passed"])
            worst_slack = min(worst_slack, float(row["slack"]))
        measured.append(
            {
                "run_index": run_index + 1,
                "aggregate_elapsed_seconds": aggregate_seconds,
                "aggregate_total_evaluations": aggregate_evals,
                "fixtures": run_rows,
            }
        )
        run_aggregates.append(aggregate_seconds)
        eval_aggregates.append(aggregate_evals)

    return {
        "profile": profile.to_dict(),
        "profile_label": profile.label(),
        "fixtures": list(fixtures),
        "warmup_runs": warmup_runs,
        "measured_runs": measured_runs,
        "all_passed": all_passed,
        "median_aggregate_elapsed_seconds": statistics.median(run_aggregates),
        "median_aggregate_total_evaluations": statistics.median(eval_aggregates),
        "worst_slack": worst_slack,
        "measured": measured,
    }


def _load_profiles(path: pathlib.Path | None) -> list[CuckooProfile]:
    if path is None:
        return [
            CuckooProfile(
                population_size=40,
                max_iterations=300,
                max_evaluations=7000,
                discovery_rate=0.25,
                min_improvement=1e-4,
                stall_iterations=25,
                name="baseline_40_300_7000",
            )
        ]

    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Profiles file must contain a JSON array.")

    profiles: list[CuckooProfile] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Profile entry {idx} must be an object.")
        profiles.append(
            CuckooProfile(
                population_size=int(row["population_size"]),
                max_iterations=int(row["max_iterations"]),
                max_evaluations=int(row["max_evaluations"]),
                discovery_rate=float(row["discovery_rate"]),
                min_improvement=float(row["min_improvement"]),
                stall_iterations=int(row["stall_iterations"]),
                name=(None if row.get("name") is None else str(row["name"])),
            )
        )
    return profiles


def _resolve_fixtures(raw: list[str]) -> tuple[str, ...]:
    if len(raw) == 1 and raw[0] == "@all":
        return ALL_CUCKOO_FIXTURES
    if len(raw) == 1 and raw[0] == "@coarse_spencer":
        return COARSE_SPENCER_FIXTURES
    return tuple(raw)


def _sorted_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda item: (
            0 if item["all_passed"] else 1,
            float(item["median_aggregate_elapsed_seconds"]),
            float(item["median_aggregate_total_evaluations"]),
            -float(item["worst_slack"]),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate cuckoo parameter profiles against frozen benchmark/oracle gates.")
    parser.add_argument(
        "--fixtures",
        nargs="*",
        default=["@all"],
        help="Fixture relpaths, or one of: @all, @coarse_spencer",
    )
    parser.add_argument(
        "--profiles-file",
        type=str,
        default=None,
        help="Path to a JSON array of profile objects. If omitted, runs current baseline profile.",
    )
    parser.add_argument("--warmup-runs", type=int, default=0, help="Number of warm-up runs per candidate.")
    parser.add_argument("--measured-runs", type=int, default=1, help="Number of measured runs per candidate.")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path relative to repo root.")
    args = parser.parse_args()

    if args.warmup_runs < 0:
        raise ValueError("--warmup-runs must be >= 0.")
    if args.measured_runs <= 0:
        raise ValueError("--measured-runs must be > 0.")

    fixtures = _resolve_fixtures(args.fixtures)
    profiles = _load_profiles(None if args.profiles_file is None else ROOT / args.profiles_file)

    results = [_evaluate_profile(profile, fixtures, args.warmup_runs, args.measured_runs) for profile in profiles]
    ranked = _sorted_results(results)

    payload = {
        "fixtures": list(fixtures),
        "profiles_evaluated": len(profiles),
        "results": ranked,
    }

    if args.output:
        output_path = ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
