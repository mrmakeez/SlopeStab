from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

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


REPO_ROOT = Path(__file__).resolve().parents[2]

FOS_TOL = 0.005
ENDPOINT_TOL = 0.30
RADIUS_REL_TOL = 0.12


@dataclass(frozen=True)
class SlideReference:
    fos: float
    center: tuple[float, float]
    radius: float
    left: tuple[float, float]
    right: tuple[float, float]


@dataclass(frozen=True)
class Scenario:
    name: str
    report_relpath: str
    geometry: GeometryInput
    search_limits: SearchLimitsInput


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="Case2_Search",
        report_relpath="Verification/Bishop/Case 2/Case2_Search/Case2_Search-i.rfcreport",
        geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
        search_limits=SearchLimitsInput(x_min=0.0, x_max=35.0),
    ),
    Scenario(
        name="Case4",
        report_relpath="Verification/Bishop/Case 4/Case4/Case4-i.rfcreport",
        geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
    ),
)

METHOD_LABELS = {
    "bishop_simplified": "bishop simplified",
    "spencer": "spencer",
}

_DATA_STRING_RE = re.compile(r"<data_string>([^<]*)</data_string>")
_FIRST_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _read_lines(relpath: str) -> list[str]:
    return (REPO_ROOT / relpath).read_text(encoding="utf-8", errors="ignore").splitlines()


def _find_line(lines: list[str], pattern: str, start: int = 0, end: int | None = None) -> int:
    stop = len(lines) if end is None else end
    for idx in range(start, stop):
        if pattern in lines[idx]:
            return idx
    raise AssertionError(f"Could not find pattern: {pattern}")


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
    raise AssertionError(f"Could not find value for label: {label}")


def _parse_float(value: str) -> float:
    match = _FIRST_FLOAT_RE.search(value)
    if match is None:
        raise AssertionError(f"Could not parse float from: {value!r}")
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


def _build_project_for_method(lines: list[str], scenario: Scenario, method: str) -> ProjectInput:
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

    soils = build_uniform_soils_for_geometry(
        geometry=scenario.geometry,
        gamma=unit_weight,
        cohesion=cohesion,
        phi_deg=phi_deg,
    )
    return ProjectInput(
        units="metric",
        geometry=scenario.geometry,
        soils=soils,
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
                search_limits=scenario.search_limits,
            ),
        ),
    )


class AutoRefineSlide2Case2Case4AlignmentTests(unittest.TestCase):
    def test_post_polish_parity_meets_slide2_thresholds(self) -> None:
        any_stage_delta = False
        for scenario in SCENARIOS:
            lines = _read_lines(scenario.report_relpath)
            for method, method_label in METHOD_LABELS.items():
                with self.subTest(case=scenario.name, method=method):
                    project = _build_project_for_method(lines, scenario, method)
                    reference = _parse_slide_reference(lines, method_label)

                    result = run_analysis(project, forced_parallel_mode="serial", forced_parallel_workers=1)
                    search_meta = result.metadata["search"]
                    self.assertIn("before_post_polish", search_meta)
                    self.assertIn("after_post_polish", search_meta)

                    before_stage = search_meta["before_post_polish"]
                    after_stage = search_meta["after_post_polish"]
                    self.assertIn("fos", before_stage)
                    self.assertIn("surface", before_stage)
                    self.assertIn("fos", after_stage)
                    self.assertIn("surface", after_stage)
                    self.assertTrue(math.isfinite(float(before_stage["fos"])))

                    self.assertAlmostEqual(result.fos, float(after_stage["fos"]), places=12)

                    before_fos = float(before_stage["fos"])
                    after_fos = float(after_stage["fos"])
                    if abs(before_fos - after_fos) > 1e-12:
                        any_stage_delta = True

                    before_surface = before_stage["surface"]
                    after_surface = after_stage["surface"]
                    if (
                        abs(float(before_surface["x_left"]) - float(after_surface["x_left"])) > 1e-12
                        or abs(float(before_surface["x_right"]) - float(after_surface["x_right"])) > 1e-12
                        or abs(float(before_surface["r"]) - float(after_surface["r"])) > 1e-12
                    ):
                        any_stage_delta = True

                    observed_fos = float(after_stage["fos"])
                    observed_surface = after_stage["surface"]
                    self.assertLessEqual(abs(observed_fos - reference.fos), FOS_TOL)
                    self.assertLessEqual(abs(observed_surface["x_left"] - reference.left[0]), ENDPOINT_TOL)
                    self.assertLessEqual(abs(observed_surface["y_left"] - reference.left[1]), ENDPOINT_TOL)
                    self.assertLessEqual(abs(observed_surface["x_right"] - reference.right[0]), ENDPOINT_TOL)
                    self.assertLessEqual(abs(observed_surface["y_right"] - reference.right[1]), ENDPOINT_TOL)

                    radius_rel_error = abs(observed_surface["r"] - reference.radius) / reference.radius
                    self.assertLessEqual(radius_rel_error, RADIUS_REL_TOL)

        self.assertTrue(any_stage_delta, "Expected at least one case where pre/post polish outputs differ.")


if __name__ == "__main__":
    unittest.main()
