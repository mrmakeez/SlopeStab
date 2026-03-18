from __future__ import annotations

from dataclasses import dataclass
import math

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import AnalysisResult, CmaesGlobalSearchInput, PrescribedCircleInput
from slope_stab.search.auto_refine import _run_toe_crest_refinement
from slope_stab.search.common import (
    BETA_MAX_RAD,
    SurfaceEvaluator,
    X_SEP_MIN,
    circle_from_endpoints_and_tangent,
    evaluate_surface_candidate,
    is_better_score,
    repair_vector_reflect,
    surface_key,
)
from slope_stab.search.direct_partition import (
    DirectRectangle,
    seeded_centers_3x3x3,
    select_potentially_optimal,
    split_rectangle,
)
from slope_stab.search.objective_evaluator import (
    CachedObjectiveEvaluator,
    ObjectiveEvaluation,
    ObjectiveScoringPolicy,
)
from slope_stab.search.post_polish import default_post_polish_refine_config


_TANGENT_EPS_RAD = math.radians(0.5)
_COARSE_TOE_LOCKED_SAMPLES = 61
_LOCAL_TOE_LOCKED_SAMPLES = 21
_LOCAL_HALF_WINDOW_STEPS = 10


@dataclass(frozen=True)
class CmaesStageDiagnostics:
    stage: str
    iteration: int
    total_evaluations: int
    incumbent_fos: float
    extra: dict[str, float | int | bool | str]


@dataclass(frozen=True)
class CmaesGlobalSearchResult:
    winning_surface: PrescribedCircleInput
    winning_result: AnalysisResult
    iteration_diagnostics: list[CmaesStageDiagnostics]
    total_evaluations: int
    valid_evaluations: int
    infeasible_evaluations: int
    termination_reason: str


def _linspace(start: float, end: float, count: int) -> list[float]:
    if count <= 1:
        return [start]
    step = (end - start) / (count - 1)
    return [start + i * step for i in range(count)]


def _run_direct_prescan(
    evaluator: CachedObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
) -> tuple[list[tuple[float, float, float]], str]:
    rectangles: list[DirectRectangle[ObjectiveEvaluation]] = []
    next_rect_id = 0

    def make_rectangle(center: tuple[float, float, float], half_sizes: tuple[float, float, float]) -> DirectRectangle[ObjectiveEvaluation]:
        nonlocal next_rect_id
        eval_result = evaluator.evaluate_vector(center)
        rect = DirectRectangle(
            rect_id=next_rect_id,
            center=center,
            half_sizes=half_sizes,
            score=eval_result.score,
            payload=eval_result,
        )
        next_rect_id += 1
        return rect

    centers_1d = seeded_centers_3x3x3()
    base_half_sizes = (1.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0)
    for u0 in centers_1d:
        for u1 in centers_1d:
            for u2 in centers_1d:
                rectangles.append(make_rectangle((u0, u1, u2), base_half_sizes))

    iteration = 0
    reason = "direct_budget_reached"
    target_budget = min(config.max_evaluations, config.direct_prescan_evaluations)
    while evaluator.total_evaluations < target_budget:
        iteration += 1
        selected = select_potentially_optimal(rectangles)
        if not selected:
            reason = "direct_no_rectangles"
            break

        selected_ids = {rect.rect_id for rect in selected}
        next_rectangles: list[DirectRectangle[ObjectiveEvaluation]] = [
            rect for rect in rectangles if rect.rect_id not in selected_ids
        ]
        for rect in selected:
            for child_center, child_half_sizes in split_rectangle(rect):
                child = make_rectangle(child_center, child_half_sizes)
                next_rectangles.append(child)
                if evaluator.total_evaluations >= target_budget:
                    break
            if evaluator.total_evaluations >= target_budget:
                break

        rectangles = next_rectangles
        incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
        diagnostics.append(
            CmaesStageDiagnostics(
                stage="direct",
                iteration=iteration,
                total_evaluations=evaluator.total_evaluations,
                incumbent_fos=incumbent_fos,
                extra={
                    "potentially_optimal_count": len(selected),
                    "rectangle_count": len(rectangles),
                    "valid_evaluations": evaluator.valid_evaluations,
                    "infeasible_evaluations": evaluator.infeasible_evaluations,
                },
            )
        )

    valid_points = sorted(
        (
            (key, value.score, value.surface)
            for key, value in evaluator.valid_points()
            if value.surface is not None
        ),
        key=lambda item: (item[1], surface_key(item[2])),
    )
    elites = [point[0] for point in valid_points[:20]]
    if not elites:
        if evaluator.best_vector is not None:
            elites = [evaluator.best_vector]
        else:
            elites = [(0.5, 0.5, 0.5)]
    return elites, reason


