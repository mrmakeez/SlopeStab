from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisInput,
    GeometryInput,
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
)
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


@dataclass(frozen=True)
class _Scenario:
    label: str
    method_label: str
    analysis_method: str
    s01_path: str
    geometry: GeometryInput
    water_surface: tuple[tuple[float, float], ...]
    surface: PrescribedCircleInput
    expected_fos: float
    fos_tolerance: float
    series_column: int


_CASE7_WATER_SURFACE = ((0.0, 4.609), (5.53621, 4.60862), (6.44028, 7.32085), (12.0, 8.0))
_CASE8_WATER_SURFACE = ((0.0, 7.184), (9.8819, 7.18448), (20.0, 9.0))

_SCENARIOS: tuple[_Scenario, ...] = (
    _Scenario(
        label="Case 7 Bishop",
        method_label="bishop simplified",
        analysis_method="bishop_simplified",
        s01_path="Verification/Bishop/Case 7/Case7/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01",
        geometry=GeometryInput(h=6.0, l=2.0, x_toe=5.0, y_toe=3.0),
        water_surface=_CASE7_WATER_SURFACE,
        surface=PrescribedCircleInput(
            xc=1.65885679531231,
            yc=9.0,
            r=6.865877145366,
            x_left=5.00078365866115,
            y_left=3.00235097598346,
            x_right=8.52473394067831,
            y_right=9.0,
        ),
        expected_fos=0.940158,
        fos_tolerance=0.005,
        series_column=0,
    ),
    _Scenario(
        label="Case 7 Spencer",
        method_label="spencer",
        analysis_method="spencer",
        s01_path="Verification/Bishop/Case 7/Case7/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01",
        geometry=GeometryInput(h=6.0, l=2.0, x_toe=5.0, y_toe=3.0),
        water_surface=_CASE7_WATER_SURFACE,
        surface=PrescribedCircleInput(
            xc=2.47419041573854,
            yc=10.3792666017876,
            r=7.75902007436276,
            x_left=5.01615097845115,
            y_left=3.04845293535344,
            x_right=10.1096351411987,
            y_right=9.0,
        ),
        expected_fos=1.049400,
        fos_tolerance=0.02,
        series_column=1,
    ),
    _Scenario(
        label="Case 8 Bishop",
        method_label="bishop simplified",
        analysis_method="bishop_simplified",
        s01_path="Verification/Bishop/Case 8/Case8/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01",
        geometry=GeometryInput(h=6.0, l=7.0, x_toe=5.0, y_toe=3.0),
        water_surface=_CASE8_WATER_SURFACE,
        surface=PrescribedCircleInput(
            xc=5.81157572491755,
            yc=13.042352415468,
            r=10.0749729401736,
            x_left=5.00012832564169,
            y_left=3.00010999340716,
            x_right=15.0400353306367,
            y_right=9.0,
        ),
        expected_fos=2.511620,
        fos_tolerance=0.005,
        series_column=0,
    ),
    _Scenario(
        label="Case 8 Spencer",
        method_label="spencer",
        analysis_method="spencer",
        s01_path="Verification/Bishop/Case 8/Case8/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01",
        geometry=GeometryInput(h=6.0, l=7.0, x_toe=5.0, y_toe=3.0),
        water_surface=_CASE8_WATER_SURFACE,
        surface=PrescribedCircleInput(
            xc=5.81157572491755,
            yc=13.042352415468,
            r=10.0749729401736,
            x_left=5.00012832564169,
            y_left=3.00010999340716,
            x_right=15.0400353306367,
            y_right=9.0,
        ),
        expected_fos=2.505910,
        fos_tolerance=0.02,
        series_column=1,
    ),
)


