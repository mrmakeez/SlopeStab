from __future__ import annotations

from dataclasses import dataclass
import math
import random

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisResult,
    AutoRefineSearchInput,
    CmaesGlobalSearchInput,
    PrescribedCircleInput,
)
from slope_stab.search.auto_refine import _run_toe_crest_refinement
from slope_stab.search.common import (
    BETA_MAX_RAD,
    CACHE_ROUND,
    TIE_TOL,
    X_SEP_MIN,
    SurfaceEvaluator,
    circle_from_endpoints_and_tangent,
    clip01,
    evaluate_surface_candidate,
    is_better_score,
    map_vector_to_surface,
    repair_vector_reflect,
    round_vector,
    surface_key,
)


_SIZE_ROUND = 15
_DIMENSIONS = 3
_LIPSCHITZ_POWERS = tuple(range(-6, 7))
_TANGENT_EPS_RAD = math.radians(0.5)


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


@dataclass(frozen=True)
class _Evaluation:
    score: float
    surface: PrescribedCircleInput | None
    result: AnalysisResult | None
    valid: bool
    reason: str


@dataclass(frozen=True)
class _Rectangle:
    rect_id: int
    center: tuple[float, float, float]
    half_sizes: tuple[float, float, float]
    evaluation: _Evaluation

    @property
    def size_metric(self) -> float:
        return max(self.half_sizes)


class _ObjectiveEvaluator:
    def __init__(
        self,
        profile: UniformSlopeProfile,
        config: CmaesGlobalSearchInput,
        evaluate_surface: SurfaceEvaluator,
    ) -> None:
        self.profile = profile
        self.config = config
        self.evaluate_surface = evaluate_surface
        self.x_min = config.search_limits.x_min
        self.x_max = config.search_limits.x_max
        self.cache: dict[tuple[float, float, float], _Evaluation] = {}
        self.total_evaluations = 0
        self.valid_evaluations = 0
        self.infeasible_evaluations = 0
        self.best_surface: PrescribedCircleInput | None = None
        self.best_result: AnalysisResult | None = None
        self.best_score = float("inf")
        self.best_vector: tuple[float, float, float] = (0.5, 0.5, 0.5)

    def evaluate_vector(self, vector: tuple[float, float, float]) -> _Evaluation:
        key = round_vector(repair_vector_reflect(vector), digits=CACHE_ROUND)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if self.total_evaluations >= self.config.max_evaluations:
            evaluation = _Evaluation(
                score=self.config.invalid_penalty,
                surface=None,
                result=None,
                valid=False,
                reason="max_evaluations",
            )
            self.cache[key] = evaluation
            return evaluation

        self.total_evaluations += 1
        surface = map_vector_to_surface(
            profile=self.profile,
            x_min=self.x_min,
            x_max=self.x_max,
            vector=key,
            repair_vector=repair_vector_reflect,
        )
        candidate = evaluate_surface_candidate(surface, self.evaluate_surface, driving_moment_tol=1e-9)

        if not candidate.valid or candidate.surface is None or candidate.result is None:
            self.infeasible_evaluations += 1
            penalty = self.config.invalid_penalty if candidate.reason == "invalid_geometry" else self.config.nonconverged_penalty
            evaluation = _Evaluation(
                score=penalty,
                surface=candidate.surface,
                result=candidate.result,
                valid=False,
                reason=candidate.reason,
            )
            self.cache[key] = evaluation
            return evaluation

        self.valid_evaluations += 1
        evaluation = _Evaluation(
            score=candidate.result.fos,
            surface=candidate.surface,
            result=candidate.result,
            valid=True,
            reason="valid",
        )
        self.cache[key] = evaluation
        self._update_incumbent(key, evaluation)
        return evaluation

    def _update_incumbent(self, vector: tuple[float, float, float], evaluation: _Evaluation) -> None:
        if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
            return
        if is_better_score(evaluation.score, evaluation.surface, self.best_score, self.best_surface):
            self.best_surface = evaluation.surface
            self.best_result = evaluation.result
            self.best_score = evaluation.score
            self.best_vector = vector


def _best_rect_per_size(rectangles: list[_Rectangle]) -> list[_Rectangle]:
    best_by_size: dict[float, _Rectangle] = {}
    for rect in rectangles:
        key = round(rect.size_metric, _SIZE_ROUND)
        current = best_by_size.get(key)
        if current is None:
            best_by_size[key] = rect
            continue
        if rect.evaluation.score < current.evaluation.score - TIE_TOL:
            best_by_size[key] = rect
            continue
        if abs(rect.evaluation.score - current.evaluation.score) <= TIE_TOL and rect.rect_id < current.rect_id:
            best_by_size[key] = rect
    return sorted(best_by_size.values(), key=lambda r: (r.size_metric, r.evaluation.score, r.rect_id))


def _select_potentially_optimal(rectangles: list[_Rectangle]) -> list[_Rectangle]:
    if not rectangles:
        return []
    reduced = _best_rect_per_size(rectangles)
    selected: dict[int, _Rectangle] = {}
    k_values = [0.0] + [10.0 ** power for power in _LIPSCHITZ_POWERS]
    for k in k_values:
        chosen = min(
            reduced,
            key=lambda r: (r.evaluation.score - k * r.size_metric, r.evaluation.score, r.rect_id),
        )
        selected[chosen.rect_id] = chosen
    return sorted(selected.values(), key=lambda r: r.rect_id)


