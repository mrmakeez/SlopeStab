from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.materials.uniform_soils import build_uniform_soils_for_geometry
from slope_stab.models import (
    AnalysisInput,
    AutoRefineSearchInput,
    GeometryInput,
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
    ProjectInput,
    SearchInput,
    SearchLimitsInput,
)


def _water_surfaces_auto_refine_project() -> ProjectInput:
    geometry = GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0)
    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=18.82, cohesion=41.65, phi_deg=15.0),
        analysis=AnalysisInput(
            method="bishop_simplified",
            n_slices=20,
            tolerance=0.0001,
            max_iter=30,
            f_init=1.0,
        ),
        prescribed_surface=None,
        search=SearchInput(
            method="auto_refine_circular",
            auto_refine_circular=AutoRefineSearchInput(
                divisions_along_slope=4,
                circles_per_division=5,
                iterations=1,
                divisions_to_use_next_iteration_pct=25.0,
                search_limits=SearchLimitsInput(x_min=0.0, x_max=66.0),
            ),
        ),
        loads=LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0)),
                hu=GroundwaterHuInput(mode="auto", value=None),
                gamma_w=9.81,
            )
        ),
    )


class WaterSurfacesSearchDeterminismTests(unittest.TestCase):
    def test_auto_refine_repeatable_for_water_surfaces(self) -> None:
        project = _water_surfaces_auto_refine_project()
        first = run_analysis(project)
        second = run_analysis(project)

        self.assertAlmostEqual(first.fos, second.fos, places=12)
        self.assertEqual(first.metadata["prescribed_surface"], second.metadata["prescribed_surface"])
        self.assertEqual(first.metadata["search"]["valid_surfaces"], second.metadata["search"]["valid_surfaces"])
        self.assertEqual(first.metadata["search"]["invalid_surfaces"], second.metadata["search"]["invalid_surfaces"])


if __name__ == "__main__":
    unittest.main()
