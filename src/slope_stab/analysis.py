from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict
from typing import Any, Callable

from slope_stab.exceptions import ConvergenceError, GeometryError, ParallelExecutionError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisResult,
    LoadsInput,
    ParallelExecutionInput,
    PrescribedCircleInput,
    ProjectInput,
    SearchInput,
)
from slope_stab.search.auto_parallel_policy import (
    EVIDENCE_VERSION,
    REASON_FORCED_PARALLEL_MODE,
    REASON_FORCED_SERIAL_MODE,
    REASON_POLICY_THRESHOLD_PARALLEL,
    REASON_POLICY_THRESHOLD_SERIAL,
    REASON_PROCESS_BACKEND_STARTUP_FAILED_SERIAL,
    REASON_PRESCRIBED_ANALYSIS_SERIAL,
    REASON_UNSUPPORTED_BATCHING_SERIAL,
    REASON_UNSUPPORTED_WORKLOAD_SERIAL,
    REASON_WORKERS_LE_ONE_SERIAL,
    ParallelResolution,
    classify_batching,
    classify_workload,
    allowed_parallel_modes,
    effective_cpu_count,
    process_policy_allows_parallel,
    resolve_requested_workers,
)
from slope_stab.search.auto_refine import run_auto_refine_search
from slope_stab.search.cmaes_global import run_cmaes_global_search
from slope_stab.search.common import SurfaceBatchEvaluator
from slope_stab.search.cuckoo_global import run_cuckoo_global_search
from slope_stab.search.direct_global import run_direct_global_search
from slope_stab.search.parallel_executor import ParallelSurfaceExecutor
from slope_stab.search.surface_solver import (
    AnalysisWorkerContext,
    build_profile,
    build_worker_context,
    solve_surface_for_context,
)


SearchRunner = Callable[
    [
        ProjectInput,
        UniformSlopeProfile,
        Callable[[PrescribedCircleInput], AnalysisResult],
        SurfaceBatchEvaluator | None,
        int,
    ],
    tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]],
]


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


def _loads_to_dict(loads: LoadsInput | None) -> dict[str, Any]:
    if loads is None:
        return {"uniform_surcharge": None, "seismic": None, "groundwater": None}
    payload: dict[str, Any] = {"uniform_surcharge": None, "seismic": None, "groundwater": None}
    if loads.uniform_surcharge is not None:
        payload["uniform_surcharge"] = {
            "magnitude_kpa": loads.uniform_surcharge.magnitude_kpa,
            "placement": loads.uniform_surcharge.placement,
            "x_start": loads.uniform_surcharge.x_start,
            "x_end": loads.uniform_surcharge.x_end,
        }
    if loads.seismic is not None:
        seismic_payload: dict[str, Any] = {"model": loads.seismic.model}
        if loads.seismic.model == "pseudo_static":
            seismic_payload["kh"] = loads.seismic.kh
            seismic_payload["kv"] = loads.seismic.kv
        payload["seismic"] = seismic_payload
    if loads.groundwater is not None:
        groundwater_payload: dict[str, Any] = {"model": loads.groundwater.model}
        if loads.groundwater.model == "water_surfaces":
            groundwater_payload["surface"] = [list(point) for point in loads.groundwater.surface]
            groundwater_payload["gamma_w"] = loads.groundwater.gamma_w
            if loads.groundwater.hu is not None:
                groundwater_payload["hu"] = {
                    "mode": loads.groundwater.hu.mode,
                    "value": loads.groundwater.hu.value,
                }
        if loads.groundwater.model == "ru_coefficient":
            groundwater_payload["ru"] = loads.groundwater.ru
        payload["groundwater"] = groundwater_payload
    return payload


