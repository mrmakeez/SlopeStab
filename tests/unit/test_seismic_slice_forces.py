from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import GroundwaterHuInput, GroundwaterInput, LoadsInput, SeismicLoadInput, UniformSurchargeInput
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


class SeismicSliceForceTests(unittest.TestCase):
    def test_pseudo_static_seismic_applies_horizontal_force_from_soil_weight(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        surface = CircularSlipSurface(xc=13.689, yc=25.558, r=15.989)
        loads = LoadsInput(seismic=SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0))
        slices = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=7,
            x_left=10.0005216402222,
            x_right=27.4990237870903,
            gamma=20.0,
            loads=loads,
        )

        for slc in slices:
            self.assertAlmostEqual(slc.seismic_force_x, 0.132 * slc.weight, places=12)
            self.assertAlmostEqual(slc.seismic_force_y, 0.0, places=12)
            self.assertAlmostEqual(slc.external_force_x, slc.seismic_force_x, places=12)
            self.assertAlmostEqual(slc.external_force_y, 0.0, places=12)

    def test_seismic_force_is_independent_of_surcharge_vertical_force(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        surface = CircularSlipSurface(xc=13.689, yc=25.558, r=15.989)
        seismic_only = LoadsInput(seismic=SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0))
        seismic_with_surcharge = LoadsInput(
            seismic=SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0),
            uniform_surcharge=UniformSurchargeInput(magnitude_kpa=10.0, placement="crest_infinite"),
        )
        slices_a = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=7,
            x_left=10.0005216402222,
            x_right=27.4990237870903,
            gamma=20.0,
            loads=seismic_only,
        )
        slices_b = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=7,
            x_left=10.0005216402222,
            x_right=27.4990237870903,
            gamma=20.0,
            loads=seismic_with_surcharge,
        )

        for a, b in zip(slices_a, slices_b):
            self.assertAlmostEqual(a.seismic_force_x, b.seismic_force_x, places=12)
            self.assertAlmostEqual(b.seismic_force_x, 0.132 * b.weight, places=12)

    def test_case10_ponded_and_surcharge_channels_remain_additive_with_seismic(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        surface = CircularSlipSurface(xc=16.6916223321657, yc=25.6398893956998, r=17.0901183698696)
        common_loads = dict(
            uniform_surcharge=UniformSurchargeInput(
                magnitude_kpa=50.0,
                placement="crest_range",
                x_start=25.0,
                x_end=35.0,
            ),
            groundwater=GroundwaterInput(
                model="water_surfaces",
                surface=((0.0, 11.0), (12.0, 11.0), (25.0, 15.0), (35.0, 15.0)),
                hu=GroundwaterHuInput(mode="custom", value=1.0),
                gamma_w=9.81,
            ),
        )
        baseline = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=50,
            x_left=9.80206461149667,
            x_right=31.7187426990865,
            gamma=20.0,
            loads=LoadsInput(**common_loads),
        )
        with_seismic = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=50,
            x_left=9.80206461149667,
            x_right=31.7187426990865,
            gamma=20.0,
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.25, kv=0.0),
                **common_loads,
            ),
        )

        for base, seis in zip(baseline, with_seismic):
            self.assertAlmostEqual(seis.seismic_force_x, 0.25 * seis.weight, places=12)
            self.assertAlmostEqual(seis.external_force_x - base.external_force_x, seis.seismic_force_x, places=12)
            self.assertAlmostEqual(seis.external_force_y, base.external_force_y, places=12)


if __name__ == "__main__":
    unittest.main()
