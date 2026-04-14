from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from slope_stab.analysis import run_analysis
from slope_stab.materials.uniform_soils import build_uniform_soils_for_geometry
from slope_stab.models import (
    AnalysisInput,
    AutoRefineSearchInput,
    GeometryInput,
    ProjectInput,
    SearchInput,
    SearchLimitsInput,
)


@dataclass(frozen=True)
class SlideReference:
    fos: float
    center: tuple[float, float]
    radius: float
    left: tuple[float, float]
    right: tuple[float, float]


@dataclass(frozen=True)
class CaseDefinition:
    case_id: str
    report_relpath: str
    s01_relpath: str
    geometry: GeometryInput
    search_limits: SearchLimitsInput


CASES: tuple[CaseDefinition, ...] = (
    CaseDefinition(
        case_id="Case2_Search",
        report_relpath="Verification/Bishop/Case 2/Case2_Search/Case2_Search-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 2/Case2_Search/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01",
        geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
        search_limits=SearchLimitsInput(x_min=0.0, x_max=35.0),
    ),
    CaseDefinition(
        case_id="Case4",
        report_relpath="Verification/Bishop/Case 4/Case4/Case4-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 4/Case4/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
        geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
    ),
)

METHOD_LABELS = {
    "bishop_simplified": "bishop simplified",
    "spencer": "spencer",
}

_DATA_STRING_RE = re.compile(r"<data_string>([^<]*)</data_string>")
_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _read_lines(relpath: str) -> list[str]:
    return (REPO_ROOT / relpath).read_text(encoding="utf-8", errors="ignore").splitlines()


def _find_line(lines: list[str], pattern: str, start: int = 0, end: int | None = None) -> int:
    stop = len(lines) if end is None else end
    for idx in range(start, stop):
        if pattern in lines[idx]:
            return idx
    raise ValueError(f"Could not find pattern: {pattern}")


def _extract_data_value(
    lines: list[str],
    label: str,
    start: int = 0,
    end: int | None = None,
    occurrence: int = 1,
) -> str:
    stop = len(lines) if end is None else end
    needle = f"<data_string>{label}</data_string>"
    found = 0
    for idx in range(start, stop):
        if needle in lines[idx]:
            found += 1
            if found != occurrence:
                continue
            for jdx in range(idx + 1, min(idx + 12, stop)):
                match = _DATA_STRING_RE.search(lines[jdx])
                if match:
                    return match.group(1).strip()
    raise ValueError(f"Could not find value for label: {label}")


def _parse_float(value: str) -> float:
    match = _FLOAT_RE.search(value)
    if match is None:
        raise ValueError(f"Could not parse float from: {value!r}")
    return float(match.group(0))


def _parse_point(value: str) -> tuple[float, float]:
    left, right = (part.strip() for part in value.split(",", maxsplit=1))
    return (float(left), float(right))


def _parse_slide_reference(lines: list[str], method_label: str) -> SlideReference:
    global_min_idx = _find_line(lines, "<Title>Global Minimums</Title>")
    support_idx = _find_line(lines, "<Title>Global Minimum Support Data</Title>", start=global_min_idx + 1)
    method_idx = _find_line(
        lines,
        f"<Title>Method: {method_label}</Title>",
        start=global_min_idx,
        end=support_idx,
    )
    fs = float(_extract_data_value(lines, "FS", start=method_idx, end=support_idx))
    center = _parse_point(_extract_data_value(lines, "Center:", start=method_idx, end=support_idx))
    radius = float(_extract_data_value(lines, "Radius:", start=method_idx, end=support_idx))
    left = _parse_point(_extract_data_value(lines, "Left Slip Surface Endpoint:", start=method_idx, end=support_idx))
    right = _parse_point(_extract_data_value(lines, "Right Slip Surface Endpoint:", start=method_idx, end=support_idx))
    return SlideReference(fos=fs, center=center, radius=radius, left=left, right=right)


