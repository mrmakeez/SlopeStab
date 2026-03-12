from __future__ import annotations

from abc import ABC, abstractmethod

from slope_stab.models import AnalysisResult, SliceGeometry


class LEMSolver(ABC):
    @abstractmethod
    def solve(self, slices: list[SliceGeometry]) -> AnalysisResult:
        raise NotImplementedError
