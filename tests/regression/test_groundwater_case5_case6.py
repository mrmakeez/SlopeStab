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


_CASE5_GEOMETRY = GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0)
_CASE5_MATERIAL = MaterialInput(gamma=18.82, c=41.65, phi_deg=15.0)
_CASE5_WATER_SURFACE = ((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0))
_CASE5_PARITY_TOL = 0.001
_CASE5_BOUNDARY_TOL = 0.0015
_CASE5_WEIGHT_TOL = 0.20
_CASE5_PORE_TOL = 0.01
_CASE5_NORMAL_TOL = 0.22


@dataclass(frozen=True)
class _Case5ParityScenario:
    label: str
    method_label: str
    series_column: int
    s01_path: str
    expected_fos: float
    project: ProjectInput


def _case5_project(*, method: str, hu_mode: str, hu_value: float | None, surface: PrescribedCircleInput) -> ProjectInput:
    return ProjectInput(
        units="metric",
        geometry=_CASE5_GEOMETRY,
        material=_CASE5_MATERIAL,
        analysis=AnalysisInput(
            method=method,
            n_slices=30,
            tolerance=0.0001,
            max_iter=50,
            f_init=1.0,
        ),
        prescribed_surface=surface,
        loads=LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=_CASE5_WATER_SURFACE,
                hu=GroundwaterHuInput(mode=hu_mode, value=hu_value),
                gamma_w=9.81,
            )
        ),
    )


