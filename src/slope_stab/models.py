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
class SoilMaterialInput:
    id: str
    gamma: float
    c: float
    phi_deg: float


@dataclass(frozen=True)
class MaterialInput:
    gamma: float
    c: float
    phi_deg: float


@dataclass(frozen=True)
class SoilRegionAssignmentInput:
    material_id: str
    seed_x: float
    seed_y: float


@dataclass(frozen=True)
class SoilsInput:
    materials: tuple[SoilMaterialInput, ...]
    external_boundary: tuple[tuple[float, float], ...]
    material_boundaries: tuple[tuple[tuple[float, float], ...], ...] = ()
    region_assignments: tuple[SoilRegionAssignmentInput, ...] = ()


@dataclass(frozen=True)
class UniformSurchargeInput:
    magnitude_kpa: float
    placement: str
    x_start: float | None = None
    x_end: float | None = None


@dataclass(frozen=True)
class SeismicLoadInput:
    model: str = "none"
    kh: float = 0.0
    kv: float = 0.0


@dataclass(frozen=True)
class GroundwaterHuInput:
    mode: str
    value: float | None = None


@dataclass(frozen=True)
class GroundwaterInput:
    model: str = "none"
    surface: tuple[tuple[float, float], ...] = ()
    hu: GroundwaterHuInput | None = None
    gamma_w: float = 9.81
    ru: float | None = None


@dataclass(frozen=True)
class LoadsInput:
    uniform_surcharge: UniformSurchargeInput | None = None
    seismic: SeismicLoadInput | None = None
    groundwater: GroundwaterInput | None = None


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
class ParallelExecutionInput:
    mode: str = "auto"
    workers: int = 0
    min_batch_size: int = 1
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class AutoRefineSearchInput:
    divisions_along_slope: int
    circles_per_division: int
    iterations: int
    divisions_to_use_next_iteration_pct: float
    search_limits: SearchLimitsInput
    model_boundary_floor_y: float | None = None


@dataclass(frozen=True)
class DirectGlobalSearchInput:
    max_iterations: int
    max_evaluations: int
    min_improvement: float
    stall_iterations: int
    min_rectangle_half_size: float
    search_limits: SearchLimitsInput


@dataclass(frozen=True)
class CuckooGlobalSearchInput:
    population_size: int
    max_iterations: int
    max_evaluations: int
    discovery_rate: float
    levy_beta: float
    alpha_max: float
    alpha_min: float
    min_improvement: float
    stall_iterations: int
    seed: int
    post_polish: bool
    search_limits: SearchLimitsInput


@dataclass(frozen=True)
class CmaesGlobalSearchInput:
    max_evaluations: int
    direct_prescan_evaluations: int
    cmaes_population_size: int
    cmaes_max_iterations: int
    cmaes_restarts: int
    cmaes_sigma0: float
    polish_max_evaluations: int
    min_improvement: float
    stall_iterations: int
    seed: int
    post_polish: bool
    invalid_penalty: float
    nonconverged_penalty: float
    search_limits: SearchLimitsInput


@dataclass(frozen=True)
class SearchInput:
    method: str
    auto_refine_circular: AutoRefineSearchInput | None = None
    direct_global_circular: DirectGlobalSearchInput | None = None
    cuckoo_global_circular: CuckooGlobalSearchInput | None = None
    cmaes_global_circular: CmaesGlobalSearchInput | None = None
    parallel: ParallelExecutionInput | None = None


@dataclass(frozen=True)
class ProjectInput:
    units: str
    geometry: GeometryInput
    analysis: AnalysisInput
    soils: SoilsInput | None = None
    material: MaterialInput | None = None
    prescribed_surface: PrescribedCircleInput | None = None
    search: SearchInput | None = None
    loads: LoadsInput | None = None

    def __post_init__(self) -> None:
        if self.soils is not None:
            if self.material is None and len(self.soils.materials) == 1:
                only = self.soils.materials[0]
                object.__setattr__(
                    self,
                    "material",
                    MaterialInput(gamma=only.gamma, c=only.c, phi_deg=only.phi_deg),
                )
            return
        if self.material is None:
            raise ValueError("ProjectInput requires soils (or legacy material for constructor compatibility).")
        # Constructor compatibility path for in-repo call sites during soils
        # migration. JSON schema paths reject top-level `material`.
        default_extent = 1_000_000.0
        external_boundary = (
            (-default_extent, -default_extent),
            (default_extent, -default_extent),
            (default_extent, default_extent),
            (-default_extent, default_extent),
        )
        legacy_id = "soil_1"
        object.__setattr__(
            self,
            "soils",
            SoilsInput(
                materials=(
                    SoilMaterialInput(
                        id=legacy_id,
                        gamma=self.material.gamma,
                        c=self.material.c,
                        phi_deg=self.material.phi_deg,
                    ),
                ),
                external_boundary=external_boundary,
                material_boundaries=(),
                region_assignments=(
                    SoilRegionAssignmentInput(material_id=legacy_id, seed_x=0.0, seed_y=0.0),
                ),
            ),
        )


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
    external_force_x: float = 0.0
    external_force_y: float = 0.0
    external_x_app: float = 0.0
    external_y_app: float = 0.0
    seismic_force_x: float = 0.0
    seismic_force_y: float = 0.0
    pore_force: float = 0.0
    pore_x_app: float = 0.0
    pore_y_app: float = 0.0
    base_material_id: str = ""
    base_cohesion: float = 0.0
    base_phi_deg: float = 0.0
    material_weight_contributions: tuple[tuple[str, float], ...] = ()

    @property
    def total_vertical_force(self) -> float:
        return self.weight + self.external_force_y


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
    external_force_x: float = 0.0
    external_force_y: float = 0.0
    external_x_app: float = 0.0
    external_y_app: float = 0.0
    seismic_force_x: float = 0.0
    seismic_force_y: float = 0.0
    pore_force: float = 0.0
    pore_x_app: float = 0.0
    pore_y_app: float = 0.0
    base_material_id: str = ""
    base_cohesion: float = 0.0
    base_phi_deg: float = 0.0
    material_weight_contributions: tuple[tuple[str, float], ...] = ()

    @property
    def total_vertical_force(self) -> float:
        return self.weight + self.external_force_y


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
