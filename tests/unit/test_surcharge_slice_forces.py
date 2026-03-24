from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import GroundwaterInput, LoadsInput, SeismicLoadInput, UniformSurchargeInput
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


class SurchargeSliceForceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        self.surface = CircularSlipSurface(xc=13.689, yc=25.558, r=15.989)
        self.x_left = 10.0005216402222
        self.x_right = 27.4990237870903
        self.n_slices = 7
        self.gamma = 20.0

    def test_no_loads_has_zero_external_force(self) -> None:
        slices = generate_vertical_slices(
            profile=self.profile,
            surface=self.surface,
            n_slices=self.n_slices,
            x_left=self.x_left,
            x_right=self.x_right,
            gamma=self.gamma,
            loads=None,
        )
        self.assertTrue(all(s.external_force_x == 0.0 for s in slices))
        self.assertTrue(all(s.external_force_y == 0.0 for s in slices))
        self.assertTrue(all(abs(s.total_vertical_force - s.weight) < 1e-12 for s in slices))

    def test_crest_infinite_surcharge_force_sum_matches_overlap(self) -> None:
        loads = LoadsInput(
            uniform_surcharge=UniformSurchargeInput(magnitude_kpa=10.0, placement="crest_infinite"),
            seismic=SeismicLoadInput(model="none"),
            groundwater=GroundwaterInput(model="none"),
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
        expected_overlap = self.x_right - max(self.x_left, self.profile.crest_x)
        expected_force = 10.0 * expected_overlap
        observed_force = sum(s.external_force_y for s in slices)
        self.assertAlmostEqual(observed_force, expected_force, places=9)
        self.assertTrue(any(s.external_force_y > 0.0 for s in slices))

    def test_crest_range_surcharge_force_sum_matches_overlap(self) -> None:
        loads = LoadsInput(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=10.0,
                placement="crest_range",
                x_start=26.0,
                x_end=27.0,
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
        observed_force = sum(s.external_force_y for s in slices)
        self.assertAlmostEqual(observed_force, 10.0, places=9)

    def test_zero_magnitude_surcharge_is_invariant(self) -> None:
        loads = LoadsInput(
            uniform_surcharge=UniformSurchargeInput(magnitude_kpa=0.0, placement="crest_infinite")
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
        self.assertTrue(all(abs(s.external_force_y) < 1e-12 for s in slices))
        self.assertTrue(all(abs(s.total_vertical_force - s.weight) < 1e-12 for s in slices))


if __name__ == "__main__":
    unittest.main()
