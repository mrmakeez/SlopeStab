from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


class SliceGenerationTests(unittest.TestCase):
    def test_case2_slice_geometry_totals(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        surface = CircularSlipSurface(xc=13.689, yc=25.558, r=15.989)
        slices = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=7,
            x_left=10.0005216402222,
            x_right=27.4990237870903,
            gamma=20.0,
        )

        self.assertEqual(len(slices), 7)
        self.assertAlmostEqual(slices[0].width, 2.499786020981157, places=9)

        total_area = sum(s.area for s in slices)
        self.assertAlmostEqual(total_area, 49.1077, places=3)


if __name__ == "__main__":
    unittest.main()