def _run_direct_prescan(
    evaluator: _ObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
) -> tuple[list[tuple[float, float, float]], str]:
    rectangles: list[_Rectangle] = []
    next_rect_id = 0

    def make_rectangle(center: tuple[float, float, float], half_sizes: tuple[float, float, float]) -> _Rectangle:
        nonlocal next_rect_id
        eval_result = evaluator.evaluate_vector(center)
        rect = _Rectangle(
            rect_id=next_rect_id,
            center=center,
            half_sizes=half_sizes,
            evaluation=eval_result,
        )
        next_rect_id += 1
        return rect

    centers_1d = (1.0 / 6.0, 0.5, 5.0 / 6.0)
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
        selected = _select_potentially_optimal(rectangles)
        if not selected:
            reason = "direct_no_rectangles"
            break

        selected_ids = {rect.rect_id for rect in selected}
        next_rectangles: list[_Rectangle] = [rect for rect in rectangles if rect.rect_id not in selected_ids]
        for rect in selected:
            half_sizes = rect.half_sizes
            split_dim = min(
                (i for i in range(_DIMENSIONS) if abs(half_sizes[i] - max(half_sizes)) <= TIE_TOL),
                default=0,
            )
            delta = half_sizes[split_dim] / 3.0
            new_half_sizes = list(half_sizes)
            new_half_sizes[split_dim] = delta
            child_half_sizes = (new_half_sizes[0], new_half_sizes[1], new_half_sizes[2])
            for shift in (-delta, 0.0, delta):
                child_center = list(rect.center)
                child_center[split_dim] = clip01(child_center[split_dim] + shift)
                child = make_rectangle((child_center[0], child_center[1], child_center[2]), child_half_sizes)
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
            for key, value in evaluator.cache.items()
            if value.valid and value.surface is not None
        ),
        key=lambda item: (item[1], surface_key(item[2])),
    )
    elites = [point[0] for point in valid_points[:20]]
    if not elites:
        elites = [evaluator.best_vector]
    return elites, reason


def _run_cmaes_stage(
    evaluator: _ObjectiveEvaluator,
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
    rng = random.Random(config.seed)

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
                vector = round_vector(
                    repair_vector_reflect((float(candidate[0]), float(candidate[1]), float(candidate[2]))),
                    digits=CACHE_ROUND,
                )
                evaluation = evaluator.evaluate_vector(vector)
                repaired.append([vector[0], vector[1], vector[2]])
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

        if evaluator.best_vector:
            x0 = [evaluator.best_vector[0], evaluator.best_vector[1], evaluator.best_vector[2]]
        else:
            x0 = [rng.random(), rng.random(), rng.random()]
        sigma0 = min(0.5, sigma0 * 1.5)

    return reason


def _run_polish_stage(
    evaluator: _ObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
) -> str:
    if not config.post_polish:
        return "post_polish_disabled"

    start = evaluator.best_vector
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
        vector = round_vector(repair_vector_reflect((float(x[0]), float(x[1]), float(x[2]))), digits=CACHE_ROUND)
        evaluation = evaluator.evaluate_vector(vector)
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
        refine_config = AutoRefineSearchInput(
            divisions_along_slope=2,
            circles_per_division=15,
            iterations=1,
            divisions_to_use_next_iteration_pct=50.0,
            search_limits=config.search_limits,
        )
        best_surface, best_result = _run_toe_crest_refinement(
            profile=evaluator.profile,
            config=refine_config,
            evaluate_surface=evaluator.evaluate_surface,
            best_surface=evaluator.best_surface,
            best_result=evaluator.best_result,
        )
        best_surface, best_result = _run_toe_locked_grid_refinement(
            profile=evaluator.profile,
            config=refine_config,
            evaluate_surface=evaluator.evaluate_surface,
            best_surface=best_surface,
            best_result=best_result,
        )
        evaluator.best_surface = best_surface
        evaluator.best_result = best_result
        evaluator.best_score = best_result.fos

    return "polish_complete"


def _run_toe_locked_grid_refinement(
    profile: UniformSlopeProfile,
    config: AutoRefineSearchInput,
    evaluate_surface: SurfaceEvaluator,
    best_surface: PrescribedCircleInput,
    best_result: AnalysisResult,
) -> tuple[PrescribedCircleInput, AnalysisResult]:
    if not (config.search_limits.x_min <= profile.x_toe <= config.search_limits.x_max):
        return best_surface, best_result

    x_left = profile.x_toe
    y_left = profile.y_ground(x_left)

    right_min = max(config.search_limits.x_min, profile.crest_x)
    right_max = min(config.search_limits.x_max, profile.crest_x + 0.3 * profile.h)
    if right_max <= right_min:
        return best_surface, best_result

    right_samples = 81
    beta_samples = 81
    for i in range(right_samples):
        frac = i / (right_samples - 1)
        x_right = right_min + frac * (right_max - right_min)
        if x_right <= x_left:
            continue
        y_right = profile.y_ground(x_right)
        for k in range(beta_samples):
            u = k / (beta_samples - 1)
            beta = _TANGENT_EPS_RAD + (BETA_MAX_RAD - _TANGENT_EPS_RAD) * u
            candidate = circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)
            evaluation = evaluate_surface_candidate(candidate, evaluate_surface, driving_moment_tol=1e-6)
            if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
                continue
            if is_better_score(evaluation.result.fos, evaluation.surface, best_result.fos, best_surface):
                best_surface = evaluation.surface
                best_result = evaluation.result

    return best_surface, best_result


def run_cmaes_global_search(
    profile: UniformSlopeProfile,
    config: CmaesGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> CmaesGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= X_SEP_MIN:
        raise GeometryError("CMA-ES search limits must satisfy x_max - x_min > 0.05 m.")

    evaluator = _ObjectiveEvaluator(profile=profile, config=config, evaluate_surface=evaluate_surface)
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
