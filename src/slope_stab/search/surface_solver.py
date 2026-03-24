from __future__ import annotations

from dataclasses import dataclass

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.base import LEMSolver
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.lem_core.spencer import SpencerSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import (
    AnalysisInput,
    AnalysisResult,
    GeometryInput,
    LoadsInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
)
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


@dataclass(frozen=True)
class AnalysisWorkerContext:
    geometry: GeometryInput
    material: MaterialInput
    analysis: AnalysisInput
    loads: LoadsInput | None


def build_worker_context(project: ProjectInput) -> AnalysisWorkerContext:
    return AnalysisWorkerContext(
        geometry=project.geometry,
        material=project.material,
        analysis=project.analysis,
        loads=project.loads,
    )


def build_profile(geometry: GeometryInput) -> UniformSlopeProfile:
    return UniformSlopeProfile(
        h=geometry.h,
        l=geometry.l,
        x_toe=geometry.x_toe,
        y_toe=geometry.y_toe,
    )


def _validate_prescribed_surface_alignment(
    profile: UniformSlopeProfile,
    surface: CircularSlipSurface,
    x: float,
    y: float,
    label: str,
) -> None:
    y_ground = profile.y_ground(x)
    y_base = surface.y_base(x)

    if abs(y - y_ground) > 2e-3:
        raise GeometryError(
            f"{label} endpoint does not align with slope ground profile: |y - y_ground|={abs(y-y_ground)}"
        )
    if abs(y - y_base) > 2e-3:
        raise GeometryError(
            f"{label} endpoint does not align with prescribed circle: |y - y_circle|={abs(y-y_base)}"
        )


def _build_solver(context: AnalysisWorkerContext, surface: CircularSlipSurface) -> LEMSolver:
    material = MohrCoulombMaterial(
        gamma=context.material.gamma,
        cohesion=context.material.c,
        phi_deg=context.material.phi_deg,
    )

    if context.analysis.method == "bishop_simplified":
        return BishopSimplifiedSolver(
            material=material,
            analysis=context.analysis,
            surface=surface,
        )
    if context.analysis.method == "spencer":
        return SpencerSolver(
            material=material,
            analysis=context.analysis,
            surface=surface,
        )

    raise GeometryError(f"Unsupported analysis method: {context.analysis.method}")


def solve_surface_for_context(
    context: AnalysisWorkerContext,
    surface_input: PrescribedCircleInput,
) -> AnalysisResult:
    profile = build_profile(context.geometry)
    surface = CircularSlipSurface(xc=surface_input.xc, yc=surface_input.yc, r=surface_input.r)

    _validate_prescribed_surface_alignment(
        profile,
        surface,
        surface_input.x_left,
        surface_input.y_left,
        "Left",
    )
    _validate_prescribed_surface_alignment(
        profile,
        surface,
        surface_input.x_right,
        surface_input.y_right,
        "Right",
    )

    slices = generate_vertical_slices(
        profile=profile,
        surface=surface,
        n_slices=context.analysis.n_slices,
        x_left=surface_input.x_left,
        x_right=surface_input.x_right,
        gamma=context.material.gamma,
        loads=context.loads,
    )

    solver = _build_solver(context, surface)
    return solver.solve(slices)