def _attach_prescribed_metadata(project: ProjectInput, result: AnalysisResult, surface: PrescribedCircleInput) -> None:
    metadata = dict(result.metadata)
    metadata.update(
        {
            "units": project.units,
            "method": project.analysis.method,
            "n_slices": project.analysis.n_slices,
            "prescribed_surface": _surface_to_dict(surface),
            "loads": _loads_to_dict(project.loads),
            "parallel": {
                "requested_mode": "serial",
                "resolved_mode": "serial",
                "decision_reason": REASON_PRESCRIBED_ANALYSIS_SERIAL,
                "evidence_version": EVIDENCE_VERSION,
                "backend": "serial",
                "requested_workers": 1,
                "resolved_workers": 1,
                "workload_class": "n/a",
                "batching_class": "n/a",
                "min_batch_size": 1,
                "timeout_seconds": None,
            },
        }
    )
    result.metadata = metadata


def _resolve_parallel_request(
    project: ProjectInput,
    forced_parallel_mode: str | None,
    forced_parallel_workers: int | None,
) -> ParallelExecutionInput:
    defaults = ParallelExecutionInput(
        mode="auto",
        workers=0,
        min_batch_size=1,
        timeout_seconds=None,
    )
    if project.search is None:
        return defaults

    configured = project.search.parallel or defaults
    mode = configured.mode if forced_parallel_mode is None else forced_parallel_mode
    if mode not in allowed_parallel_modes():
        raise GeometryError(f"Unsupported parallel mode override: {mode}")
    workers = configured.workers if forced_parallel_workers is None else forced_parallel_workers
    if workers < 0:
        raise GeometryError("Parallel worker override must be greater than or equal to zero.")
    return ParallelExecutionInput(
        mode=mode,
        workers=workers,
        min_batch_size=configured.min_batch_size,
        timeout_seconds=configured.timeout_seconds,
    )


def _initial_parallel_resolution(
    search: SearchInput,
    analysis_method: str,
    requested: ParallelExecutionInput,
    available_workers: int,
) -> ParallelResolution:
    requested_mode = requested.mode
    requested_workers = resolve_requested_workers(requested.workers, available_workers)
    batching_class = classify_batching(requested.min_batch_size)
    workload_class = classify_workload(search, analysis_method)

    if requested_mode == "serial":
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="serial",
            resolved_workers=1,
            decision_reason=REASON_FORCED_SERIAL_MODE,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="serial",
        )

    if requested_workers <= 1:
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="serial",
            resolved_workers=1,
            decision_reason=REASON_WORKERS_LE_ONE_SERIAL,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="serial",
        )

    if requested_mode == "parallel":
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="parallel",
            resolved_workers=requested_workers,
            decision_reason=REASON_FORCED_PARALLEL_MODE,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="process",
        )

    # requested_mode == "auto"
    if workload_class == "unsupported":
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="serial",
            resolved_workers=1,
            decision_reason=REASON_UNSUPPORTED_WORKLOAD_SERIAL,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="serial",
        )

    if batching_class != "default_batching":
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="serial",
            resolved_workers=1,
            decision_reason=REASON_UNSUPPORTED_BATCHING_SERIAL,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="serial",
        )

    if not process_policy_allows_parallel(
        search_method=search.method,
        analysis_method=analysis_method,
        workload_class=workload_class,
        batching_class=batching_class,
    ):
        return ParallelResolution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            resolved_mode="serial",
            resolved_workers=1,
            decision_reason=REASON_POLICY_THRESHOLD_SERIAL,
            workload_class=workload_class,
            batching_class=batching_class,
            evidence_version=EVIDENCE_VERSION,
            backend="serial",
        )

    return ParallelResolution(
        requested_mode=requested_mode,
        requested_workers=requested_workers,
        resolved_mode="parallel",
        resolved_workers=requested_workers,
        decision_reason=REASON_POLICY_THRESHOLD_PARALLEL,
        workload_class=workload_class,
        batching_class=batching_class,
        evidence_version=EVIDENCE_VERSION,
        backend="process",
    )


def _resolution_for_process_startup_failure(
    initial: ParallelResolution,
) -> ParallelResolution:
    if initial.resolved_mode != "parallel":
        return initial

    return ParallelResolution(
        requested_mode=initial.requested_mode,
        requested_workers=initial.requested_workers,
        resolved_mode="serial",
        resolved_workers=1,
        decision_reason=REASON_PROCESS_BACKEND_STARTUP_FAILED_SERIAL,
        workload_class=initial.workload_class,
        batching_class=initial.batching_class,
        evidence_version=initial.evidence_version,
        backend="serial",
    )