def _parse_series_column(path: Path, series_name: str, col: int) -> list[float]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    for idx in range(len(lines) - 1):
        if lines[idx] == "* name" and lines[idx + 1] == series_name:
            seek = idx + 2
            while seek < len(lines) and lines[seek] != "* data":
                seek += 1
            seek += 1
            values: list[float] = []
            while seek < len(lines) and not lines[seek].startswith("* "):
                row = lines[seek].split()
                if len(row) > col:
                    values.append(float(row[col]))
                seek += 1
            return values
    raise AssertionError(f"Could not locate series '{series_name}' in {path}")


def _project_for_scenario(scenario: _Scenario) -> ProjectInput:
    return ProjectInput(
        units="metric",
        geometry=scenario.geometry,
        material=MaterialInput(gamma=16.0, c=12.0, phi_deg=38.0),
        analysis=AnalysisInput(
            method=scenario.analysis_method,
            n_slices=50,
            tolerance=0.001,
            max_iter=75,
            f_init=1.0,
        ),
        prescribed_surface=scenario.surface,
        loads=LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=scenario.water_surface,
                hu=GroundwaterHuInput(mode="auto", value=None),
                gamma_w=9.81,
            )
        ),
    )


class GroundwaterCase78RegressionTests(unittest.TestCase):
    def test_case7_case8_fos_parity(self) -> None:
        for scenario in _SCENARIOS:
            with self.subTest(scenario=scenario.label):
                result = run_analysis(_project_for_scenario(scenario))
                self.assertLessEqual(abs(result.fos - scenario.expected_fos), scenario.fos_tolerance)

    def test_ponded_water_generates_external_slice_forces(self) -> None:
        for scenario in _SCENARIOS:
            with self.subTest(scenario=scenario.label):
                result = run_analysis(_project_for_scenario(scenario))
                self.assertTrue(any(abs(s.external_force_x) > 1e-9 for s in result.slice_results))
                self.assertTrue(any(s.external_force_y > 0.0 for s in result.slice_results))

    def test_bishop_first_10_slice_parity_against_slide2(self) -> None:
        for scenario in _SCENARIOS:
            if scenario.analysis_method != "bishop_simplified":
                continue
            with self.subTest(scenario=scenario.label):
                project = _project_for_scenario(scenario)
                result = run_analysis(project)
                assert project.prescribed_surface is not None
                profile = UniformSlopeProfile(
                    h=project.geometry.h,
                    l=project.geometry.l,
                    x_toe=project.geometry.x_toe,
                    y_toe=project.geometry.y_toe,
                )
                slices = generate_vertical_slices(
                    profile=profile,
                    surface=CircularSlipSurface(
                        xc=project.prescribed_surface.xc,
                        yc=project.prescribed_surface.yc,
                        r=project.prescribed_surface.r,
                    ),
                    n_slices=project.analysis.n_slices,
                    x_left=project.prescribed_surface.x_left,
                    x_right=project.prescribed_surface.x_right,
                    gamma=project.material.gamma,
                    loads=project.loads,
                )
                s01_path = Path(scenario.s01_path)
                s01_weights = _parse_series_column(s01_path, "Slice Weight", scenario.series_column)
                s01_pore = _parse_series_column(s01_path, "Pore Pressure", scenario.series_column)
                s01_base_normal = _parse_series_column(s01_path, "Base Normal Force", scenario.series_column)

                ours_weights = [sl.weight + sl.external_force_y for sl in slices]
                ours_pore = [sl.pore_force / sl.base_length for sl in slices]
                ours_base_normal = [sl.normal + sl.pore_force for sl in result.slice_results]

                first_n = 10
                max_weight = max(abs(ours_weights[i] - s01_weights[i]) for i in range(first_n))
                max_pore = max(abs(ours_pore[i] - s01_pore[i]) for i in range(first_n))
                max_base_normal = max(abs(ours_base_normal[i] - s01_base_normal[i]) for i in range(first_n))

                self.assertLessEqual(max_weight, 0.15)
                self.assertLessEqual(max_pore, 0.03)
                self.assertLessEqual(max_base_normal, 0.15)


if __name__ == "__main__":
    unittest.main()
