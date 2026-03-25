"""Placeholder models reserved for future surcharge and groundwater extensions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NullLoadModel:
    pass


@dataclass(frozen=True)
class NullPorePressureModel:
    pass