def _run_auto_refine_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.auto_refine_circular is None:
        raise GeometryError("Missing search.auto_refine_circular configuration.")

    config = search.auto_refine_circular
    auto_result = run_auto_refine_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
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
            "model_boundary_floor_y": config.model_boundary_floor_y,
        },
        "generated_surfaces": auto_result.generated_surfaces,
        "valid_surfaces": auto_result.valid_surfaces,
        "invalid_surfaces": auto_result.invalid_surfaces,
        "post_refinement_generated_surfaces": auto_result.post_refinement_generated_surfaces,
        "post_refinement_valid_surfaces": auto_result.post_refinement_valid_surfaces,
        "post_refinement_invalid_surfaces": auto_result.post_refinement_invalid_surfaces,
        "before_post_polish": {
            "fos": auto_result.before_post_polish_result.fos,
            "surface": _surface_to_dict(auto_result.before_post_polish_surface),
        },
        "after_post_polish": {
            "fos": auto_result.after_post_polish_result.fos,
            "surface": _surface_to_dict(auto_result.after_post_polish_surface),
        },
        "iteration_diagnostics": [asdict(item) for item in auto_result.iteration_diagnostics],
    }

    return auto_result.winning_result, auto_result.winning_surface, search_payload


def _run_direct_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.direct_global_circular is None:
        raise GeometryError("Missing search.direct_global_circular configuration.")

    config = search.direct_global_circular
    direct_result = run_direct_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
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
        "post_refinement_total_evaluations": direct_result.post_refinement_total_evaluations,
        "post_refinement_valid_evaluations": direct_result.post_refinement_valid_evaluations,
        "post_refinement_infeasible_evaluations": direct_result.post_refinement_infeasible_evaluations,
        "termination_reason": direct_result.termination_reason,
        "iteration_diagnostics": [asdict(item) for item in direct_result.iteration_diagnostics],
    }

    return direct_result.winning_result, direct_result.winning_surface, search_payload


def _run_cuckoo_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.cuckoo_global_circular is None:
        raise GeometryError("Missing search.cuckoo_global_circular configuration.")

    config = search.cuckoo_global_circular
    cuckoo_result = run_cuckoo_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
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
        "post_refinement_total_evaluations": cuckoo_result.post_refinement_total_evaluations,
        "post_refinement_valid_evaluations": cuckoo_result.post_refinement_valid_evaluations,
        "post_refinement_infeasible_evaluations": cuckoo_result.post_refinement_infeasible_evaluations,
        "termination_reason": cuckoo_result.termination_reason,
        "iteration_diagnostics": [asdict(item) for item in cuckoo_result.iteration_diagnostics],
    }

    return cuckoo_result.winning_result, cuckoo_result.winning_surface, search_payload


