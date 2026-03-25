from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from slope_stab.exceptions import GeometryError
from slope_stab.surfaces.base import SlipSurface


@dataclass(frozen=True)
class CircularSlipSurface(SlipSurface):
    xc: float
    yc: float
    r: float

    def is_within_domain(self, x: float) -> bool:
        return (x - self.xc) ** 2 <= self.r**2 + 1e-12

    def y_base(self, x: float) -> float:
        inside = self.r**2 - (x - self.xc) ** 2
        if inside < -1e-10:
            raise GeometryError(
                f"x={x} falls outside prescribed circle domain for xc={self.xc}, r={self.r}."
            )
        return self.yc - math.sqrt(max(inside, 0.0))

    def y_base_array(self, x: np.ndarray) -> np.ndarray:
        x_arr = np.asarray(x, dtype=float)
        inside = self.r**2 - (x_arr - self.xc) ** 2
        if np.any(inside < -1e-10):
            bad_idx = int(np.flatnonzero(inside < -1e-10)[0])
            bad_x = float(x_arr[bad_idx])
            raise GeometryError(
                f"x={bad_x} falls outside prescribed circle domain for xc={self.xc}, r={self.r}."
            )
        return self.yc - np.sqrt(np.maximum(inside, 0.0))

    def point_error(self, x: float, y: float) -> float:
        return abs((x - self.xc) ** 2 + (y - self.yc) ** 2 - self.r**2)
