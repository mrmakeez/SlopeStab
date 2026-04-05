from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisInput,
    AutoRefineSearchInput,
    GeometryInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
    SearchInput,
    SearchLimitsInput,
)
from slope_stab.search.auto_refine import (
    _build_retained_path,
    _division_boundaries_and_midpoints_for_retained_path,
    _generate_pre_polish_pair_candidates,
)
from slope_stab.search.surface_solver import build_worker_context, solve_surface_for_context


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUND_DIGITS = 6
SLIDE2_SMALL_DRIVING_THRESHOLD = 0.1

SurfaceKey = tuple[float, float, float, float, float, float, float]


@dataclass(frozen=True)
class Scenario:
    name: str
    geometry: GeometryInput
    material: MaterialInput
    n_slices: int
    tolerance: float
    max_iter: int
    f_init: float
    search_x_min: float
    search_x_max: float
    divisions_along_slope: int
    circles_per_division: int
    model_boundary_floor_y: float
    s01_relpath: str

    @property
    def profile(self) -> UniformSlopeProfile:
        return UniformSlopeProfile(
            h=self.geometry.h,
            l=self.geometry.l,
            x_toe=self.geometry.x_toe,
            y_toe=self.geometry.y_toe,
        )

    @property
    def theoretical_slot_count(self) -> int:
        return (
            self.divisions_along_slope
            * (self.divisions_along_slope - 1)
            // 2
            * self.circles_per_division
        )

    def build_project(self, method_name: str) -> ProjectInput:
        method_map = {
            "bishop simplified": "bishop_simplified",
            "spencer": "spencer",
        }
        internal_method = method_map.get(method_name.lower())
        if internal_method is None:
            raise ValueError(f"Unsupported Slide2 analysis method name: {method_name}")
        return ProjectInput(
            units="metric",
            geometry=self.geometry,
            material=self.material,
            analysis=AnalysisInput(
                method=internal_method,
                n_slices=self.n_slices,
                tolerance=self.tolerance,
                max_iter=self.max_iter,
                f_init=self.f_init,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="auto_refine_circular",
                auto_refine_circular=AutoRefineSearchInput(
                    divisions_along_slope=self.divisions_along_slope,
                    circles_per_division=self.circles_per_division,
                    iterations=1,
                    divisions_to_use_next_iteration_pct=50.0,
                    search_limits=SearchLimitsInput(
                        x_min=self.search_x_min,
                        x_max=self.search_x_max,
                    ),
                    model_boundary_floor_y=self.model_boundary_floor_y,
                ),
            ),
        )


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="Case2_Search_Iter_1",
        geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
        material=MaterialInput(gamma=20.0, c=20.0, phi_deg=20.0),
        n_slices=7,
        tolerance=0.005,
        max_iter=50,
        f_init=1.0,
        search_x_min=0.0,
        search_x_max=35.0,
        divisions_along_slope=20,
        circles_per_division=10,
        model_boundary_floor_y=0.0,
        s01_relpath="Verification/Bishop/Case 2/Case2_Search_Iter_1/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01",
    ),
    Scenario(
        name="Case4_Iter1",
        geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        material=MaterialInput(gamma=16.0, c=9.0, phi_deg=32.0),
        n_slices=25,
        tolerance=0.0001,
        max_iter=100,
        f_init=1.0,
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=30,
        circles_per_division=15,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
    Scenario(
        name="Case4_Iter1_Simple",
        geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        material=MaterialInput(gamma=16.0, c=9.0, phi_deg=32.0),
        n_slices=25,
        tolerance=0.0001,
        max_iter=100,
        f_init=1.0,
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=5,
        circles_per_division=5,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
)


def _surface_key(surface: PrescribedCircleInput) -> SurfaceKey:
    return (
        round(surface.xc, ROUND_DIGITS),
        round(surface.yc, ROUND_DIGITS),
        round(surface.r, ROUND_DIGITS),
        round(surface.x_left, ROUND_DIGITS),
        round(surface.y_left, ROUND_DIGITS),
        round(surface.x_right, ROUND_DIGITS),
        round(surface.y_right, ROUND_DIGITS),
    )


def _surface_key_to_dict(surface: SurfaceKey) -> dict[str, float]:
    return {
        "xc": surface[0],
        "yc": surface[1],
        "r": surface[2],
        "x_left": surface[3],
        "y_left": surface[4],
        "x_right": surface[5],
        "y_right": surface[6],
    }


def _surface_from_key(surface: SurfaceKey) -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=surface[0],
        yc=surface[1],
        r=surface[2],
        x_left=surface[3],
        y_left=surface[4],
        x_right=surface[5],
        y_right=surface[6],
    )


