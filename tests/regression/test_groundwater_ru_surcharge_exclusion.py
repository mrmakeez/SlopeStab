from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.models import (
    AnalysisInput,
    GeometryInput,
    GroundwaterInput,
    LoadsInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
    UniformSurchargeInput,
)


def _case6_project(
    *,
    method: str,
    surface: PrescribedCircleInput,
    surcharge_kpa: float | None,
) -> ProjectInput:
    loads = LoadsInput(
        groundwater=GroundwaterInput(model="ru_coefficient", ru=0.5),
        uniform_surcharge=(
            None
            if surcharge_kpa is None
            else UniformSurchargeInput(magnitude_kpa=surcharge_kpa, placement="crest_infinite")
        ),
    )
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
        loads=loads,
    )


class GroundwaterRuSurchargeExclusionTests(unittest.TestCase):
    def test_ru_pore_forces_are_unchanged_by_surcharge_toggle(self) -> None:
        method_surfaces = {
            "bishop_simplified": PrescribedCircleInput(
                xc=69.4716746369335,
                yc=90.1503711737807,
                r=80.1517372879095,
                x_left=6.94774912515767,
                y_left=40.0,
                x_right=69.9992594556713,
                y_right=10.0003702721644,
            ),
            "spencer": PrescribedCircleInput(
                xc=69.6211856957322,
                yc=90.016174054555,
                r=80.0166969745064,
                x_left=7.16276650620701,
                y_left=40.0,
                x_right=69.9992594556713,
                y_right=10.0003702721644,
            ),
        }

        for method, surface in method_surfaces.items():
            with self.subTest(method=method):
                without = run_analysis(_case6_project(method=method, surface=surface, surcharge_kpa=None))
                with_surcharge = run_analysis(_case6_project(method=method, surface=surface, surcharge_kpa=50.0))

                for a, b in zip(without.slice_results, with_surcharge.slice_results):
                    self.assertAlmostEqual(a.pore_force, b.pore_force, places=12)
                    self.assertAlmostEqual(a.pore_x_app, b.pore_x_app, places=12)
                    self.assertAlmostEqual(a.pore_y_app, b.pore_y_app, places=12)


if __name__ == "__main__":
    unittest.main()