def _run_cmaes_stage(
    evaluator: CachedObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    elites: list[tuple[float, float, float]],
    diagnostics: list[CmaesStageDiagnostics],
) -> str:
    try:
        import cma  # type: ignore
    except Exception as exc:
        raise RuntimeError("CMA-ES dependency 'cma' is required for cmaes_global_circular.") from exc

    restart_count = config.cmaes_restarts + 1
    reason = "cmaes_max_iterations"

    x0 = list(elites[0])
    if elites:
        weight_sum = 0.0
        mean = [0.0, 0.0, 0.0]
        for rank, elite in enumerate(elites[:8], start=1):
            weight = 1.0 / rank
            weight_sum += weight
            mean[0] += elite[0] * weight
            mean[1] += elite[1] * weight
            mean[2] += elite[2] * weight
        x0 = [mean[0] / weight_sum, mean[1] / weight_sum, mean[2] / weight_sum]

    sigma0 = config.cmaes_sigma0
    for restart in range(restart_count):
        if evaluator.total_evaluations >= config.max_evaluations:
            return "max_evaluations"

        opts = {
            "seed": config.seed + restart,
            "popsize": config.cmaes_population_size,
            "bounds": [0.0, 1.0],
            "verbose": -9,
            "verb_log": 0,
            "verb_disp": 0,
        }
        es = cma.CMAEvolutionStrategy(x0, sigma0, opts)
        stall_counter = 0

        for iteration in range(1, config.cmaes_max_iterations + 1):
            if evaluator.total_evaluations >= config.max_evaluations:
                return "max_evaluations"

            solutions = es.ask()
            repaired: list[list[float]] = []
            scores: list[float] = []
            before_best = evaluator.best_score

            for candidate in solutions:
                evaluation = evaluator.evaluate_vector((float(candidate[0]), float(candidate[1]), float(candidate[2])))
                repaired.append([evaluation.vector[0], evaluation.vector[1], evaluation.vector[2]])
                scores.append(float(evaluation.score))
                if evaluator.total_evaluations >= config.max_evaluations:
                    break

            es.tell(repaired, scores)

            current_best = evaluator.best_score
            incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
            diagnostics.append(
                CmaesStageDiagnostics(
                    stage="cmaes",
                    iteration=iteration + restart * config.cmaes_max_iterations,
                    total_evaluations=evaluator.total_evaluations,
                    incumbent_fos=incumbent_fos,
                    extra={
                        "restart": restart,
                        "sigma": float(es.sigma),
                        "population_size": len(repaired),
                        "valid_evaluations": evaluator.valid_evaluations,
                        "infeasible_evaluations": evaluator.infeasible_evaluations,
                    },
                )
            )

            improvement = before_best - current_best
            if improvement < config.min_improvement:
                stall_counter += 1
            else:
                stall_counter = 0

            if es.sigma < 1e-3:
                reason = "cmaes_sigma_limit"
                break
            if stall_counter >= config.stall_iterations:
                reason = "cmaes_stall_tolerance_reached"
                break

        if evaluator.best_vector is not None:
            x0 = [evaluator.best_vector[0], evaluator.best_vector[1], evaluator.best_vector[2]]
        else:
            x0 = list(elites[min(restart + 1, len(elites) - 1)])
        sigma0 = min(0.5, sigma0 * 1.5)

    return reason


