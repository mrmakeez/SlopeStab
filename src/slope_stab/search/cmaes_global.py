from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from slope_stab.exceptions import ConvergenceError, GeometryError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import (
    AnalysisResult,
    AutoRefineSearchInput,
    CmaesGlobalSearchInput,
    PrescribedCircleInput,
)
from slope_stab.search.auto_refine import _run_toe_crest_refinement


SurfaceEvaluator = Callable[[PrescribedCircleInput], AnalysisResult]

_X_SEP_MIN = 0.05
_BETA_MIN_RAD = math.radians(0.5)
_BETA_MAX_RAD = math.radians(89.5)
_TIE_TOL = 1e-12
_CACHE_ROUND = 15
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


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _reflect01(value: float) -> float:
    x = float(value)
    while x < 0.0 or x > 1.0:
        if x < 0.0:
            x = -x
        if x > 1.0:
            x = 2.0 - x
    return _clip01(x)


def _repair_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (_reflect01(vector[0]), _reflect01(vector[1]), _reflect01(vector[2]))


def _round_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (round(vector[0], _CACHE_ROUND), round(vector[1], _CACHE_ROUND), round(vector[2], _CACHE_ROUND))


def _surface_key(surface: PrescribedCircleInput) -> tuple[float, float, float]:
    return (surface.x_left, surface.x_right, surface.r)


def _map_to_surface(
    profile: UniformSlopeProfile,
    x_min: float,
    x_max: float,
    vector: tuple[float, float, float],
) -> PrescribedCircleInput | None:
    u_left, u_span, u_beta = _repair_vector(vector)
    width = x_max - x_min
    if width <= _X_SEP_MIN:
        return None

    left_range = width - _X_SEP_MIN
    x_left = x_min + u_left * left_range
    right_range = x_max - x_left - _X_SEP_MIN
    if right_range < 0.0:
        return None

    x_right = x_left + _X_SEP_MIN + u_span * right_range
    if x_right <= x_left:
        return None

    y_left = profile.y_ground(x_left)
    y_right = profile.y_ground(x_right)
    beta = _BETA_MIN_RAD + u_beta * (_BETA_MAX_RAD - _BETA_MIN_RAD)
    return _circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)


