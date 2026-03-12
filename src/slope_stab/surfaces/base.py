from __future__ import annotations

from abc import ABC, abstractmethod


class SlipSurface(ABC):
    @abstractmethod
    def y_base(self, x: float) -> float:
        raise NotImplementedError

    @abstractmethod
    def is_within_domain(self, x: float) -> bool:
        raise NotImplementedError
