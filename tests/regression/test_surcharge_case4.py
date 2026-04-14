from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.materials.uniform_soils import build_uniform_soils_for_geometry
from slope_stab.models import (
    AnalysisInput,
    GeometryInput,
    LoadsInput,
    PrescribedCircleInput,
    ProjectInput,
    UniformSurchargeInput,
)


def _case4_project(method: str) -> ProjectInput:
    geometry = GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=16.0, cohesion=9.0, phi_deg=32.0),
        analysis=AnalysisInput(
            method=method,
            n_slices=25,
            tolerance=0.0001,
            max_iter=100,
            f_init=1.0,
        ),
        prescribed_surface=PrescribedCircleInput(
            xc=20.009,
            yc=70.632,
            r=46.713,
            x_left=30.000,
            y_left=25.000,
            x_right=59.061,
            y_right=45.000,
        ),
        loads=LoadsInput(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=50.0,
                placement="crest_infinite",
            )
        ),
    )


class Case4SurchargeRegressionTests(unittest.TestCase):
    def test_bishop_matches_slide2_case4_surcharge_reference(self) -> None:
        result = run_analysis(_case4_project("bishop_simplified"))
        self.assertLessEqual(abs(result.fos - 1.159740), 0.005)

    def test_spencer_matches_slide2_case4_surcharge_reference(self) -> None:
        result = run_analysis(_case4_project("spencer"))
        self.assertLessEqual(abs(result.fos - 1.155970), 0.005)


if __name__ == "__main__":
    unittest.main()
