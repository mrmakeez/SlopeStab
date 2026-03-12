from __future__ import annotations

import math
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.surfaces.circular import CircularSlipSurface


class GeometryTests(unittest.TestCase):
    def test_uniform_profile_piecewise(self) -> None:
        profile = UniformSlopeProfile(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0)
        self.assertAlmostEqual(profile.y_ground(20.0), 25.0)
        self.assertAlmostEqual(profile.y_ground(30.0), 25.0)
        self.assertAlmostEqual(profile.y_ground(40.0), 30.0)
        self.assertAlmostEqual(profile.y_ground(50.0), 35.0)
        self.assertAlmostEqual(profile.y_ground(70.0), 35.0)

    def test_circle_base_and_point_residual(self) -> None:
        surface = CircularSlipSurface(xc=13.689, yc=25.558, r=15.989)
        y = surface.y_base(10.0005216402222)
        self.assertAlmostEqual(y, 10.0002608201111, places=6)
        residual = surface.point_error(10.0005216402222, 10.0002608201111)
        self.assertLess(residual, 1e-6)


if __name__ == "__main__":
    unittest.main()
