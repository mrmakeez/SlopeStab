from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MohrCoulombMaterial:
    gamma: float
    cohesion: float
    phi_deg: float

    @property
    def phi_rad(self) -> float:
        return math.radians(self.phi_deg)

    @property
    def tan_phi(self) -> float:
        return math.tan(self.phi_rad)
