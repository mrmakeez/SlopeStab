from __future__ import annotations

from dataclasses import asdict

from slope_stab.exceptions import ConvergenceError
from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisResult, PrescribedCircleInput, ProjectInput
from slope_stab.search.auto_refine import run_auto_refine_search
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


def _build_profile(project: ProjectInput) -> UniformSlopeProfile:
    return UniformSlopeProfile(
        h=project.geometry.h,
        l=project.geometry.l,
        x_toe=project.geometry.x_toe,
        y_toe=project.geometry.y_toe,
    )


def _solve_prescribed_surface(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    surface_input: PrescribedCircleInput,
) -> AnalysisResult:
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
        n_slices=project.analysis.n_slices,
        x_left=surface_input.x_left,
        x_right=surface_input.x_right,
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

    return solver.solve(slices)


def _surface_to_dict(surface: PrescribedCircleInput) -> dict[str, float]:
    return {
        "xc": surface.xc,
        "yc": surface.yc,
        "r": surface.r,
        "x_left": surface.x_left,
        "y_left": surface.y_left,
        "x_right": surface.x_right,
        "y_right": surface.y_right,
    }


def _attach_prescribed_metadata(project: ProjectInput, result: AnalysisResult, surface: PrescribedCircleInput) -> None:
    result.metadata = {
        "units": project.units,
        "method": project.analysis.method,
        "n_slices": project.analysis.n_slices,
        "prescribed_surface": _surface_to_dict(surface),
    }


def run_analysis(project: ProjectInput) -> AnalysisResult:
    profile = _build_profile(project)

    if project.prescribed_surface is not None and project.search is None:
        result = _solve_prescribed_surface(project, profile, project.prescribed_surface)
        _attach_prescribed_metadata(project, result, project.prescribed_surface)
        return result

    if project.search is not None and project.prescribed_surface is None:
        if project.search.method != "auto_refine_circular":
            raise GeometryError(f"Unsupported search method: {project.search.method}")

        search_result = run_auto_refine_search(
            profile=profile,
            config=project.search.auto_refine_circular,
            evaluate_surface=lambda s: _solve_prescribed_surface(project, profile, s),
        )
        result = search_result.winning_result
        winning_surface = search_result.winning_surface

        result.metadata = {
            "units": project.units,
            "method": project.analysis.method,
            "n_slices": project.analysis.n_slices,
            "mode": "auto_refine_circular",
            "prescribed_surface": _surface_to_dict(winning_surface),
            "search": {
                "method": project.search.method,
                "auto_refine_circular": {
                    "divisions_along_slope": project.search.auto_refine_circular.divisions_along_slope,
                    "circles_per_division": project.search.auto_refine_circular.circles_per_division,
                    "iterations": project.search.auto_refine_circular.iterations,
                    "divisions_to_use_next_iteration_pct": (
                        project.search.auto_refine_circular.divisions_to_use_next_iteration_pct
                    ),
                    "search_limits": {
                        "x_min": project.search.auto_refine_circular.search_limits.x_min,
                        "x_max": project.search.auto_refine_circular.search_limits.x_max,
                    },
                },
                "generated_surfaces": search_result.generated_surfaces,
                "valid_surfaces": search_result.valid_surfaces,
                "invalid_surfaces": search_result.invalid_surfaces,
                "iteration_diagnostics": [asdict(item) for item in search_result.iteration_diagnostics],
            },
        }
        return result

    raise ConvergenceError("Project input must define exactly one analysis mode.")