def _build_project(case: CaseDefinition, lines: list[str], method: str) -> ProjectInput:
    n_slices = int(_parse_float(_extract_data_value(lines, "Number of slices:")))
    tolerance = float(_extract_data_value(lines, "Tolerance:"))
    max_iter = int(_parse_float(_extract_data_value(lines, "Maximum number of iterations:")))
    unit_weight = _parse_float(_extract_data_value(lines, "Unit Weight "))
    cohesion = _parse_float(_extract_data_value(lines, "Cohesion "))
    phi_deg = _parse_float(_extract_data_value(lines, "Phi "))
    divisions = int(_parse_float(_extract_data_value(lines, "Divisions along slope:")))
    circles_per_division = int(_parse_float(_extract_data_value(lines, "Circles per division:")))
    iterations = int(_parse_float(_extract_data_value(lines, "Number of iterations:")))
    retain_pct = _parse_float(_extract_data_value(lines, "Divisions to use in next iteration:"))

    return ProjectInput(
        units="metric",
        geometry=case.geometry,
        soils=build_uniform_soils_for_geometry(
            geometry=case.geometry,
            gamma=unit_weight,
            cohesion=cohesion,
            phi_deg=phi_deg,
        ),
        analysis=AnalysisInput(
            method=method,
            n_slices=n_slices,
            tolerance=tolerance,
            max_iter=max_iter,
            f_init=1.0,
        ),
        prescribed_surface=None,
        search=SearchInput(
            method="auto_refine_circular",
            auto_refine_circular=AutoRefineSearchInput(
                divisions_along_slope=divisions,
                circles_per_division=circles_per_division,
                iterations=iterations,
                divisions_to_use_next_iteration_pct=retain_pct,
                search_limits=case.search_limits,
            ),
        ),
    )


def _stage_deltas(stage: dict[str, object], reference: SlideReference) -> dict[str, float]:
    surface = stage["surface"]
    assert isinstance(surface, dict)
    observed_center = (float(surface["xc"]), float(surface["yc"]))
    return {
        "fos_abs_delta": abs(float(stage["fos"]) - reference.fos),
        "x_left_abs_delta": abs(float(surface["x_left"]) - reference.left[0]),
        "y_left_abs_delta": abs(float(surface["y_left"]) - reference.left[1]),
        "x_right_abs_delta": abs(float(surface["x_right"]) - reference.right[0]),
        "y_right_abs_delta": abs(float(surface["y_right"]) - reference.right[1]),
        "radius_rel_delta": abs(float(surface["r"]) - reference.radius) / reference.radius,
        "center_distance": math.hypot(observed_center[0] - reference.center[0], observed_center[1] - reference.center[1]),
    }


def _capture_case_method(case: CaseDefinition, method: str) -> dict[str, object]:
    lines = _read_lines(case.report_relpath)
    method_label = METHOD_LABELS[method]
    reference = _parse_slide_reference(lines, method_label)
    project = _build_project(case, lines, method)
    result = run_analysis(project, forced_parallel_mode="serial", forced_parallel_workers=1)
    search_meta = result.metadata["search"]
    before_stage = search_meta["before_post_polish"]
    after_stage = search_meta["after_post_polish"]
    soil = project.soils.materials[0]

    return {
        "case_id": case.case_id,
        "method": method,
        "source_files": {
            "rfcreport": case.report_relpath,
            "s01": case.s01_relpath,
        },
        "analysis_input": {
            "geometry": asdict(case.geometry),
            "search_limits": asdict(case.search_limits),
            "n_slices": project.analysis.n_slices,
            "tolerance": project.analysis.tolerance,
            "max_iter": project.analysis.max_iter,
            "material": {
                "gamma": soil.gamma,
                "c": soil.c,
                "phi_deg": soil.phi_deg,
            },
            "auto_refine_circular": {
                "divisions_along_slope": project.search.auto_refine_circular.divisions_along_slope,
                "circles_per_division": project.search.auto_refine_circular.circles_per_division,
                "iterations": project.search.auto_refine_circular.iterations,
                "divisions_to_use_next_iteration_pct": project.search.auto_refine_circular.divisions_to_use_next_iteration_pct,
            },
        },
        "effective_search_limits": asdict(case.search_limits),
        "slide_reference": {
            "fos": reference.fos,
            "surface": {
                "xc": reference.center[0],
                "yc": reference.center[1],
                "r": reference.radius,
                "x_left": reference.left[0],
                "y_left": reference.left[1],
                "x_right": reference.right[0],
                "y_right": reference.right[1],
            },
        },
        "observed": {
            "before_post_polish": before_stage,
            "after_post_polish": after_stage,
        },
        "deltas": {
            "before_post_polish": _stage_deltas(before_stage, reference),
            "after_post_polish": _stage_deltas(after_stage, reference),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture Slide2 Case2_Search/Case4 auto-refine comparison snapshot for current implementation."
    )
    parser.add_argument("--implementation-label", required=True, help="Implementation label for this snapshot (e.g. current/new)")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for case in CASES:
        for method in ("bishop_simplified", "spencer"):
            rows.append(_capture_case_method(case, method))

    payload = {
        "implementation_label": args.implementation_label,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
