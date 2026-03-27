from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import GroundwaterHuInput, GroundwaterInput, LoadsInput
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


class GroundwaterSliceForceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = UniformSlopeProfile(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0)
        self.surface = CircularSlipSurface(xc=27.747, yc=45.404, r=31.927)
        self.x_left = 18.001230966286172
        self.x_right = 57.93126929710242
        self.n_slices = 30
        self.gamma = 18.82
        self.water_surface = ((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0))

    def test_water_surfaces_custom_generates_positive_pore_forces(self) -> None:
        loads = LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=self.water_surface,
                hu=GroundwaterHuInput(mode="custom", value=1.0),
                gamma_w=9.81,
            )
        )
        slices = generate_vertical_slices(
            profile=self.profile,
            surface=self.surface,
            n_slices=self.n_slices,
            x_left=self.x_left,
            x_right=self.x_right,
            gamma=self.gamma,
            loads=loads,
        )
        self.assertTrue(any(s.pore_force > 0.0 for s in slices))
        self.assertTrue(all(s.pore_force >= 0.0 for s in slices))

    def test_water_surfaces_auto_is_not_greater_than_custom_for_same_surface(self) -> None:
        custom_loads = LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=self.water_surface,
                hu=GroundwaterHuInput(mode="custom", value=1.0),
                gamma_w=9.81,
            )
        )
        auto_loads = LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=self.water_surface,
                hu=GroundwaterHuInput(mode="auto"),
                gamma_w=9.81,
            )
        )
        custom_slices = generate_vertical_slices(
            profile=self.profile,
            surface=self.surface,
            n_slices=self.n_slices,
            x_left=self.x_left,
            x_right=self.x_right,
            gamma=self.gamma,
            loads=custom_loads,
        )
        auto_slices = generate_vertical_slices(
            profile=self.profile,
            surface=self.surface,
            n_slices=self.n_slices,
            x_left=self.x_left,
            x_right=self.x_right,
            gamma=self.gamma,
            loads=auto_loads,
        )
        self.assertLessEqual(
            sum(s.pore_force for s in auto_slices),
            sum(s.pore_force for s in custom_slices) + 1e-9,
        )

    def test_water_surface_out_of_range_is_explicit_error(self) -> None:
        loads = LoadsInput(
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=((18.0, 15.0), (48.0, 29.0)),
                hu=GroundwaterHuInput(mode="custom", value=1.0),
                gamma_w=9.81,
            )
        )
        with self.assertRaises(GeometryError):
            generate_vertical_slices(
                profile=self.profile,
                surface=self.surface,
                n_slices=self.n_slices,
                x_left=self.x_left,
                x_right=self.x_right,
                gamma=self.gamma,
                loads=loads,
            )

    def test_ru_pore_force_matches_operational_formula(self) -> None:
        ru = 0.5
        loads = LoadsInput(groundwater=GroundwaterInput(model="ru_coefficient", ru=ru))
        slices = generate_vertical_slices(
            profile=self.profile,
            surface=self.surface,
            n_slices=self.n_slices,
            x_left=self.x_left,
            x_right=self.x_right,
            gamma=self.gamma,
            loads=loads,
        )
        for slc in slices:
            expected = ru * (slc.weight / slc.width) * slc.base_length
            self.assertAlmostEqual(slc.pore_force, expected, places=10)


if __name__ == "__main__":
    unittest.main()