def _parse_slide2_s01_records(path: Path) -> tuple[list[str], dict[SurfaceKey, dict[str, float]]]:
    lines = path.read_text().splitlines()
    analysis_names: list[str] = []
    n_methods = 0
    center: tuple[float, float] | None = None
    records: dict[SurfaceKey, dict[str, float]] = {}
    line_idx = 0

    while line_idx < len(lines):
        line = lines[line_idx].strip()
        lowered = line.lower()
        if lowered == "* number of analysis types":
            n_methods = int(lines[line_idx + 1].strip())
            line_idx += 2
            continue
        if lowered == "* analysis names":
            if n_methods <= 0:
                raise ValueError(f"Missing number of analysis types before analysis names in {path}")
            analysis_names = [lines[line_idx + 1 + offset].strip() for offset in range(n_methods)]
            line_idx += 1 + n_methods
            continue
        if line == "* surface center":
            center = tuple(map(float, lines[line_idx + 1].split()))
            line_idx += 2
            continue
        if line.startswith("* surface ") and "data" in line:
            if center is None:
                raise ValueError(f"Encountered surface data before a center in {path}.")
            if not analysis_names:
                raise ValueError(f"Missing analysis names before surface data in {path}.")
            first_values = list(map(float, lines[line_idx + 1].split()[:5]))
            radius, x_left, y_left, x_right, y_right = first_values
            key = (
                round(center[0], ROUND_DIGITS),
                round(center[1], ROUND_DIGITS),
                round(radius, ROUND_DIGITS),
                round(x_left, ROUND_DIGITS),
                round(y_left, ROUND_DIGITS),
                round(x_right, ROUND_DIGITS),
                round(y_right, ROUND_DIGITS),
            )
            status_by_method: dict[str, float] = {}
            for method_idx, method_name in enumerate(analysis_names, start=1):
                values = lines[line_idx + method_idx].split()
                status_by_method[method_name] = float(values[5])
            records[key] = status_by_method
            line_idx += 1 + len(analysis_names)
            continue
        line_idx += 1

    return analysis_names, records


def _enumerate_ours(scenario: Scenario) -> tuple[dict[SurfaceKey, PrescribedCircleInput], int]:
    retained_path = _build_retained_path(
        scenario.profile,
        scenario.search_x_min,
        scenario.search_x_max,
    )
    _, midpoints = _division_boundaries_and_midpoints_for_retained_path(
        retained_path,
        scenario.divisions_along_slope,
    )

    surfaces: dict[SurfaceKey, PrescribedCircleInput] = {}
    slot_count = 0
    for left_idx in range(scenario.divisions_along_slope):
        for right_idx in range(left_idx + 1, scenario.divisions_along_slope):
            pair_candidates = _generate_pre_polish_pair_candidates(
                profile=scenario.profile,
                search_x_min=scenario.search_x_min,
                search_x_max=scenario.search_x_max,
                p_left=midpoints[left_idx],
                p_right=midpoints[right_idx],
                circles_per_division=scenario.circles_per_division,
                model_boundary_floor_y=scenario.model_boundary_floor_y,
            )
            slot_count += len(pair_candidates)
            for surface in pair_candidates:
                if surface is None:
                    continue
                surfaces[_surface_key(surface)] = surface
    return surfaces, slot_count