def _case6_project(*, method: str, surface: PrescribedCircleInput) -> ProjectInput:
    return ProjectInput(
        units="metric",
        geometry=GeometryInput(h=-30.0, l=60.0, x_toe=10.0, y_toe=40.0),
        material=MaterialInput(gamma=18.0, c=10.8, phi_deg=40.0),
        analysis=AnalysisInput(
            method=method,
            n_slices=30,
            tolerance=0.0001,
            max_iter=50,
            f_init=1.0,
        ),
        prescribed_surface=surface,
        loads=LoadsInput(
            groundwater=GroundwaterInput(
                model="ru_coefficient",
                ru=0.5,
            )
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


def _parse_minimum_slice_info(path: Path, method_label: str) -> list[tuple[float, float, float, float, float, float]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    header = f"* minimum slice info(xb,xt,yt,yb,yt_soil loc.) method={method_label}"
    try:
        idx = lines.index(header)
    except ValueError as exc:
        raise AssertionError(f"Could not locate minimum slice info block for '{method_label}' in {path}") from exc

    rows: list[tuple[float, float, float, float, float, float]] = []
    seek = idx + 1
    while seek < len(lines) and not lines[seek].startswith("* "):
        fields = lines[seek].split()
        if len(fields) >= 6:
            rows.append(tuple(float(x) for x in fields[:6]))
        seek += 1
    return rows


class GroundwaterCase56RegressionTests(unittest.TestCase):
    def _case5_parity_scenarios(self) -> tuple[_Case5ParityScenario, ...]:
        hu1_bishop_project = _case5_project(
            method="bishop_simplified",
            hu_mode="custom",
            hu_value=1.0,
            surface=PrescribedCircleInput(
                xc=27.7816099623784,
                yc=45.4165765413013,
                r=31.9496411014504,
                x_left=18.0011387032865,
                y_left=15.0007591355243,
                x_right=57.9854921577304,
                y_right=35.0,
            ),
        )
        hu1_spencer_project = _case5_project(
            method="spencer",
            hu_mode="custom",
            hu_value=1.0,
            surface=PrescribedCircleInput(
                xc=27.6258499840977,
                yc=45.3623063863069,
                r=31.8505670075193,
                x_left=18.0011387032865,
                y_left=15.0007591355243,
                x_right=57.7436391635308,
                y_right=35.0,
            ),
        )
        hu_auto_project = _case5_project(
            method="bishop_simplified",
            hu_mode="auto",
            hu_value=None,
            surface=PrescribedCircleInput(
                xc=27.435184386849,
                yc=45.2985429525467,
                r=31.7351010556423,
                x_left=17.9951137322134,
                y_left=15.0,
                x_right=57.4527900886098,
                y_right=35.0,
            ),
        )
        hu_auto_spencer_project = _case5_project(
            method="spencer",
            hu_mode="auto",
            hu_value=None,
            surface=PrescribedCircleInput(
                xc=27.435184386849,
                yc=45.2985429525467,
                r=31.7351010556423,
                x_left=17.9951137322134,
                y_left=15.0,
                x_right=57.4527900886098,
                y_right=35.0,
            ),
        )
        return (
            _Case5ParityScenario(
                label="Case 5 Hu=1 Bishop",
                method_label="bishop simplified",
                series_column=0,
                s01_path="Verification/Bishop/Case 5/Hu=1/Case5_Hu=1.s01",
                expected_fos=1.11619,
                project=hu1_bishop_project,
            ),
            _Case5ParityScenario(
                label="Case 5 Hu=1 Spencer",
                method_label="spencer",
                series_column=1,
                s01_path="Verification/Bishop/Case 5/Hu=1/Case5_Hu=1.s01",
                expected_fos=1.11648,
                project=hu1_spencer_project,
            ),
            _Case5ParityScenario(
                label="Case 5 Hu=Auto Bishop",
                method_label="bishop simplified",
                series_column=0,
                s01_path="Verification/Bishop/Case 5/Hu=Auto/Case5_Hu=Auto.s01",
                expected_fos=1.1572,
                project=hu_auto_project,
            ),
            _Case5ParityScenario(
                label="Case 5 Hu=Auto Spencer",
                method_label="spencer",
                series_column=1,
                s01_path="Verification/Bishop/Case 5/Hu=Auto/Case5_Hu=Auto.s01",
                expected_fos=1.15702,
                project=hu_auto_spencer_project,
            ),
        )

    def test_case5_hu1_bishop_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="bishop_simplified",
                hu_mode="custom",
                hu_value=1.0,
                surface=PrescribedCircleInput(
                    xc=27.7816099623784,
                    yc=45.4165765413013,
                    r=31.9496411014504,
                    x_left=18.0011387032865,
                    y_left=15.0007591355243,
                    x_right=57.9854921577304,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.116190), _CASE5_PARITY_TOL)

    def test_case5_hu1_spencer_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="spencer",
                hu_mode="custom",
                hu_value=1.0,
                surface=PrescribedCircleInput(
                    xc=27.6258499840977,
                    yc=45.3623063863069,
                    r=31.8505670075193,
                    x_left=18.0011387032865,
                    y_left=15.0007591355243,
                    x_right=57.7436391635308,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.116480), _CASE5_PARITY_TOL)

    def test_case5_hu_auto_bishop_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="bishop_simplified",
                hu_mode="auto",
                hu_value=None,
                surface=PrescribedCircleInput(
                    xc=27.435184386849,
                    yc=45.2985429525467,
                    r=31.7351010556423,
                    x_left=17.9951137322134,
                    y_left=15.0,
                    x_right=57.4527900886098,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.157200), _CASE5_PARITY_TOL)

    def test_case5_hu_auto_spencer_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="spencer",
                hu_mode="auto",
                hu_value=None,
                surface=PrescribedCircleInput(
                    xc=27.435184386849,
                    yc=45.2985429525467,
                    r=31.7351010556423,
                    x_left=17.9951137322134,
                    y_left=15.0,
                    x_right=57.4527900886098,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.157020), _CASE5_PARITY_TOL)

    def test_case6_ru_bishop_benchmark(self) -> None:
        result = run_analysis(
            _case6_project(
                method="bishop_simplified",
                surface=PrescribedCircleInput(
                    xc=69.4716746369335,
                    yc=90.1503711737807,
                    r=80.1517372879095,
                    x_left=6.94774912515767,
                    y_left=40.0,
                    x_right=69.9992594556713,
                    y_right=10.0003702721644,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.001250), 0.005)

    def test_case6_ru_spencer_benchmark(self) -> None:
        result = run_analysis(
            _case6_project(
                method="spencer",
                surface=PrescribedCircleInput(
                    xc=69.6211856957322,
                    yc=90.016174054555,
                    r=80.0166969745064,
                    x_left=7.16276650620701,
                    y_left=40.0,
                    x_right=69.9992594556713,
                    y_right=10.0003702721644,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.018880), 0.005)

    def test_metadata_includes_resolved_groundwater_payload(self) -> None:
        result = run_analysis(
            _case5_project(
                method="bishop_simplified",
                hu_mode="custom",
                hu_value=1.0,
                surface=PrescribedCircleInput(
                    xc=27.7816099623784,
                    yc=45.4165765413013,
                    r=31.9496411014504,
                    x_left=18.0011387032865,
                    y_left=15.0007591355243,
                    x_right=57.9854921577304,
                    y_right=35.0,
                ),
            )
        )
        loads = result.metadata.get("loads", {})
        groundwater = loads.get("groundwater")
        self.assertIsNotNone(groundwater)
        assert groundwater is not None
        self.assertEqual(groundwater.get("model"), "water_surfaces")
        self.assertEqual(groundwater.get("gamma_w"), 9.81)
        hu = groundwater.get("hu")
        self.assertIsNotNone(hu)
        assert hu is not None
        self.assertEqual(hu.get("mode"), "custom")
        self.assertEqual(hu.get("value"), 1.0)
        self.assertTrue(any(slc.pore_force > 0.0 for slc in result.slice_results))

    def test_case5_boundary_parity_against_slide2(self) -> None:
        for scenario in self._case5_parity_scenarios():
            with self.subTest(scenario=scenario.label):
                project = scenario.project
                result = run_analysis(project)
                self.assertLessEqual(abs(result.fos - scenario.expected_fos), _CASE5_PARITY_TOL)

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
                s01_rows = _parse_minimum_slice_info(Path(scenario.s01_path), scenario.method_label)
                s01_boundaries = [row[0] for row in s01_rows]
                ours_boundaries = [slices[0].x_left] + [slc.x_right for slc in slices]
                self.assertEqual(len(ours_boundaries), len(s01_boundaries))
                max_dx = max(abs(ours_boundaries[i] - s01_boundaries[i]) for i in range(len(ours_boundaries)))
                self.assertLessEqual(max_dx, _CASE5_BOUNDARY_TOL)

    def test_case5_per_slice_parity_against_slide2(self) -> None:
        for scenario in self._case5_parity_scenarios():
            with self.subTest(scenario=scenario.label):
                project = scenario.project
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

                ours_weights = [slc.weight + slc.external_force_y for slc in slices]
                ours_pore = [slc.pore_force / slc.base_length for slc in slices]
                ours_base_normal = [slc.normal + slc.pore_force for slc in result.slice_results]

                max_weight = max(abs(ours_weights[i] - s01_weights[i]) for i in range(len(ours_weights)))
                max_pore = max(abs(ours_pore[i] - s01_pore[i]) for i in range(len(ours_pore)))
                max_base_normal = max(
                    abs(ours_base_normal[i] - s01_base_normal[i]) for i in range(len(ours_base_normal))
                )
                self.assertLessEqual(max_weight, _CASE5_WEIGHT_TOL)
                self.assertLessEqual(max_pore, _CASE5_PORE_TOL)
                self.assertLessEqual(max_base_normal, _CASE5_NORMAL_TOL)


if __name__ == "__main__":
    unittest.main()
