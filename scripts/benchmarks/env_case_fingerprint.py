from __future__ import annotations

import argparse
import io
import json
import multiprocessing as mp
import os
import pathlib
import platform
import re
import socket
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


ROOT = _repo_root()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cma  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
from slope_stab.analysis import run_analysis  # noqa: E402
from slope_stab.verification.cases import AutoRefineVerificationCase, VERIFICATION_CASES  # noqa: E402


TARGET_CASE_NAME = "Case 4 (Spencer Auto-Refine Parity)"
DEFAULT_RUNS = 3


def _pool_probe_task(value: int) -> int:
    return value * value


def _relative_error(actual: float, expected: float) -> float:
    if expected == 0.0:
        if actual == 0.0:
            return 0.0
        return float("inf")
    return abs(actual - expected) / abs(expected)


def _sanitize_host(host: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", host).strip("-")
    return cleaned or "unknown-host"


def _capture_numpy_config_text() -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        np.__config__.show()
    return buffer.getvalue().rstrip()


def _probe_process_pool(mp_context: Any | None = None, context_name: str = "default") -> dict[str, Any]:
    start = time.perf_counter()
    payload: dict[str, Any] = {
        "context": context_name,
        "ok": False,
        "elapsed_seconds": None,
    }
    try:
        kwargs: dict[str, Any] = {"max_workers": 2}
        if mp_context is not None:
            kwargs["mp_context"] = mp_context
        with ProcessPoolExecutor(**kwargs) as executor:
            result = list(executor.map(_pool_probe_task, [2, 3]))
        payload["ok"] = True
        payload["result"] = result
    except Exception as exc:  # pragma: no cover - diagnostics path
        payload["error_type"] = type(exc).__name__
        payload["error_message"] = str(exc)
    payload["elapsed_seconds"] = time.perf_counter() - start
    return payload


def _resolve_case() -> AutoRefineVerificationCase:
    for case in VERIFICATION_CASES:
        if case.name == TARGET_CASE_NAME:
            if not isinstance(case, AutoRefineVerificationCase):
                raise TypeError(f"Resolved case is not auto-refine: {TARGET_CASE_NAME}")
            return case
    raise ValueError(f"Unable to resolve verification case by name: {TARGET_CASE_NAME}")


def _run_case_once(case: AutoRefineVerificationCase, run_index: int) -> dict[str, Any]:
    started = time.perf_counter()
    result = run_analysis(case.project, forced_parallel_mode="serial", forced_parallel_workers=1)
    elapsed = time.perf_counter() - started

    surface = result.metadata.get("prescribed_surface", {})
    search_meta = result.metadata.get("search", {})
    run_payload = {
        "run_index": run_index,
        "elapsed_seconds": elapsed,
        "solver": {
            "fos": result.fos,
            "driving_moment": result.driving_moment,
            "resisting_moment": result.resisting_moment,
            "iterations": result.iterations,
            "residual": result.residual,
            "converged": result.converged,
        },
        "surface": {
            "xc": float(surface.get("xc", float("nan"))),
            "yc": float(surface.get("yc", float("nan"))),
            "r": float(surface.get("r", float("nan"))),
            "x_left": float(surface.get("x_left", float("nan"))),
            "y_left": float(surface.get("y_left", float("nan"))),
            "x_right": float(surface.get("x_right", float("nan"))),
            "y_right": float(surface.get("y_right", float("nan"))),
        },
        "search_counts": {
            "valid_surfaces": search_meta.get("valid_surfaces"),
            "invalid_surfaces": search_meta.get("invalid_surfaces"),
            "generated_surfaces": search_meta.get("generated_surfaces"),
            "iteration_diagnostics_count": len(search_meta.get("iteration_diagnostics", [])),
        },
    }
    return run_payload


def _gate_for_run(case: AutoRefineVerificationCase, run_payload: dict[str, Any]) -> dict[str, Any]:
    solver = run_payload["solver"]
    surface = run_payload["surface"]

    fos_actual = float(solver["fos"])
    fos_abs_error = abs(fos_actual - case.expected_fos)
    endpoint_errors = {
        "x_left": abs(float(surface["x_left"]) - case.expected_left[0]),
        "y_left": abs(float(surface["y_left"]) - case.expected_left[1]),
        "x_right": abs(float(surface["x_right"]) - case.expected_right[0]),
        "y_right": abs(float(surface["y_right"]) - case.expected_right[1]),
    }
    radius_rel_error = _relative_error(float(surface["r"]), case.expected_radius)

    endpoint_gate = {
        key: {
            "expected": (
                case.expected_left[0]
                if key == "x_left"
                else case.expected_left[1]
                if key == "y_left"
                else case.expected_right[0]
                if key == "x_right"
                else case.expected_right[1]
            ),
            "tolerance": case.endpoint_abs_tolerance,
            "actual_error": value,
            "passed": value <= case.endpoint_abs_tolerance,
        }
        for key, value in endpoint_errors.items()
    }
    endpoint_passed = all(item["passed"] for item in endpoint_gate.values())

    fos_gate = {
        "expected": case.expected_fos,
        "tolerance": case.fos_tolerance,
        "actual": fos_actual,
        "actual_error": fos_abs_error,
        "passed": fos_abs_error <= case.fos_tolerance,
    }
    radius_gate = {
        "expected": case.expected_radius,
        "tolerance": case.radius_rel_tolerance,
        "actual": float(surface["r"]),
        "actual_error": radius_rel_error,
        "passed": radius_rel_error <= case.radius_rel_tolerance,
    }

    overall_pass = fos_gate["passed"] and endpoint_passed and radius_gate["passed"]
    return {
        "run_index": run_payload["run_index"],
        "fos_abs_error": fos_gate,
        "endpoint_abs_error": endpoint_gate,
        "radius_rel_error": radius_gate,
        "overall_passed": overall_pass,
    }


def _determinism_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    def _signature(run_payload: dict[str, Any]) -> tuple[Any, ...]:
        solver = run_payload["solver"]
        surface = run_payload["surface"]
        counts = run_payload["search_counts"]
        return (
            float(solver["fos"]),
            float(surface["xc"]),
            float(surface["yc"]),
            float(surface["r"]),
            float(surface["x_left"]),
            float(surface["y_left"]),
            float(surface["x_right"]),
            float(surface["y_right"]),
            counts["valid_surfaces"],
            counts["invalid_surfaces"],
            counts["generated_surfaces"],
            counts["iteration_diagnostics_count"],
        )

    signatures = [_signature(run_payload) for run_payload in runs]
    unique_signatures = {sig for sig in signatures}

    fos_values = [float(run_payload["solver"]["fos"]) for run_payload in runs]
    x_right_values = [float(run_payload["surface"]["x_right"]) for run_payload in runs]
    radius_values = [float(run_payload["surface"]["r"]) for run_payload in runs]

    return {
        "all_runs_identical": len(unique_signatures) == 1,
        "unique_signature_count": len(unique_signatures),
        "spread": {
            "fos": {
                "min": min(fos_values),
                "max": max(fos_values),
                "range": max(fos_values) - min(fos_values),
            },
            "x_right": {
                "min": min(x_right_values),
                "max": max(x_right_values),
                "range": max(x_right_values) - min(x_right_values),
            },
            "r": {
                "min": min(radius_values),
                "max": max(radius_values),
                "range": max(radius_values) - min(radius_values),
            },
        },
    }


def _default_output_path() -> pathlib.Path:
    host = _sanitize_host(socket.gethostname())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel = f"docs/benchmarks/env-case4-spencer-fingerprint-{host}-{stamp}.json"
    return ROOT / rel


def _environment_fingerprint() -> dict[str, Any]:
    uname = platform.uname()
    start_method: str | None = None
    try:
        start_method = mp.get_start_method()
    except RuntimeError:
        start_method = None

    methods = []
    try:
        methods = list(mp.get_all_start_methods())
    except Exception:
        methods = []

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": {
            "version": sys.version.replace("\n", " "),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "uname": {
            "system": uname.system,
            "node": uname.node,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
        },
        "cpu_count": os.cpu_count(),
        "dependencies": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "cma": cma.__version__,
        },
        "multiprocessing": {
            "default_start_method": start_method,
            "available_start_methods": methods,
        },
        "numpy_config_text": _capture_numpy_config_text(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture environment + Case 4 (Spencer Auto-Refine Parity) fingerprint."
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Number of repeated case runs.")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output JSON path relative to repo root or absolute path.",
    )
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be greater than zero.")

    env = _environment_fingerprint()
    preflight_default = _probe_process_pool(context_name="default")
    preflight_fork: dict[str, Any]
    if "fork" in env["multiprocessing"]["available_start_methods"]:
        preflight_fork = _probe_process_pool(mp_context=mp.get_context("fork"), context_name="fork")
    else:
        preflight_fork = {
            "context": "fork",
            "supported": False,
            "ok": False,
            "reason": "fork_start_method_not_available",
        }

    case = _resolve_case()
    runs = [_run_case_once(case, run_index=i + 1) for i in range(args.runs)]
    gate_per_run = [_gate_for_run(case, run_payload) for run_payload in runs]
    gate_all_passed = all(item["overall_passed"] for item in gate_per_run)
    determinism = _determinism_summary(runs)

    payload = {
        "environment": env,
        "preflight": {
            "default_process_pool": preflight_default,
            "fork_process_pool": preflight_fork,
        },
        "case_reference": {
            "name": case.name,
            "case_type": case.case_type,
            "analysis_method": case.analysis_method,
            "expected": {
                "fos": case.expected_fos,
                "fos_tolerance": case.fos_tolerance,
                "radius": case.expected_radius,
                "radius_rel_tolerance": case.radius_rel_tolerance,
                "center": {
                    "xc": case.expected_center[0],
                    "yc": case.expected_center[1],
                },
                "left": {
                    "x": case.expected_left[0],
                    "y": case.expected_left[1],
                },
                "right": {
                    "x": case.expected_right[0],
                    "y": case.expected_right[1],
                },
                "endpoint_abs_tolerance": case.endpoint_abs_tolerance,
            },
        },
        "runs": runs,
        "gate_evaluation": {
            "all_runs_passed": gate_all_passed,
            "per_run": gate_per_run,
        },
        "determinism": determinism,
    }

    if args.output:
        output_path = pathlib.Path(args.output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
    else:
        output_path = _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    first_run = runs[0]
    first_gate = gate_per_run[0]
    print(f"artifact_path={output_path}")
    print(f"case={case.name}")
    print(f"runs={args.runs}")
    print(f"all_runs_passed={gate_all_passed}")
    print(f"first_run_overall_passed={first_gate['overall_passed']}")
    print(f"first_run_fos={first_run['solver']['fos']}")
    print(f"first_run_x_right={first_run['surface']['x_right']}")
    print(f"preflight_default_ok={preflight_default.get('ok')}")
    print(f"preflight_fork_ok={preflight_fork.get('ok')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