def _classify_ours_surface(
    method_name: str,
    surface: PrescribedCircleInput,
    scenario: Scenario,
) -> dict[str, object]:
    context = build_worker_context(scenario.build_project(method_name))
    try:
        result = solve_surface_for_context(context, surface)
    except GeometryError as exc:
        return {
            "status": "geometry_exception",
            "slide2_like_status": "other_invalid",
            "message": str(exc),
        }
    except ConvergenceError as exc:
        return {
            "status": "convergence_exception",
            "slide2_like_status": "error_-111_like",
            "message": str(exc),
        }
    except ValueError as exc:
        return {
            "status": "value_error",
            "slide2_like_status": "other_invalid",
            "message": str(exc),
        }

    if not result.converged:
        return {
            "status": "nonconverged_result",
            "slide2_like_status": "error_-111_like",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    if not math.isfinite(result.fos):
        return {
            "status": "nonfinite_fos",
            "slide2_like_status": "other_invalid",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    if result.fos <= 0.0:
        return {
            "status": "nonpositive_fos",
            "slide2_like_status": "other_invalid",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    if not math.isfinite(result.driving_moment):
        return {
            "status": "nonfinite_driving_moment",
            "slide2_like_status": "other_invalid",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    if abs(result.driving_moment) <= SLIDE2_SMALL_DRIVING_THRESHOLD:
        return {
            "status": "small_driving_moment_le_0p1",
            "slide2_like_status": "error_-108_like",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    if not math.isfinite(result.resisting_moment):
        return {
            "status": "nonfinite_resisting_moment",
            "slide2_like_status": "other_invalid",
            "fos": result.fos,
            "driving_moment": result.driving_moment,
        }
    return {
        "status": "valid",
        "slide2_like_status": "valid",
        "fos": result.fos,
        "driving_moment": result.driving_moment,
    }


def _slide2_status_label(status_value: float) -> str:
    if status_value < 0:
        return f"error_{int(status_value)}"
    return "valid"


def _slide2_method_counts(records: dict[SurfaceKey, dict[str, float]], method_name: str) -> dict[str, int]:
    counter = Counter(_slide2_status_label(statuses[method_name]) for statuses in records.values())
    return dict(sorted(counter.items()))


def _evaluate_ours_by_method(
    scenario: Scenario,
    surfaces: dict[SurfaceKey, PrescribedCircleInput],
    method_names: list[str],
) -> dict[str, dict[SurfaceKey, dict[str, object]]]:
    return {
        method_name: {
            key: _classify_ours_surface(method_name, surface, scenario)
            for key, surface in surfaces.items()
        }
        for method_name in method_names
    }


def _status_counts(records: dict[SurfaceKey, dict[str, object]]) -> dict[str, int]:
    counter = Counter(str(status["status"]) for status in records.values())
    return dict(sorted(counter.items()))


def _slide2_like_counts(records: dict[SurfaceKey, dict[str, object]]) -> dict[str, int]:
    counter = Counter(str(status["slide2_like_status"]) for status in records.values())
    return dict(sorted(counter.items()))


def _alignment_summary(
    slide2_records: dict[SurfaceKey, dict[str, float]],
    our_results: dict[SurfaceKey, dict[str, object]],
    method_name: str,
) -> dict[str, object]:
    alignment_counter = Counter()
    mismatch_examples: list[dict[str, object]] = []
    for key, slide2_statuses in slide2_records.items():
        slide2_label = _slide2_status_label(slide2_statuses[method_name])
        ours = our_results.get(key)
        ours_label = "missing_geometry" if ours is None else str(ours["slide2_like_status"])
        alignment_counter[f"{slide2_label} -> {ours_label}"] += 1
        if slide2_label != ours_label and len(mismatch_examples) < 10:
            mismatch_payload = {
                **_surface_key_to_dict(key),
                "slide2_status": slide2_label,
                "ours_status": ours_label,
            }
            if ours is not None:
                if "status" in ours:
                    mismatch_payload["ours_raw_status"] = ours["status"]
                if "fos" in ours:
                    mismatch_payload["ours_fos"] = ours["fos"]
                if "driving_moment" in ours:
                    mismatch_payload["ours_driving_moment"] = ours["driving_moment"]
            mismatch_examples.append(mismatch_payload)
    return {
        "counts": dict(sorted(alignment_counter.items())),
        "mismatch_examples": mismatch_examples,
    }


def _summarize_scenario(scenario: Scenario) -> dict[str, object]:
    analysis_names, slide2_records = _parse_slide2_s01_records(REPO_ROOT / scenario.s01_relpath)
    our_surfaces, generated_slot_count = _enumerate_ours(scenario)
    our_evaluations = _evaluate_ours_by_method(scenario, our_surfaces, analysis_names)

    stored_keys = set(slide2_records.keys())
    our_keys = set(our_surfaces.keys())
    shared_keys = stored_keys & our_keys
    ours_only_keys = our_keys - stored_keys

    slide2_per_method = {
        method_name: {
            "stored_status_counts": _slide2_method_counts(slide2_records, method_name),
        }
        for method_name in analysis_names
    }
    ours_per_method = {
        method_name: {
            "all_generated_status_counts": _status_counts(our_evaluations[method_name]),
            "all_generated_slide2_like_counts": _slide2_like_counts(our_evaluations[method_name]),
            "ours_only_status_counts": _status_counts(
                {key: our_evaluations[method_name][key] for key in ours_only_keys}
            ),
            "shared_geometry_alignment": _alignment_summary(
                {key: slide2_records[key] for key in shared_keys},
                our_evaluations[method_name],
                method_name,
            ),
        }
        for method_name in analysis_names
    }

    return {
        "name": scenario.name,
        "s01": scenario.s01_relpath,
        "analysis_names": analysis_names,
        "theoretical_slot_count": scenario.theoretical_slot_count,
        "generated_slot_count_from_ours": generated_slot_count,
        "slide2_stored_geometry_count": len(stored_keys),
        "slide2_unstored_slot_gap": scenario.theoretical_slot_count - len(stored_keys),
        "ours_unique_geometry_count": len(our_keys),
        "shared_geometry_count": len(shared_keys),
        "ours_only_geometry_count": len(ours_only_keys),
        "slide2_per_method": slide2_per_method,
        "ours_per_method": ours_per_method,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare stored Slide2 iteration-1 per-method status/error results against "
            "our coarse Bishop/Spencer outcome classification."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=[scenario.name for scenario in SCENARIOS],
        action="append",
        help="Optional scenario name filter. May be supplied multiple times.",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "benchmarks" / "auto_refine_slide2_iteration1_error_harness_current.json"),
        help="Path to write the JSON summary.",
    )
    args = parser.parse_args()

    selected = tuple(
        scenario for scenario in SCENARIOS if args.scenario is None or scenario.name in set(args.scenario)
    )
    summaries = [_summarize_scenario(scenario) for scenario in selected]
    payload = {
        "round_digits": ROUND_DIGITS,
        "small_driving_moment_proxy_threshold": SLIDE2_SMALL_DRIVING_THRESHOLD,
        "note": (
            "Slide2 stores per-method status rows for each stored geometry. This harness parses those rows and "
            "compares them against our coarse outcome classes on the same generated geometries. "
            "The -108 comparison uses our driving-moment <= 0.1 proxy because the Slide2 page refers to "
            "small driving force or moment depending on method."
        ),
        "scenarios": summaries,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")

    for summary in summaries:
        print(
            f"{summary['name']}: stored={summary['slide2_stored_geometry_count']} "
            f"unstored_gap={summary['slide2_unstored_slot_gap']} "
            f"ours_unique={summary['ours_unique_geometry_count']}"
        )
        for method_name in summary["analysis_names"]:
            slide2_counts = summary["slide2_per_method"][method_name]["stored_status_counts"]
            ours_counts = summary["ours_per_method"][method_name]["all_generated_slide2_like_counts"]
            print(f"  {method_name}: slide2={slide2_counts} ours={ours_counts}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
