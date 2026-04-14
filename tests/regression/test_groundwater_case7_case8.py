from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

import numpy as np

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.lem_core.spencer import SpencerSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.materials.uniform_soils import build_uniform_soils_for_geometry
from slope_stab.models import (
    AnalysisInput,
    AnalysisResult,
    GeometryInput,
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
    PrescribedCircleInput,
    ProjectInput,
    SliceGeometry,
)
from slope_stab.slicing.slice_generator import (
    _NEG_HEIGHT_TOL,
    _VERTICAL_TOL,
    _combine_external_resultants,
    _groundwater_pore_resultant,
    _integration_nodes,
    _ponded_water_top_resultant,
    generate_vertical_slices,
)
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
    production_weight_tol: float
    production_pore_tol: float
    production_normal_tol: float
    boundary_tol: float
    exact_weight_tol: float
    exact_pore_tol: float
    exact_normal_tol: float
    expected_spencer_solve_path: str | None = None


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
        fos_tolerance=0.001,
        series_column=0,
        production_weight_tol=0.1,
        production_pore_tol=0.1,
        production_normal_tol=0.1,
        boundary_tol=0.0015,
        exact_weight_tol=0.002,
        exact_pore_tol=0.001,
        exact_normal_tol=0.01,
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
        fos_tolerance=0.001,
        series_column=1,
        production_weight_tol=0.1,
        production_pore_tol=0.1,
        production_normal_tol=0.1,
        boundary_tol=0.0015,
        exact_weight_tol=0.002,
        exact_pore_tol=0.001,
        exact_normal_tol=0.01,
        expected_spencer_solve_path="lambda_zero_fallback",
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
        fos_tolerance=0.001,
        series_column=0,
        production_weight_tol=0.1,
        production_pore_tol=0.1,
        production_normal_tol=0.1,
        boundary_tol=0.0015,
        exact_weight_tol=0.002,
        exact_pore_tol=0.001,
        exact_normal_tol=0.01,
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
        fos_tolerance=0.001,
        series_column=1,
        production_weight_tol=0.1,
        production_pore_tol=0.1,
        production_normal_tol=0.1,
        boundary_tol=0.0015,
        exact_weight_tol=0.002,
        exact_pore_tol=0.001,
        exact_normal_tol=0.01,
        expected_spencer_solve_path="two_dimensional",
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