def _run_cmaes_global_mode(
    project: ProjectInput,
    profile: UniformSlopeProfile,
    evaluate_surface: Callable[[PrescribedCircleInput], AnalysisResult],
    batch_evaluate_surfaces: SurfaceBatchEvaluator | None,
    min_batch_size: int,
) -> tuple[AnalysisResult, PrescribedCircleInput, dict[str, Any]]:
    search = project.search
    if search is None or search.cmaes_global_circular is None:
        raise GeometryError("Missing search.cmaes_global_circular configuration.")

    config = search.cmaes_global_circular
    cmaes_result = run_cmaes_global_search(
        profile=profile,
        config=config,
        evaluate_surface=evaluate_surface,
        batch_evaluate_surfaces=batch_evaluate_surfaces,
        min_batch_size=min_batch_size,
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
        "post_refinement_total_evaluations": cmaes_result.post_refinement_total_evaluations,
        "post_refinement_valid_evaluations": cmaes_result.post_refinement_valid_evaluations,
        "post_refinement_infeasible_evaluations": cmaes_result.post_refinement_infeasible_evaluations,
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


def _evaluate_surface_for_context(
    context: AnalysisWorkerContext,
    surface: PrescribedCircleInput,
) -> AnalysisResult:
    return solve_surface_for_context(context, surface)


def _parallel_metadata(
    decision: ParallelResolution,
    min_batch_size: int,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    return {
        "requested_mode": decision.requested_mode,
        "resolved_mode": decision.resolved_mode,
        "decision_reason": decision.decision_reason,
        "evidence_version": decision.evidence_version,
        "backend": decision.backend,
        "requested_workers": decision.requested_workers,
        "resolved_workers": decision.resolved_workers,
        "workload_class": decision.workload_class,
        "batching_class": decision.batching_class,
        "min_batch_size": min_batch_size,
        "timeout_seconds": timeout_seconds,
    }


def run_analysis(
    project: ProjectInput,
    forced_parallel_workers: int | None = None,
    forced_parallel_mode: str | None = None,
) -> AnalysisResult:
    context = build_worker_context(project)
    profile = build_profile(project.geometry)

    if project.prescribed_surface is not None and project.search is None:
        result = solve_surface_for_context(context, project.prescribed_surface)
        _attach_prescribed_metadata(project, result, project.prescribed_surface)
        return result

    if project.search is not None and project.prescribed_surface is None:
        runner = _SEARCH_RUNNERS.get(project.search.method)
        if runner is None:
            raise GeometryError(f"Unsupported search method: {project.search.method}")

        evaluate_surface = lambda s: _evaluate_surface_for_context(context, s)
        requested_parallel = _resolve_parallel_request(
            project=project,
            forced_parallel_mode=forced_parallel_mode,
            forced_parallel_workers=forced_parallel_workers,
        )
        available_workers = effective_cpu_count()
        initial_resolution = _initial_parallel_resolution(
            search=project.search,
            analysis_method=project.analysis.method,
            requested=requested_parallel,
            available_workers=available_workers,
        )

        batch_evaluate_surfaces: SurfaceBatchEvaluator | None = None
        decision = initial_resolution

        if initial_resolution.run_parallel:
            try:
                executor_cm = ParallelSurfaceExecutor(
                    context=context,
                    workers=initial_resolution.resolved_workers,
                    timeout_seconds=requested_parallel.timeout_seconds,
                )
            except (OSError, PermissionError) as exc:
                if initial_resolution.requested_mode == "parallel":
                    raise ParallelExecutionError(
                        f"Process backend startup failed for forced parallel mode: {exc}"
                    ) from exc
                decision = _resolution_for_process_startup_failure(initial_resolution)
                result, winning_surface, search_payload = runner(
                    project,
                    profile,
                    evaluate_surface,
                    None,
                    1,
                )
            else:
                with ExitStack() as executor_stack:
                    try:
                        executor = executor_stack.enter_context(executor_cm)
                    except (OSError, PermissionError) as exc:
                        if initial_resolution.requested_mode == "parallel":
                            raise ParallelExecutionError(
                                f"Process backend startup failed for forced parallel mode: {exc}"
                            ) from exc
                        decision = _resolution_for_process_startup_failure(initial_resolution)
                        result, winning_surface, search_payload = runner(
                            project,
                            profile,
                            evaluate_surface,
                            None,
                            1,
                        )
                    else:
                        batch_evaluate_surfaces = executor.evaluate_surfaces
                        result, winning_surface, search_payload = runner(
                            project,
                            profile,
                            evaluate_surface,
                            batch_evaluate_surfaces,
                            requested_parallel.min_batch_size,
                        )
        else:
            result, winning_surface, search_payload = runner(
                project,
                profile,
                evaluate_surface,
                None,
                1,
            )

        search_payload["parallel"] = _parallel_metadata(
            decision=decision,
            min_batch_size=requested_parallel.min_batch_size,
            timeout_seconds=requested_parallel.timeout_seconds,
        )
        result.metadata = {
            "units": project.units,
            "method": project.analysis.method,
            "n_slices": project.analysis.n_slices,
            "mode": project.search.method,
            "prescribed_surface": _surface_to_dict(winning_surface),
            "loads": _loads_to_dict(project.loads),
            "search": search_payload,
        }
        return result

    raise ConvergenceError("Project input must define exactly one analysis mode.")
