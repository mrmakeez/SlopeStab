from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from slope_stab.exceptions import ConvergenceError
from slope_stab.exceptions import GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisResult, PrescribedCircleInput, ProjectInput
from slope_stab.search.auto_refine import run_auto_refine_search
from slope_stab.search.cmaes_global import run_cmaes_global_search
from slope_stab.search.cuckoo_global import run_cuckoo_global_search
from slope_stab.search.direct_global import run_direct_global_search
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface


POINT_TOL = 1e-6
SearchRunner = Callable[[ProjectInput, UniformSlopeProfile, Callable[[PrescribedCircleInput], AnalysisResult]], tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]]


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


def _run_auto_refine_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.auto_refine_circular is None:
        raise GeometryError("Missing search.auto_refine_circular configuration.")

    config = search.auto_refine_circular
    auto_result = run_auto_refine_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
    )

    search_payload = {
        "method": "auto_refine_circular",
        "auto_refine_circular": {
            "divisions_along_slope": config.divisions_along_slope,
            "circles_per_division": config.circles_per_division,
            "iterations": config.iterations,
            "divisions_to_use_next_iteration_pct": config.divisions_to_use_next_iteration_pct,
            "search_limits": {
                "x_min": config.search_limits.x_min,
                "x_max": config.search_limits.x_max,
            },
        },
        "generated_surfaces": auto_result.generated_surfaces,
        "valid_surfaces": auto_result.valid_surfaces,
        "invalid_surfaces": auto_result.invalid_surfaces,
        "iteration_diagnostics": [asdict(item) for item in auto_result.iteration_diagnostics],
    }

    return auto_result.winning_result, auto_result.winning_surface, search_payload


def _run_direct_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.direct_global_circular is None:
        raise GeometryError("Missing search.direct_global_circular configuration.")

    config = search.direct_global_circular
    direct_result = run_direct_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
    )

    search_payload = {
        "method": "direct_global_circular",
        "direct_global_circular": {
            "max_iterations": config.max_iterations,
            "max_evaluations": config.max_evaluations,
            "min_improvement": config.min_improvement,
            "stall_iterations": config.stall_iterations,
            "min_rectangle_half_size": config.min_rectangle_half_size,
            "search_limits": {
                "x_min": config.search_limits.x_min,
                "x_max": config.search_limits.x_max,
            },
        },
        "total_evaluations": direct_result.total_evaluations,
        "valid_evaluations": direct_result.valid_evaluations,
        "infeasible_evaluations": direct_result.infeasible_evaluations,
        "termination_reason": direct_result.termination_reason,
        "iteration_diagnostics": [asdict(item) for item in direct_result.iteration_diagnostics],
    }

    return direct_result.winning_result, direct_result.winning_surface, search_payload


def _run_cuckoo_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.cuckoo_global_circular is None:
        raise GeometryError("Missing search.cuckoo_global_circular configuration.")

    config = search.cuckoo_global_circular
    cuckoo_result = run_cuckoo_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
    )

    search_payload = {
        "method": "cuckoo_global_circular",
        "cuckoo_global_circular": {
            "population_size": config.population_size,
            "max_iterations": config.max_iterations,
            "max_evaluations": config.max_evaluations,
            "discovery_rate": config.discovery_rate,
            "levy_beta": config.levy_beta,
            "alpha_max": config.alpha_max,
            "alpha_min": config.alpha_min,
            "min_improvement": config.min_improvement,
            "stall_iterations": config.stall_iterations,
            "seed": config.seed,
            "post_polish": config.post_polish,
            "search_limits": {
                "x_min": config.search_limits.x_min,
                "x_max": config.search_limits.x_max,
            },
        },
        "total_evaluations": cuckoo_result.total_evaluations,
        "valid_evaluations": cuckoo_result.valid_evaluations,
        "infeasible_evaluations": cuckoo_result.infeasible_evaluations,
        "termination_reason": cuckoo_result.termination_reason,
        "iteration_diagnostics": [asdict(item) for item in cuckoo_result.iteration_diagnostics],
    }

    return cuckoo_result.winning_result, cuckoo_result.winning_surface, search_payload


def _run_cmaes_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.cmaes_global_circular is None:
        raise GeometryError("Missing search.cmaes_global_circular configuration.")

    config = search.cmaes_global_circular
    cmaes_result = run_cmaes_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
    )

    search_payload = {
        "method": "cmaes_global_circular",
        "cmaes_global_circular": {
            "max_evaluations": config.max_evaluations,
            "direct_prescan_evaluations": config.direct_prescan_evaluations,
            "cmaes_population_size": config.cmaes_population_size,
            "cmaes_max_iterations": config.cmaes_max_iterations,
            "cmaes_restarts": config.cmaes_restarts,
            "cmaes_sigma0": config.cmaes_sigma0,
            "polish_max_evaluations": config.polish_max_evaluations,
            "min_improvement": config.min_improvement,
            "stall_iterations": config.stall_iterations,
            "seed": config.seed,
            "post_polish": config.post_polish,
            "invalid_penalty": config.invalid_penalty,
            "nonconverged_penalty": config.nonconverged_penalty,
            "search_limits": {
                "x_min": config.search_limits.x_min,
                "x_max": config.search_limits.x_max,
            },
        },
        "total_evaluations": cmaes_result.total_evaluations,
        "valid_evaluations": cmaes_result.valid_evaluations,
        "infeasible_evaluations": cmaes_result.infeasible_evaluations,
        "termination_reason": cmaes_result.termination_reason,
        "iteration_diagnostics": [asdict(item) for item in cmaes_result.iteration_diagnostics],
    }

    return cmaes_result.winning_result, cmaes_result.winning_surface, search_payload


_SEARCH_RUNNERS: dict[str, SearchRunner] = {
    "auto_refine_circular": _run_auto_refine_mode,
    "direct_global_circular": _run_direct_global_mode,
    "cuckoo_global_circular": _run_cuckoo_global_mode,
    "cmaes_global_circular": _run_cmaes_global_mode,
}


def run_analysis(project: ProjectInput) -> AnalysisResult:
    profile = _build_profile(project)

    if project.prescribed_surface is not None and project.search is None:
        result = _solve_prescribed_surface(project, profile, project.prescribed_surface)
        _attach_prescribed_metadata(project, result, project.prescribed_surface)
        return result

    if project.search is not None and project.prescribed_surface is None:
        runner = _SEARCH_RUNNERS.get(project.search.method)
        if runner is None:
            raise GeometryError(f"Unsupported search method: {project.search.method}")

        evaluate_surface = lambda s: _solve_prescribed_surface(project, profile, s)
        result, winning_surface, search_payload = runner(project, profile, evaluate_surface)
        result.metadata = {
            "units": project.units,
            "method": project.analysis.method,
            "n_slices": project.analysis.n_slices,
            "mode": project.search.method,
            "prescribed_surface": _surface_to_dict(winning_surface),
            "search": search_payload,
        }
        return result

    raise ConvergenceError("Project input must define exactly one analysis mode.")