def _project_for_scenario(scenario: _Scenario) -> ProjectInput:
    return ProjectInput(
        units="metric",
        geometry=scenario.geometry,
        soils=build_uniform_soils_for_geometry(geometry=scenario.geometry, gamma=16.0, cohesion=12.0, phi_deg=38.0),
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


def _generate_slices_with_edges(project: ProjectInput, x_edges: np.ndarray) -> list[SliceGeometry]:
    assert project.prescribed_surface is not None
    profile = UniformSlopeProfile(
        h=project.geometry.h,
        l=project.geometry.l,
        x_toe=project.geometry.x_toe,
        y_toe=project.geometry.y_toe,
    )
    surface = CircularSlipSurface(
        xc=project.prescribed_surface.xc,
        yc=project.prescribed_surface.yc,
        r=project.prescribed_surface.r,
    )
    loads = project.loads

    x_nodes = _integration_nodes(x_edges, profile)
    y_top_nodes = profile.y_ground_array(x_nodes)
    y_base_nodes = surface.y_base_array(x_nodes)
    heights_nodes = y_top_nodes - y_base_nodes
    if np.any(heights_nodes < -_NEG_HEIGHT_TOL):
        raise AssertionError("Negative heights encountered while building exact-edge slices.")

    segment_areas = 0.5 * (heights_nodes[:-1] + heights_nodes[1:]) * (x_nodes[1:] - x_nodes[:-1])
    cumulative_area = np.concatenate((np.array([0.0]), np.cumsum(segment_areas)))
    edge_indices = np.searchsorted(x_nodes, x_edges)
    slice_areas = cumulative_area[edge_indices[1:]] - cumulative_area[edge_indices[:-1]]

    y_top_edges = y_top_nodes[edge_indices]
    y_base_edges = y_base_nodes[edge_indices]
    dx = x_edges[1:] - x_edges[:-1]

    alpha = np.arctan2(y_base_edges[1:] - y_base_edges[:-1], dx)
    cos_alpha = np.cos(alpha)
    if np.any(np.abs(cos_alpha) < _VERTICAL_TOL):
        raise AssertionError("Near-vertical base encountered while building exact-edge slices.")
    base_length = dx / cos_alpha
    material = project.soils.materials[0]
    weights = material.gamma * slice_areas

    groundwater = loads.groundwater if loads is not None else None
    slices: list[SliceGeometry] = []
    for i in range(len(dx)):
        x_left = float(x_edges[i])
        x_right = float(x_edges[i + 1])
        x_mid = 0.5 * (x_left + x_right)
        y_mid = 0.5 * (float(y_top_edges[i]) + float(y_top_edges[i + 1]))

        ext_resultants: list[tuple[float, float, float, float]] = []
        if groundwater is not None and groundwater.model == "water_surfaces":
            fx, fy, x_app, y_app = _ponded_water_top_resultant(
                profile=profile,
                groundwater=groundwater,
                x_left=x_left,
                x_right=x_right,
            )
            if abs(fx) > _VERTICAL_TOL or abs(fy) > _VERTICAL_TOL:
                ext_resultants.append((fx, fy, x_app, y_app))

        ext_force_x, ext_force_y, ext_x_app, ext_y_app = _combine_external_resultants(
            resultants=ext_resultants,
            x_mid=x_mid,
            y_mid=y_mid,
        )

        pore_force, pore_x_app, pore_y_app = _groundwater_pore_resultant(
            groundwater=groundwater,
            x_left=x_left,
            x_right=x_right,
            y_base_left=float(y_base_edges[i]),
            y_base_right=float(y_base_edges[i + 1]),
            width=float(dx[i]),
            base_length=float(base_length[i]),
            weight=float(weights[i]),
        )

        slices.append(
            SliceGeometry(
                slice_id=i + 1,
                x_left=x_left,
                x_right=x_right,
                y_top_left=float(y_top_edges[i]),
                y_top_right=float(y_top_edges[i + 1]),
                y_base_left=float(y_base_edges[i]),
                y_base_right=float(y_base_edges[i + 1]),
                width=float(dx[i]),
                area=float(slice_areas[i]),
                weight=float(weights[i]),
                alpha_rad=float(alpha[i]),
                base_length=float(base_length[i]),
                external_force_x=float(ext_force_x),
                external_force_y=float(ext_force_y),
                external_x_app=float(ext_x_app),
                external_y_app=float(ext_y_app),
                pore_force=float(pore_force),
                pore_x_app=float(pore_x_app),
                pore_y_app=float(pore_y_app),
            )
        )
    return slices


def _solve_with_exact_edges(
    scenario: _Scenario,
) -> tuple[list[SliceGeometry], AnalysisResult]:
    project = _project_for_scenario(scenario)
    s01_path = Path(scenario.s01_path)
    min_rows = _parse_minimum_slice_info(s01_path, scenario.method_label)
    x_edges = np.asarray([row[0] for row in min_rows], dtype=float)

    slices = _generate_slices_with_edges(project, x_edges)
    soil = project.soils.materials[0]
    material = MohrCoulombMaterial(
        gamma=soil.gamma,
        cohesion=soil.c,
        phi_deg=soil.phi_deg,
    )
    assert project.prescribed_surface is not None
    surface = CircularSlipSurface(
        xc=project.prescribed_surface.xc,
        yc=project.prescribed_surface.yc,
        r=project.prescribed_surface.r,
    )
    if scenario.analysis_method == "bishop_simplified":
        solver = BishopSimplifiedSolver(material, project.analysis, surface)
    else:
        solver = SpencerSolver(material, project.analysis, surface)
    return slices, solver.solve(slices)


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

    def test_spencer_metadata_reports_solver_path(self) -> None:
        for scenario in _SCENARIOS:
            if scenario.expected_spencer_solve_path is None:
                continue
            with self.subTest(scenario=scenario.label):
                result = run_analysis(_project_for_scenario(scenario))
                spencer_meta = result.metadata.get("spencer", {})
                self.assertEqual(spencer_meta.get("solve_path"), scenario.expected_spencer_solve_path)

    def test_full_slice_parity_against_slide2_production_layout(self) -> None:
        for scenario in _SCENARIOS:
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
                material = project.soils.materials[0]
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
                    gamma=material.gamma,
                    loads=project.loads,
                )
                s01_path = Path(scenario.s01_path)
                s01_weights = _parse_series_column(s01_path, "Slice Weight", scenario.series_column)
                s01_pore = _parse_series_column(s01_path, "Pore Pressure", scenario.series_column)
                s01_base_normal = _parse_series_column(s01_path, "Base Normal Force", scenario.series_column)

                ours_weights = [sl.weight + sl.external_force_y for sl in slices]
                ours_pore = [sl.pore_force / sl.base_length for sl in slices]
                ours_base_normal = [sl.normal + sl.pore_force for sl in result.slice_results]
                self.assertEqual(len(ours_weights), len(s01_weights))
                self.assertEqual(len(ours_pore), len(s01_pore))
                self.assertEqual(len(ours_base_normal), len(s01_base_normal))

                max_weight = max(abs(ours_weights[i] - s01_weights[i]) for i in range(len(ours_weights)))
                max_pore = max(abs(ours_pore[i] - s01_pore[i]) for i in range(len(ours_pore)))
                max_base_normal = max(
                    abs(ours_base_normal[i] - s01_base_normal[i]) for i in range(len(ours_base_normal))
                )

                self.assertLessEqual(max_weight, scenario.production_weight_tol)
                self.assertLessEqual(max_pore, scenario.production_pore_tol)
                self.assertLessEqual(max_base_normal, scenario.production_normal_tol)

    def test_boundary_parity_diagnostics_against_slide2(self) -> None:
        for scenario in _SCENARIOS:
            with self.subTest(scenario=scenario.label):
                project = _project_for_scenario(scenario)
                assert project.prescribed_surface is not None
                profile = UniformSlopeProfile(
                    h=project.geometry.h,
                    l=project.geometry.l,
                    x_toe=project.geometry.x_toe,
                    y_toe=project.geometry.y_toe,
                )
                material = project.soils.materials[0]
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
                    gamma=material.gamma,
                    loads=project.loads,
                )
                s01_rows = _parse_minimum_slice_info(Path(scenario.s01_path), scenario.method_label)
                s01_boundaries = [row[0] for row in s01_rows]
                ours_boundaries = [slices[0].x_left] + [sl.x_right for sl in slices]
                self.assertEqual(len(ours_boundaries), len(s01_boundaries))
                max_dx = max(
                    abs(ours_boundaries[i] - s01_boundaries[i]) for i in range(len(ours_boundaries))
                )
                self.assertLessEqual(max_dx, scenario.boundary_tol)

    def test_exact_boundary_tooling_full_slice_parity(self) -> None:
        for scenario in _SCENARIOS:
            with self.subTest(scenario=scenario.label):
                slices, result = _solve_with_exact_edges(scenario)
                s01_path = Path(scenario.s01_path)
                s01_weights = _parse_series_column(s01_path, "Slice Weight", scenario.series_column)
                s01_pore = _parse_series_column(s01_path, "Pore Pressure", scenario.series_column)
                s01_base_normal = _parse_series_column(s01_path, "Base Normal Force", scenario.series_column)

                ours_weights = [sl.weight + sl.external_force_y for sl in slices]
                ours_pore = [sl.pore_force / sl.base_length for sl in slices]
                ours_base_normal = [sl.normal + sl.pore_force for sl in result.slice_results]

                max_weight = max(abs(ours_weights[i] - s01_weights[i]) for i in range(len(ours_weights)))
                max_pore = max(abs(ours_pore[i] - s01_pore[i]) for i in range(len(ours_pore)))
                max_base_normal = max(
                    abs(ours_base_normal[i] - s01_base_normal[i]) for i in range(len(ours_base_normal))
                )
                self.assertLessEqual(max_weight, scenario.exact_weight_tol)
                self.assertLessEqual(max_pore, scenario.exact_pore_tol)
                self.assertLessEqual(max_base_normal, scenario.exact_normal_tol)
                self.assertLessEqual(abs(result.fos - scenario.expected_fos), scenario.fos_tolerance)


if __name__ == "__main__":
    unittest.main()
