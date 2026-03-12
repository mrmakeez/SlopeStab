from __future__ import annotations

from dataclasses import dataclass
import math

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

    def point_error(self, x: float, y: float) -> float:
        return abs((x - self.xc) ** 2 + (y - self.yc) ** 2 - self.r**2)