def _circle_from_endpoints_and_tangent(
    p_left: tuple[float, float],
    p_right: tuple[float, float],
    beta: float,
) -> PrescribedCircleInput | None:
    x1, y1 = p_left
    x2, y2 = p_right
    if x2 <= x1:
        return None
    if beta <= 0.0 or beta >= 0.5 * math.pi:
        return None

    dx = x2 - x1
    dy = y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0.0:
        return None

    sin_beta = math.sin(beta)
    tan_beta = math.tan(beta)
    if abs(sin_beta) <= 1e-12 or abs(tan_beta) <= 1e-12:
        return None

    radius = chord / (2.0 * sin_beta)
    center_offset = chord / (2.0 * tan_beta)
    if radius <= 0.0 or not math.isfinite(radius) or not math.isfinite(center_offset):
        return None

    mid_x = 0.5 * (x1 + x2)
    mid_y = 0.5 * (y1 + y2)

    normal_x = -dy / chord
    normal_y = dx / chord
    if normal_y < 0.0:
        normal_x = -normal_x
        normal_y = -normal_y

    xc = mid_x + center_offset * normal_x
    yc = mid_y + center_offset * normal_y
    if not math.isfinite(xc) or not math.isfinite(yc):
        return None
    if yc <= max(y1, y2) + 1e-9:
        return None

    return PrescribedCircleInput(
        xc=xc,
        yc=yc,
        r=radius,
        x_left=x1,
        y_left=y1,
        x_right=x2,
        y_right=y2,
    )


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
        key = _round_vector(_repair_vector(vector))
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
        surface = _map_to_surface(self.profile, self.x_min, self.x_max, key)
        if surface is None:
            self.infeasible_evaluations += 1
            evaluation = _Evaluation(
                score=self.config.invalid_penalty,
                surface=None,
                result=None,
                valid=False,
                reason="invalid_geometry",
            )
            self.cache[key] = evaluation
            return evaluation

        try:
            result = self.evaluate_surface(surface)
        except (ConvergenceError, GeometryError, ValueError):
            self.infeasible_evaluations += 1
            evaluation = _Evaluation(
                score=self.config.nonconverged_penalty,
                surface=surface,
                result=None,
                valid=False,
                reason="evaluation_exception",
            )
            self.cache[key] = evaluation
            return evaluation

        if (
            (not result.converged)
            or (not math.isfinite(result.fos))
            or result.fos <= 0.0
            or (not math.isfinite(result.driving_moment))
            or abs(result.driving_moment) <= 1e-9
            or (not math.isfinite(result.resisting_moment))
        ):
            self.infeasible_evaluations += 1
            evaluation = _Evaluation(
                score=self.config.nonconverged_penalty,
                surface=surface,
                result=result,
                valid=False,
                reason="nonconverged_or_invalid_fos",
            )
            self.cache[key] = evaluation
            return evaluation

        self.valid_evaluations += 1
        evaluation = _Evaluation(
            score=result.fos,
            surface=surface,
            result=result,
            valid=True,
            reason="valid",
        )
        self.cache[key] = evaluation
        self._update_incumbent(key, evaluation)
        return evaluation

    def _update_incumbent(self, vector: tuple[float, float, float], evaluation: _Evaluation) -> None:
        if not evaluation.valid or evaluation.surface is None or evaluation.result is None:
            return
        if self.best_surface is None or self.best_result is None:
            self.best_surface = evaluation.surface
            self.best_result = evaluation.result
            self.best_score = evaluation.score
            self.best_vector = vector
            return
        if evaluation.score < self.best_score - _TIE_TOL:
            self.best_surface = evaluation.surface
            self.best_result = evaluation.result
            self.best_score = evaluation.score
            self.best_vector = vector
            return
        if abs(evaluation.score - self.best_score) <= _TIE_TOL and _surface_key(evaluation.surface) < _surface_key(self.best_surface):
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
        if rect.evaluation.score < current.evaluation.score - _TIE_TOL:
            best_by_size[key] = rect
            continue
        if abs(rect.evaluation.score - current.evaluation.score) <= _TIE_TOL and rect.rect_id < current.rect_id:
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
    while evaluator.total_evaluations < min(config.max_evaluations, config.direct_prescan_evaluations):
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
                (i for i in range(_DIMENSIONS) if abs(half_sizes[i] - max(half_sizes)) <= _TIE_TOL),
                default=0,
            )
            delta = half_sizes[split_dim] / 3.0
            new_half_sizes = list(half_sizes)
            new_half_sizes[split_dim] = delta
            child_half_sizes = (new_half_sizes[0], new_half_sizes[1], new_half_sizes[2])
            for shift in (-delta, 0.0, delta):
                child_center = list(rect.center)
                child_center[split_dim] = _clip01(child_center[split_dim] + shift)
                child = make_rectangle((child_center[0], child_center[1], child_center[2]), child_half_sizes)
                next_rectangles.append(child)
                if evaluator.total_evaluations >= min(config.max_evaluations, config.direct_prescan_evaluations):
                    break
            if evaluator.total_evaluations >= min(config.max_evaluations, config.direct_prescan_evaluations):
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
        key=lambda item: (item[1], _surface_key(item[2])),
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
    except Exception:
        return _run_fallback_seeded_stage(evaluator, config, diagnostics)

    restart_count = config.cmaes_restarts + 1
    best_history: list[float] = []
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
                vector = _round_vector(
                    _repair_vector((float(candidate[0]), float(candidate[1]), float(candidate[2])))
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

            best_history.append(current_best)
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


def _run_fallback_seeded_stage(
    evaluator: _ObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
) -> str:
    rng = random.Random(config.seed)
    best_history: list[float] = []
    reason = "fallback_max_iterations"
    current = evaluator.best_vector

    total_iters = max(1, config.cmaes_max_iterations * (config.cmaes_restarts + 1))
    for iteration in range(1, total_iters + 1):
        if evaluator.total_evaluations >= config.max_evaluations:
            return "max_evaluations"
        alpha = max(0.01, config.cmaes_sigma0 * math.exp(-2.0 * iteration / total_iters))
        before_best = evaluator.best_score
        for _ in range(config.cmaes_population_size):
            trial = _round_vector(
                _repair_vector(
                    (
                        current[0] + rng.gauss(0.0, alpha),
                        current[1] + rng.gauss(0.0, alpha),
                        current[2] + rng.gauss(0.0, alpha),
                    )
                )
            )
            evaluator.evaluate_vector(trial)
            if evaluator.total_evaluations >= config.max_evaluations:
                return "max_evaluations"
        current = evaluator.best_vector
        incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
        diagnostics.append(
            CmaesStageDiagnostics(
                stage="cmaes",
                iteration=iteration,
                total_evaluations=evaluator.total_evaluations,
                incumbent_fos=incumbent_fos,
                extra={
                    "fallback": True,
                    "alpha": alpha,
                    "valid_evaluations": evaluator.valid_evaluations,
                    "infeasible_evaluations": evaluator.infeasible_evaluations,
                },
            )
        )
        best_history.append(evaluator.best_score)
        if len(best_history) > config.stall_iterations:
            prev = best_history[-config.stall_iterations - 1]
            curr = best_history[-1]
            if (prev - curr) < config.min_improvement:
                reason = "fallback_stall_tolerance_reached"
                break

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
    except Exception:
        return _run_fallback_polish(evaluator, config, diagnostics, stage_budget)

    def objective(x: list[float]) -> float:
        vector = _round_vector(_repair_vector((float(x[0]), float(x[1]), float(x[2]))))
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

    # Final deterministic toe/crest-focused refinement for parity consistency.
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


def _run_fallback_polish(
    evaluator: _ObjectiveEvaluator,
    config: CmaesGlobalSearchInput,
    diagnostics: list[CmaesStageDiagnostics],
    stage_budget: int,
) -> str:
    current = evaluator.best_vector
    step = 0.06
    used = 0
    while used < stage_budget:
        improved = False
        for dim in range(3):
            for sign in (-1.0, 1.0):
                if used >= stage_budget:
                    break
                trial = list(current)
                trial[dim] = trial[dim] + sign * step
                trial_vec = _round_vector(_repair_vector((trial[0], trial[1], trial[2])))
                before = evaluator.best_score
                evaluator.evaluate_vector(trial_vec)
                used += 1
                if evaluator.best_score < before - _TIE_TOL:
                    current = evaluator.best_vector
                    improved = True
        step *= 0.7
        if not improved and step < 1e-3:
            break

    incumbent_fos = evaluator.best_result.fos if evaluator.best_result is not None else float("inf")
    diagnostics.append(
        CmaesStageDiagnostics(
            stage="polish",
            iteration=1,
            total_evaluations=evaluator.total_evaluations,
            incumbent_fos=incumbent_fos,
            extra={
                "fallback": True,
                "used_evaluations": used,
                "final_step": step,
            },
        )
    )
    return "fallback_polish_complete"


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
            beta = _TANGENT_EPS_RAD + (_BETA_MAX_RAD - _TANGENT_EPS_RAD) * u
            candidate = _circle_from_endpoints_and_tangent((x_left, y_left), (x_right, y_right), beta)
            if candidate is None:
                continue
            try:
                result = evaluate_surface(candidate)
            except (ConvergenceError, GeometryError, ValueError):
                continue
            if not math.isfinite(result.fos) or result.fos <= 0.0:
                continue
            if not math.isfinite(result.driving_moment) or abs(result.driving_moment) <= 1e-6:
                continue

            if result.fos < best_result.fos - _TIE_TOL:
                best_surface = candidate
                best_result = result
            elif abs(result.fos - best_result.fos) <= _TIE_TOL:
                candidate_key = (candidate.x_left, candidate.x_right, candidate.r)
                best_key = (best_surface.x_left, best_surface.x_right, best_surface.r)
                if candidate_key < best_key:
                    best_surface = candidate
                    best_result = result

    return best_surface, best_result


def run_cmaes_global_search(
    profile: UniformSlopeProfile,
    config: CmaesGlobalSearchInput,
    evaluate_surface: SurfaceEvaluator,
) -> CmaesGlobalSearchResult:
    x_min = config.search_limits.x_min
    x_max = config.search_limits.x_max
    if x_max - x_min <= _X_SEP_MIN:
        raise GeometryError("CMA-ES search limits must satisfy x_max - x_min > 0.05 m.")

    # Force reproducible RNG state for all downstream stochastic libraries.
    try:
        import numpy as np  # type: ignore

        np.random.seed(config.seed)
    except Exception:
        pass
    random.seed(config.seed)

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
    elif cma_reason.startswith("cmaes_") or cma_reason.startswith("fallback_"):
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
