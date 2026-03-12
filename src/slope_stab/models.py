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
class AutoRefineInput:
    divisions: int = 20
    circles_per_pair: int = 10
    iterations: int = 10
    retain_ratio: float = 0.5
    toe_extension_h: float = 1.0
    crest_extension_h: float = 2.0
    min_span_h: float = 0.10
    radius_max_h: float = 10.0
    seed: int = 42


@dataclass(frozen=True)
class AnalysisInput:
    method: str
    n_slices: int
    tolerance: float
    max_iter: int
    f_init: float = 1.0
    mode: str = "prescribed"


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
class ProjectInput:
    units: str
    geometry: GeometryInput
    material: MaterialInput
    analysis: AnalysisInput
    prescribed_surface: PrescribedCircleInput | None = None
    auto_refine: AutoRefineInput | None = None


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
    search: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slice_results"] = [asdict(s) for s in self.slice_results]
        payload["iteration_history"] = [asdict(s) for s in self.iteration_history]
        return payload
