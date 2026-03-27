from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
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


_CASE5_GEOMETRY = GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0)
_CASE5_MATERIAL = MaterialInput(gamma=18.82, c=41.65, phi_deg=15.0)
_CASE5_WATER_SURFACE = ((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0))
_CASE5_PARITY_TOL = 1e-4


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


class GroundwaterCase56RegressionTests(unittest.TestCase):
    def test_case5_hu1_bishop_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="bishop_simplified",
                hu_mode="custom",
                hu_value=1.0,
                surface=PrescribedCircleInput(
                    xc=27.7467380814499,
                    yc=45.4044062550562,
                    r=31.9273936519829,
                    x_left=18.0011387032865,
                    y_left=15.0007591355243,
                    x_right=57.931283727996,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.116900), _CASE5_PARITY_TOL)

    def test_case5_hu1_spencer_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="spencer",
                hu_mode="custom",
                hu_value=1.0,
                surface=PrescribedCircleInput(
                    xc=27.7306356373665,
                    yc=45.3987904209922,
                    r=31.9171335903235,
                    x_left=18.0011387032864,
                    y_left=15.0007591355243,
                    x_right=57.906264452734,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.117220), _CASE5_PARITY_TOL)

    def test_case5_hu_auto_bishop_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="bishop_simplified",
                hu_mode="auto",
                hu_value=None,
                surface=PrescribedCircleInput(
                    xc=27.7989617093161,
                    yc=45.42435160635,
                    r=31.9643522782854,
                    x_left=17.9969901778581,
                    y_left=15.0,
                    x_right=58.0157237820054,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.157570), _CASE5_PARITY_TOL)

    def test_case5_hu_auto_spencer_benchmark(self) -> None:
        result = run_analysis(
            _case5_project(
                method="spencer",
                hu_mode="auto",
                hu_value=None,
                surface=PrescribedCircleInput(
                    xc=27.7989617093161,
                    yc=45.42435160635,
                    r=31.9643522782854,
                    x_left=17.9969901778581,
                    y_left=15.0,
                    x_right=58.0157237820054,
                    y_right=35.0,
                ),
            )
        )
        self.assertLessEqual(abs(result.fos - 1.157480), _CASE5_PARITY_TOL)

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
                    xc=27.7467380814499,
                    yc=45.4044062550562,
                    r=31.9273936519829,
                    x_left=18.0011387032865,
                    y_left=15.0007591355243,
                    x_right=57.931283727996,
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


if __name__ == "__main__":
    unittest.main()
