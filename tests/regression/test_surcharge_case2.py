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


def _case2_project(*, method: str, surcharge_kpa: float | None) -> ProjectInput:
    geometry = GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
    loads = None
    if surcharge_kpa is not None:
        loads = LoadsInput(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=surcharge_kpa,
                placement="crest_infinite",
            )
        )
    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=20.0, cohesion=20.0, phi_deg=20.0),
        analysis=AnalysisInput(
            method=method,
            n_slices=7,
            tolerance=0.005,
            max_iter=50,
            f_init=1.0,
        ),
        prescribed_surface=PrescribedCircleInput(
            xc=13.689,
            yc=25.558,
            r=15.989,
            x_left=10.0005216402222,
            y_left=10.0002608201111,
            x_right=27.4990237870903,
            y_right=17.500,
        ),
        loads=loads,
    )


class Case2SurchargeRegressionTests(unittest.TestCase):
    def test_zero_surcharge_matches_no_load_for_bishop(self) -> None:
        without = run_analysis(_case2_project(method="bishop_simplified", surcharge_kpa=None))
        with_zero = run_analysis(_case2_project(method="bishop_simplified", surcharge_kpa=0.0))
        self.assertAlmostEqual(without.fos, with_zero.fos, places=12)

    def test_zero_surcharge_matches_no_load_for_spencer(self) -> None:
        without = run_analysis(_case2_project(method="spencer", surcharge_kpa=None))
        with_zero = run_analysis(_case2_project(method="spencer", surcharge_kpa=0.0))
        self.assertAlmostEqual(without.fos, with_zero.fos, places=12)

    def test_bishop_matches_slide2_case2_surcharge_reference(self) -> None:
        result = run_analysis(_case2_project(method="bishop_simplified", surcharge_kpa=10.0))
        self.assertLessEqual(abs(result.fos - 2.02895), 0.005)

    def test_spencer_matches_slide2_case2_surcharge_reference(self) -> None:
        result = run_analysis(_case2_project(method="spencer", surcharge_kpa=10.0))
        self.assertLessEqual(abs(result.fos - 2.02478), 0.005)

    def test_prescribed_metadata_includes_loads_payload(self) -> None:
        result = run_analysis(_case2_project(method="bishop_simplified", surcharge_kpa=10.0))
        loads_meta = result.metadata.get("loads")
        self.assertIsNotNone(loads_meta)
        assert loads_meta is not None
        self.assertIsNotNone(loads_meta.get("uniform_surcharge"))
        surcharge = loads_meta["uniform_surcharge"]
        assert surcharge is not None
        self.assertEqual(surcharge["magnitude_kpa"], 10.0)
        self.assertEqual(surcharge["placement"], "crest_infinite")

    def test_no_load_metadata_is_explicitly_null(self) -> None:
        result = run_analysis(_case2_project(method="bishop_simplified", surcharge_kpa=None))
        loads_meta = result.metadata.get("loads")
        self.assertEqual(
            loads_meta,
            {"uniform_surcharge": None, "seismic": None, "groundwater": None},
        )


if __name__ == "__main__":
    unittest.main()