def _toe_locked_sweep(
    profile: UniformSlopeProfile,
    evaluate_surface: SurfaceEvaluator,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
    x_left: float,
    y_left: float,
    right_values: list[float],
    beta_values: list[float],
) -> tuple[PrescribedCircleInput, AnalysisResult, float, float]:
    improved_x = right_values[0] if right_values else x_left
    improved_beta = beta_values[0] if beta_values else _TANGENT_EPS_RAD

    for x_right in right_values:
        if x_right <= x_left:
            continue
        y_right = profile.y_ground(x_right)
        for beta in beta_values:
            candidate = circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)
            evaluation = evaluate_surface_candidate(candidate, evaluate_surface, driving_moment_tol=1e-6)
            if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
                continue
            if is_better_score(evaluation.result.fos, evaluation.surface, best_result.fos, best_surface):
                best_surface = evaluation.surface
                best_result = evaluation.result
                improved_x = x_right
                improved_beta = beta

    return best_surface, best_result, improved_x, improved_beta


def _run_toe_locked_grid_refinement(
    profile: UniformSlopeProfile,
    evaluate_surface: SurfaceEvaluator,
    search_limits_x_min: float,
    search_limits_x_max: float,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    if not (search_limits_x_min <= profile.x_toe <= search_limits_x_max):
        return best_surface, best_result

    x_left = profile.x_toe
    y_left = profile.y_ground(x_left)

    right_min = max(search_limits_x_min, profile.crest_x)
    right_max = min(search_limits_x_max, profile.crest_x + 0.3 * profile.h)
    if right_max <= right_min:
        return best_surface, best_result

    beta_min = _TANGENT_EPS_RAD
    beta_max = BETA_MAX_RAD

    coarse_right = _linspace(right_min, right_max, _COARSE_TOE_LOCKED_SAMPLES)
    coarse_beta = _linspace(beta_min, beta_max, _COARSE_TOE_LOCKED_SAMPLES)
    best_surface, best_result, best_x_right, best_beta = _toe_locked_sweep(
        profile=profile,
        evaluate_surface=evaluate_surface,
        best_surface=best_surface,
        best_result=best_result,
        x_left=x_left,
        y_left=y_left,
        right_values=coarse_right,
        beta_values=coarse_beta,
    )

    right_step = (right_max - right_min) / (_COARSE_TOE_LOCKED_SAMPLES - 1)
    beta_step = (beta_max - beta_min) / (_COARSE_TOE_LOCKED_SAMPLES - 1)

    local_right_min = max(right_min, best_x_right - _LOCAL_HALF_WINDOW_STEPS * right_step)
    local_right_max = min(right_max, best_x_right + _LOCAL_HALF_WINDOW_STEPS * right_step)
    local_beta_min = max(beta_min, best_beta - _LOCAL_HALF_WINDOW_STEPS * beta_step)
    local_beta_max = min(beta_max, best_beta + _LOCAL_HALF_WINDOW_STEPS * beta_step)

    local_right = _linspace(local_right_min, local_right_max, _LOCAL_TOE_LOCKED_SAMPLES)
    local_beta = _linspace(local_beta_min, local_beta_max, _LOCAL_TOE_LOCKED_SAMPLES)
    best_surface, best_result, _, _ = _toe_locked_sweep(
        profile=profile,
        evaluate_surface=evaluate_surface,
        best_surface=best_surface,
        best_result=best_result,
        x_left=x_left,
        y_left=y_left,
        right_values=local_right,
        beta_values=local_beta,
    )

    return best_surface, best_result


def _run_polish_stage(
    evaluator: CachedObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
) -> str:
    if not config.post_polish:
        return "post_polish_disabled"

    start = evaluator.best_vector if evaluator.best_vector is not None else (0.5, 0.5, 0.5)
    if evaluator.total_evaluations >= config.max_evaluations:
        return "max_evaluations"
    stage_budget = min(config.polish_max_evaluations, config.max_evaluations - evaluator.total_evaluations)
    if stage_budget <= 0:
        return "max_evaluations"

    try:
        from scipy.optimize import minimize  # type: ignore
    except Exception as exc:
        raise RuntimeError("SciPy dependency is required for cmaes_global_circular polish stage.") from exc

    def objective(x: list[float]) -> float:
        evaluation = evaluator.evaluate_vector((float(x[0]), float(x[1]), float(x[2])))
        return evaluation.score

    result = minimize(
        objective,
        x0=[start[0], start[1], start[2]],
        method="Nelder-Mead",
        options={
            "maxiter": int(stage_budget),
            "maxfev": int(stage_budget),
            "xatol": 1e-4,
            "fatol": config.min_improvement,
            "disp": False,
        },
    )

    incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
    diagnostics.append(
        CmaesStageDiagnostics(
            stage="polish",
            iteration=1,
            total_evaluations=evaluator.total_evaluations,
            incumbent_fos=incumbent_fos,
            extra={
                "success": bool(result.success),
                "nfev": int(getattr(result, "nfev", 0)),
                "status": int(getattr(result, "status", 0)),
            },
        )
    )

    if evaluator.best_surface is not None and evaluator.best_result is not None:
        refine_config = default_post_polish_refine_config(config.search_limits)
        best_surface, best_result = _run_toe_crest_refinement(
            profile=evaluator.profile,
            config=refine_config,
            evaluate_surface=evaluator.evaluate_surface,
            best_surface=evaluator.best_surface,
            best_result=evaluator.best_result,
        )
        best_surface, best_result = _run_toe_locked_grid_refinement(
            profile=evaluator.profile,
            evaluate_surface=evaluator.evaluate_surface,
            search_limits_x_min=config.search_limits.x_min,
            search_limits_x_max=config.search_limits.x_max,
            best_surface=best_surface,
            best_result=best_result,
        )
        evaluator.best_surface = best_surface
        evaluator.best_result = best_result
        evaluator.best_score = best_result.fos

    return "polish_complete"


def run_cmaes_global_search(
    profile: UniformSlopeProfile,
    config: CmaesGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> CmaesGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= X_SEP_MIN:
        raise GeometryError("CMA-ES search limits must satisfy x_max - x_min > 0.05 m.")

    evaluator = CachedObjectiveEvaluator(
        profile=profile,
        x_min=x_min,
        x_max=x_max,
        max_evaluations=config.max_evaluations,
        evaluate_surface=evaluate_surface,
        policy=ObjectiveScoringPolicy(
            repair_vector=repair_vector_reflect,
            invalid_geometry_score=config.invalid_penalty,
            invalid_result_score=config.nonconverged_penalty,
            evaluation_exception_score=config.nonconverged_penalty,
            keep_invalid_payload=True,
        ),
        driving_moment_tol=1e-9,
    )
    diagnostics: list[CmaesStageDiagnostics] = []

    elites, direct_reason = _run_direct_prescan(evaluator, config, diagnostics)
    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("CMA-ES global search did not produce any valid surfaces in DIRECT prescan.")

    cma_reason = _run_cmaes_stage(evaluator, config, elites, diagnostics)
    polish_reason = _run_polish_stage(evaluator, config, diagnostics)

    if evaluator.best_surface is None or evaluator.best_result is None:
        raise ConvergenceError("CMA-ES global search did not produce any valid surfaces.")

    termination_reason = polish_reason
    if evaluator.total_evaluations >= config.max_evaluations:
        termination_reason = "max_evaluations"
    elif cma_reason.startswith("cmaes_"):
        termination_reason = cma_reason
    elif direct_reason.startswith("direct_"):
        termination_reason = direct_reason

    return CmaesGlobalSearchResult(
        winning_surface=evaluator.best_surface,
        winning_result=evaluator.best_result,
        iteration_diagnostics=diagnostics,
        total_evaluations=evaluator.total_evaluations,
        valid_evaluations=evaluator.valid_evaluations,
        infeasible_evaluations=evaluator.infeasible_evaluations,
        termination_reason=termination_reason,
    )
