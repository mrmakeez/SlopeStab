from __future__ import annotations

from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisResult, PrescribedCircleInput, ProjectInput
from slope_stab.search.auto_refine import run_auto_refine_search
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


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


def _solve_for_prescribed_surface(
    profile: UniformSlopeProfile,
    material: MohrCoulombMaterial,
    project: ProjectInput,
    surface_data: PrescribedCircleInput,
    *,
    validate_alignment: bool,
) -> AnalysisResult:
    surface = CircularSlipSurface(
        xc=surface_data.xc,
        yc=surface_data.yc,
        r=surface_data.r,
    )

    if validate_alignment:
        _validate_prescribed_surface_alignment(
            profile,
            surface,
            surface_data.x_left,
            surface_data.y_left,
            "Left",
        )
        _validate_prescribed_surface_alignment(
            profile,
            surface,
            surface_data.x_right,
            surface_data.y_right,
            "Right",
        )

    slices = generate_vertical_slices(
        profile=profile,
        surface=surface,
        n_slices=project.analysis.n_slices,
        x_left=surface_data.x_left,
        x_right=surface_data.x_right,
        gamma=material.gamma,
    )

    solver = BishopSimplifiedSolver(material=material, analysis=project.analysis, surface=surface)
    return solver.solve(slices)


def run_analysis(project: ProjectInput, *, top_n: int = 20) -> AnalysisResult:
    profile = UniformSlopeProfile(
        h=project.geometry.h,
        l=project.geometry.l,
        x_toe=project.geometry.x_toe,
        y_toe=project.geometry.y_toe,
    )
    material = MohrCoulombMaterial(
        gamma=project.material.gamma,
        cohesion=project.material.c,
        phi_deg=project.material.phi_deg,
    )

    if project.analysis.mode == "prescribed":
        if project.prescribed_surface is None:
            raise GeometryError("Prescribed mode requires a prescribed_surface definition.")

        result = _solve_for_prescribed_surface(
            profile=profile,
            material=material,
            project=project,
            surface_data=project.prescribed_surface,
            validate_alignment=True,
        )
        result.metadata = {
            "units": project.units,
            "method": project.analysis.method,
            "mode": project.analysis.mode,
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

    if project.analysis.mode == "auto_refine":
        if project.auto_refine is None:
            raise GeometryError("Auto-refine mode requires auto_refine settings.")

        result, search_payload = run_auto_refine_search(
            profile=profile,
            material=material,
            analysis=project.analysis,
            settings=project.auto_refine,
            top_n=top_n,
        )
        result.metadata = {
            "units": project.units,
            "method": project.analysis.method,
            "mode": project.analysis.mode,
            "n_slices": project.analysis.n_slices,
        }
        result.search = search_payload
        return result

    raise GeometryError(f"Unsupported analysis mode: {project.analysis.mode}")
