from __future__ import annotations

from slope_stab.models import GeometryInput, SoilMaterialInput, SoilRegionAssignmentInput, SoilsInput


def build_uniform_soils(
    *,
    gamma: float,
    cohesion: float,
    phi_deg: float,
    material_id: str = "soil_1",
    extent: float = 1_000_000.0,
) -> SoilsInput:
    external_boundary = (
        (-extent, -extent),
        (extent, -extent),
        (extent, extent),
        (-extent, extent),
    )
    return SoilsInput(
        materials=(
            SoilMaterialInput(
                id=material_id,
                gamma=gamma,
                c=cohesion,
                phi_deg=phi_deg,
            ),
        ),
        external_boundary=external_boundary,
        material_boundaries=(),
        region_assignments=(
            SoilRegionAssignmentInput(material_id=material_id, seed_x=0.0, seed_y=0.0),
        ),
    )


def default_uniform_external_boundary(geometry: GeometryInput) -> tuple[tuple[float, float], ...]:
    span = max(abs(geometry.h), abs(geometry.l), 1.0)
    x_min = geometry.x_toe - 6.0 * span
    x_max = geometry.x_toe + geometry.l + 6.0 * span
    y_low = min(geometry.y_toe, geometry.y_toe + geometry.h)
    y_high = max(geometry.y_toe, geometry.y_toe + geometry.h)
    y_min = y_low - 4.0 * span
    y_max = y_high + 4.0 * span
    return (
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    )


def build_uniform_soils_for_geometry(
    *,
    geometry: GeometryInput,
    gamma: float,
    cohesion: float,
    phi_deg: float,
    material_id: str = "soil_1",
) -> SoilsInput:
    external_boundary = default_uniform_external_boundary(geometry)
    x_seed = 0.5 * (external_boundary[0][0] + external_boundary[1][0])
    y_seed = 0.5 * (external_boundary[0][1] + external_boundary[2][1])
    return SoilsInput(
        materials=(
            SoilMaterialInput(
                id=material_id,
                gamma=gamma,
                c=cohesion,
                phi_deg=phi_deg,
            ),
        ),
        external_boundary=external_boundary,
        material_boundaries=(),
        region_assignments=(
            SoilRegionAssignmentInput(
                material_id=material_id,
                seed_x=x_seed,
                seed_y=y_seed,
            ),
        ),
    )
