from __future__ import annotations

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisResult, ProjectInput
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


POINT_TOL = 1e-6


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


def run_analysis(project: ProjectInput) -> AnalysisResult:
    profile = UniformSlopeProfile(
        h=project.geometry.h,
        l=project.geometry.l,
        x_toe=project.geometry.x_toe,
        y_toe=project.geometry.y_toe,
    )
    surface = CircularSlipSurface(
        xc=project.prescribed_surface.xc,
        yc=project.prescribed_surface.yc,
        r=project.prescribed_surface.r,
    )

    _validate_prescribed_surface_alignment(
        profile,
        surface,
        project.prescribed_surface.x_left,
        project.prescribed_surface.y_left,
        "Left",
    )
    _validate_prescribed_surface_alignment(
        profile,
        surface,
        project.prescribed_surface.x_right,
        project.prescribed_surface.y_right,
        "Right",
    )

    slices = generate_vertical_slices(
        profile=profile,
        surface=surface,
        n_slices=project.analysis.n_slices,
        x_left=project.prescribed_surface.x_left,
        x_right=project.prescribed_surface.x_right,
        gamma=project.material.gamma,
    )

    solver = BishopSimplifiedSolver(
        material=MohrCoulombMaterial(
            gamma=project.material.gamma,
            cohesion=project.material.c,
            phi_deg=project.material.phi_deg,
        ),
        analysis=project.analysis,
        surface=surface,
    )

    result = solver.solve(slices)
    result.metadata = {
        "units": project.units,
        "method": project.analysis.method,
        "n_slices": project.analysis.n_slices,
        "prescribed_surface": {
            "xc": project.prescribed_surface.xc,
            "yc": project.prescribed_surface.yc,
            "r": project.prescribed_surface.r,
            "x_left": project.prescribed_surface.x_left,
            "y_left": project.prescribed_surface.y_left,
            "x_right": project.prescribed_surface.x_right,
            "y_right": project.prescribed_surface.y_right,
        },
    }
    return result
