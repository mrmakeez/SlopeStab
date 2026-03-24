from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.exceptions import ConvergenceError
from slope_stab.analysis import run_analysis
from slope_stab.models import (
    AnalysisInput,
    GeometryInput,
    LoadsInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
    UniformSurchargeInput,
)


def _case3_project(method: str) -> ProjectInput:
    return ProjectInput(
        units="metric",
        geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
        material=MaterialInput(gamma=20.0, c=3.0, phi_deg=19.6),
        analysis=AnalysisInput(
            method=method,
            n_slices=25,
            tolerance=0.0001,
            max_iter=100,
            f_init=1.0,
        ),
        prescribed_surface=PrescribedCircleInput(
            xc=49.898,
            yc=35.068,
            r=0.189,
            x_left=49.8059083395470,
            y_left=34.9029541697735,
            x_right=50.0743434149607,
            y_right=35.000,
        ),
        loads=LoadsInput(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=100.0,
                placement="crest_infinite",
            )
        ),
    )


class Case3SurchargeRegressionTests(unittest.TestCase):
    def test_bishop_matches_slide2_case3_surcharge_reference(self) -> None:
        result = run_analysis(_case3_project("bishop_simplified"))
        self.assertLessEqual(abs(result.fos - 0.609948), 0.005)

    def test_spencer_reports_invalid_surface_under_malpha_rule(self) -> None:
        with self.assertRaises(ConvergenceError):
            run_analysis(_case3_project("spencer"))


if __name__ == "__main__":
    unittest.main()
