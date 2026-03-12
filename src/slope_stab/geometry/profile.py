from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniformSlopeProfile:
    """Piecewise-linear slope with infinite flat toe and crest extent."""

    h: float
    l: float
    x_toe: float
    y_toe: float

    @property
    def crest_x(self) -> float:
        return self.x_toe + self.l

    @property
    def crest_y(self) -> float:
        return self.y_toe + self.h

    @property
    def slope_gradient(self) -> float:
        return self.h / self.l

    def y_ground(self, x: float) -> float:
        if x <= self.x_toe:
            return self.y_toe
        if x >= self.crest_x:
            return self.crest_y
        return self.y_toe + self.slope_gradient * (x - self.x_toe)
