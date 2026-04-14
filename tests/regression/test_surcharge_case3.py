from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.exceptions import ConvergenceError
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


def _case3_project(method: str, *, surcharge_kpa: float, surface: PrescribedCircleInput) -> ProjectInput:
    geometry = GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0)
    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=20.0, cohesion=3.0, phi_deg=19.6),
        analysis=AnalysisInput(
            method=method,
            n_slices=25,
            tolerance=0.0001,
            max_iter=100,
            f_init=1.0,
        ),
        prescribed_surface=surface,
        loads=LoadsInput(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=surcharge_kpa,
                placement="crest_infinite",
            )
        ),
    )


def _case3_surface_50kpa() -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=27.6485174011401,
        yc=61.5854419184982,
        r=36.6607805519873,
        x_left=30.0003512982362,
        y_left=25.0001756491181,
        x_right=52.891875115183,
        y_right=35.0,
    )


def _case3_surface_100kpa() -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=49.898,
        yc=35.068,
        r=0.189,
        x_left=49.8059083395470,
        y_left=34.9029541697735,
        x_right=50.0743434149607,
        y_right=35.000,
    )


class Case3SurchargeRegressionTests(unittest.TestCase):
    def test_bishop_matches_slide2_case3_surcharge_50kpa_reference(self) -> None:
        result = run_analysis(
            _case3_project(
                "bishop_simplified",
                surcharge_kpa=50.0,
                surface=_case3_surface_50kpa(),
            )
        )
        self.assertLessEqual(abs(result.fos - 0.903987), 0.005)

    def test_spencer_matches_slide2_case3_surcharge_50kpa_reference(self) -> None:
        result = run_analysis(
            _case3_project(
                "spencer",
                surcharge_kpa=50.0,
                surface=_case3_surface_50kpa(),
            )
        )
        self.assertLessEqual(abs(result.fos - 0.903192), 0.005)

    def test_bishop_matches_slide2_case3_surcharge_100kpa_shallow_reference(self) -> None:
        result = run_analysis(
            _case3_project(
                "bishop_simplified",
                surcharge_kpa=100.0,
                surface=_case3_surface_100kpa(),
            )
        )
        self.assertLessEqual(abs(result.fos - 0.609948), 0.005)

    def test_spencer_reports_invalid_surface_under_malpha_rule_for_100kpa(self) -> None:
        with self.assertRaises(ConvergenceError):
            run_analysis(
                _case3_project(
                    "spencer",
                    surcharge_kpa=100.0,
                    surface=_case3_surface_100kpa(),
                )
            )


if __name__ == "__main__":
    unittest.main()
