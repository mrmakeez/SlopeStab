from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GeometryInput:
    h: float
    l: float
    x_toe: float
    y_toe: float


@dataclass(frozen=True)
class MaterialInput:
    gamma: float
    c: float
    phi_deg: float


@dataclass(frozen=True)
class AnalysisInput:
    method: str
    n_slices: int
    tolerance: float
    max_iter: int
    f_init: float = 1.0


@dataclass(frozen=True)
class PrescribedCircleInput:
    xc: float
    yc: float
    r: float
    x_left: float
    y_left: float
    x_right: float
    y_right: float


@dataclass(frozen=True)
class SearchLimitsInput:
    x_min: float
    x_max: float


@dataclass(frozen=True)
class AutoRefineSearchInput:
    divisions_along_slope: int
    circles_per_division: int
    iterations: int
    divisions_to_use_next_iteration_pct: float
    search_limits: SearchLimitsInput


@dataclass(frozen=True)
class SearchInput:
    method: str
    auto_refine_circular: AutoRefineSearchInput


@dataclass(frozen=True)
class ProjectInput:
    units: str
    geometry: GeometryInput
    material: MaterialInput
    analysis: AnalysisInput
    prescribed_surface: PrescribedCircleInput | None = None
    search: SearchInput | None = None


@dataclass(frozen=True)
class SliceGeometry:
    slice_id: int
    x_left: float
    x_right: float
    y_top_left: float
    y_top_right: float
    y_base_left: float
    y_base_right: float
    width: float
    area: float
    weight: float
    alpha_rad: float
    base_length: float


@dataclass(frozen=True)
class IterationState:
    iteration: int
    fos: float
    delta: float
    numerator: float
    denominator: float


@dataclass(frozen=True)
class SliceResult:
    slice_id: int
    x_left: float
    x_right: float
    width: float
    area: float
    weight: float
    alpha_deg: float
    base_length: float
    normal: float
    shear_strength: float
    driving_component: float
    friction_component: float
    cohesion_component: float
    m_alpha: float


@dataclass
class AnalysisResult:
    fos: float
    converged: bool
    iterations: int
    residual: float
    driving_moment: float
    resisting_moment: float
    warnings: list[str] = field(default_factory=list)
    slice_results: list[SliceResult] = field(default_factory=list)
    iteration_history: list[IterationState] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slice_results"] = [asdict(s) for s in self.slice_results]
        payload["iteration_history"] = [asdict(s) for s in self.iteration_history]
        return payload
