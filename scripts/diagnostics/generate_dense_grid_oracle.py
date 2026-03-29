from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

from slope_stab.io.json_io import parse_project_input
from slope_stab.search.common import (
    evaluate_surface_candidate,
    is_better_score,
    map_vector_to_surface,
    repair_vector_clip,
)
from slope_stab.search.surface_solver import build_profile, build_worker_context, solve_surface_for_context


@dataclass(frozen=True)
class DenseGridOracle:
    source: str
    grid_resolution_per_dimension: int
    benchmark_fos: float
    margin: float
    benchmark_surface: dict[str, float]
    endpoint_abs_tolerance: float


def _resolve_limits(project_payload: dict) -> tuple[float, float]:
    search = project_payload.get("search", {})
    method = search.get("method")

    if method == "cuckoo_global_circular":
        limits = search["cuckoo_global_circular"]["search_limits"]
        return float(limits["x_min"]), float(limits["x_max"])
    if method == "cmaes_global_circular":
        limits = search["cmaes_global_circular"]["search_limits"]
        return float(limits["x_min"]), float(limits["x_max"])
    if method == "direct_global_circular":
        limits = search["direct_global_circular"]["search_limits"]
        return float(limits["x_min"]), float(limits["x_max"])
    if method == "auto_refine_circular":
        limits = search["auto_refine_circular"]["search_limits"]
        return float(limits["x_min"]), float(limits["x_max"])

    raise ValueError(f"Unsupported search method in fixture for dense-grid oracle generation: {method!r}")


def generate_oracle(
    fixture_path: Path,
    *,
    analysis_method: str | None,
    resolution: int,
    margin: float,
    endpoint_abs_tolerance: float,
) -> DenseGridOracle:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    project = parse_project_input(payload)
    if analysis_method is not None:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload.setdefault("analysis", {})
        payload["analysis"]["method"] = analysis_method
        project = parse_project_input(payload)

    if project.search is None:
        raise ValueError("Fixture must include a search configuration.")

    x_min, x_max = _resolve_limits(payload)
    profile = build_profile(project.geometry)
    context = build_worker_context(project)

    best_score = float("inf")
    best_surface = None
    total = resolution * resolution * resolution
    valid = 0
    invalid = 0
    processed = 0
    start = time.perf_counter()

    denom = resolution - 1
    for i_left in range(resolution):
        u_left = i_left / denom
        for i_span in range(resolution):
            u_span = i_span / denom
            for i_beta in range(resolution):
                u_beta = i_beta / denom
                vector = (u_left, u_span, u_beta)
                surface = map_vector_to_surface(
                    profile=profile,
                    x_min=x_min,
                    x_max=x_max,
                    vector=vector,
                    repair_vector=repair_vector_clip,
                )
                candidate = evaluate_surface_candidate(
                    surface,
                    lambda current: solve_surface_for_context(context, current),
                    driving_moment_tol=1e-9,
                )
                processed += 1
                if candidate.valid and candidate.surface is not None and candidate.result is not None:
                    valid += 1
                    if is_better_score(
                        candidate.result.fos,
                        candidate.surface,
                        best_score,
                        best_surface,
                    ):
                        best_score = candidate.result.fos
                        best_surface = candidate.surface
                else:
                    invalid += 1

                if processed % 25000 == 0:
                    elapsed = time.perf_counter() - start
                    print(
                        f"[progress] processed={processed}/{total} valid={valid} invalid={invalid} "
                        f"elapsed_s={elapsed:.1f}"
                    )

    if best_surface is None:
        raise RuntimeError("Dense-grid evaluation did not find any valid surface.")

    oracle = DenseGridOracle(
        source="dense_grid_u_space",
        grid_resolution_per_dimension=resolution,
        benchmark_fos=float(best_score),
        margin=margin,
        benchmark_surface={
            "xc": float(best_surface.xc),
            "yc": float(best_surface.yc),
            "r": float(best_surface.r),
            "x_left": float(best_surface.x_left),
            "y_left": float(best_surface.y_left),
            "x_right": float(best_surface.x_right),
            "y_right": float(best_surface.y_right),
        },
        endpoint_abs_tolerance=endpoint_abs_tolerance,
    )
    elapsed = time.perf_counter() - start
    print(f"[done] processed={processed} valid={valid} invalid={invalid} elapsed_s={elapsed:.1f}")
    return oracle


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate dense-grid oracle metadata for a search fixture.")
    parser.add_argument("--fixture", required=True, help="Path to fixture JSON file.")
    parser.add_argument(
        "--method",
        choices=("bishop_simplified", "spencer"),
        default=None,
        help="Override analysis.method before evaluating the dense grid.",
    )
    parser.add_argument("--resolution", type=int, default=61, help="Grid resolution per dimension.")
    parser.add_argument("--margin", type=float, default=0.005, help="Oracle margin.")
    parser.add_argument(
        "--endpoint-abs-tolerance",
        type=float,
        default=0.6,
        help="Endpoint absolute tolerance.",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    oracle = generate_oracle(
        fixture_path=fixture_path,
        analysis_method=args.method,
        resolution=args.resolution,
        margin=args.margin,
        endpoint_abs_tolerance=args.endpoint_abs_tolerance,
    )
    print(json.dumps({"oracle": oracle.__dict__}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
