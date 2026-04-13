from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq, root

from slope_stab.exceptions import ConvergenceError
from slope_stab.lem_core.base import LEMSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisInput, AnalysisResult, IterationState, SliceGeometry, SliceResult
from slope_stab.surfaces.circular import CircularSlipSurface


@dataclass(frozen=True)
class _SpencerState:
    fos: float
    lambda_value: float
    force_residual_norm: float
    moment_residual: float
    m_alpha: np.ndarray
    normal: np.ndarray
    shear_strength: np.ndarray
    cohesion_base: np.ndarray
    denominator: float
    delta_e: np.ndarray


class SpencerSolver(LEMSolver):
    _LAMBDA_BOUNDS = (-5.0, 5.0)
    _M_ALPHA_MIN = 0.2

    def __init__(
        self,
        analysis: AnalysisInput | MohrCoulombMaterial,
        surface: CircularSlipSurface | AnalysisInput,
        material: MohrCoulombMaterial | CircularSlipSurface | None = None,
    ) -> None:
        if isinstance(analysis, MohrCoulombMaterial):
            # Backward-compatible constructor form:
            # SpencerSolver(material, analysis, surface)
            if not isinstance(surface, AnalysisInput) or not isinstance(material, CircularSlipSurface):
                raise TypeError(
                    "Legacy SpencerSolver signature requires "
                    "(material: MohrCoulombMaterial, analysis: AnalysisInput, surface: CircularSlipSurface)."
                )
            self._analysis = surface
            self._surface = material
            self._material = analysis
            return

        if not isinstance(analysis, AnalysisInput) or not isinstance(surface, CircularSlipSurface):
            raise TypeError(
                "SpencerSolver requires "
                "(analysis: AnalysisInput, surface: CircularSlipSurface, material: MohrCoulombMaterial | None)."
            )
        if material is not None and not isinstance(material, MohrCoulombMaterial):
            raise TypeError("SpencerSolver material must be MohrCoulombMaterial or None.")

        self._analysis = analysis
        self._surface = surface
        self._material = material

    def _compute_state(
        self,
        f_k: float,
        lambda_value: float,
        weights: np.ndarray,
        external_force_x: np.ndarray,
        pore_forces: np.ndarray,
        sin_a: np.ndarray,
        cos_a: np.ndarray,
        tan_phi: np.ndarray,
        cohesion_base: np.ndarray,
        denominator: float,
        scale_force: float,
    ) -> _SpencerState:
        if f_k <= 0.0 or not math.isfinite(f_k):
            raise ConvergenceError("Spencer FOS is non-positive or non-finite during iteration.")
        if not math.isfinite(lambda_value):
            raise ConvergenceError("Spencer lambda is non-finite during iteration.")
        if lambda_value < self._LAMBDA_BOUNDS[0] or lambda_value > self._LAMBDA_BOUNDS[1]:
            raise ConvergenceError(f"Spencer lambda is outside supported bounds {self._LAMBDA_BOUNDS}.")

        a_term = sin_a - (tan_phi * cos_a) / f_k
        b_term = cos_a + (tan_phi * sin_a) / f_k
        m_alpha = b_term + lambda_value * a_term

        if np.any(np.abs(m_alpha) < 1e-12):
            bad_idx = int(np.flatnonzero(np.abs(m_alpha) < 1e-12)[0])
            raise ConvergenceError(
                f"Slice {bad_idx + 1}: Spencer m_alpha approaches zero."
            )
        if np.any(np.abs(b_term) < 1e-12):
            bad_idx = int(np.flatnonzero(np.abs(b_term) < 1e-12)[0])
            raise ConvergenceError(
                f"Slice {bad_idx + 1}: Spencer B-term approaches zero."
            )

        # Represent pore pressure through effective-base terms:
        # T = cL + (N - U) * tan(phi), where U is base-normal pore resultant.
        cohesion_effective = cohesion_base - (pore_forces * tan_phi)
        delta_e = (
            (weights * a_term)
            + (external_force_x * b_term)
            - (cohesion_effective / f_k)
        ) / m_alpha
        normal_total = (weights - lambda_value * delta_e - (cohesion_effective * sin_a) / f_k) / b_term
        normal = normal_total - pore_forces

        shear_strength = np.maximum(cohesion_base + (normal * tan_phi), 0.0)

        force_residual = -float(np.sum(delta_e))
        force_residual_norm = force_residual / scale_force

        fos_from_moment = float(np.sum(shear_strength) / denominator)
        moment_residual = f_k - fos_from_moment

        return _SpencerState(
            fos=f_k,
            lambda_value=lambda_value,
            force_residual_norm=force_residual_norm,
            moment_residual=moment_residual,
            m_alpha=m_alpha,
            normal=normal,
            shear_strength=shear_strength,
            cohesion_base=cohesion_base,
            denominator=denominator,
            delta_e=delta_e,
        )

    def solve(self, slices: list[SliceGeometry]) -> AnalysisResult:
        if self._analysis.f_init <= 0.0:
            raise ConvergenceError("Initial FOS must be greater than zero.")

        slice_ids = np.fromiter((s.slice_id for s in slices), dtype=int)
        x_left = np.fromiter((s.x_left for s in slices), dtype=float)
        x_right = np.fromiter((s.x_right for s in slices), dtype=float)
        soil_weights = np.fromiter((s.weight for s in slices), dtype=float)
        external_force_x = np.fromiter((s.external_force_x for s in slices), dtype=float)
        external_force_y = np.fromiter((s.external_force_y for s in slices), dtype=float)
        external_x_app = np.fromiter((s.external_x_app for s in slices), dtype=float)
        external_y_app = np.fromiter((s.external_y_app for s in slices), dtype=float)
        weights = soil_weights + external_force_y
        pore_forces = np.fromiter((s.pore_force for s in slices), dtype=float)
        alpha = np.fromiter((s.alpha_rad for s in slices), dtype=float)
        base_lengths = np.fromiter((s.base_length for s in slices), dtype=float)
        base_cohesion = np.fromiter((s.base_cohesion for s in slices), dtype=float)
        base_phi_deg = np.fromiter((s.base_phi_deg for s in slices), dtype=float)
        if self._material is not None and np.allclose(base_cohesion, 0.0) and np.allclose(base_phi_deg, 0.0):
            base_cohesion = np.full_like(base_cohesion, self._material.cohesion)
            base_phi_deg = np.full_like(base_phi_deg, self._material.phi_deg)
        tan_phi = np.tan(np.radians(base_phi_deg))

        sin_a = np.sin(alpha)
        cos_a = np.cos(alpha)

        x_mid = 0.5 * (x_left + x_right)
        x_offset = x_mid - self._surface.xc
        external_x_offset = external_x_app - self._surface.xc
        external_y_offset = external_y_app - self._surface.yc
        driving_moment_component = (
            (soil_weights * x_offset)
            + (external_force_y * external_x_offset)
            - (external_force_x * external_y_offset)
        )
        driving_component = driving_moment_component / self._surface.r
        denominator_raw = float(np.sum(driving_component))
        direction = 1.0 if denominator_raw >= 0.0 else -1.0
        sin_a = sin_a * direction
        denominator = abs(denominator_raw)
        if abs(denominator) < 1e-12:
            raise ConvergenceError("Driving denominator is numerically zero.")

        cohesion_base = base_cohesion * base_lengths
        scale_force = max(float(np.sum(np.abs(weights))), 1.0)

        def evaluate_state(
            fos: float,
            lambda_value: float,
        ) -> _SpencerState:
            return self._compute_state(
                f_k=fos,
                lambda_value=lambda_value,
                weights=weights,
                external_force_x=external_force_x,
                pore_forces=pore_forces,
                sin_a=sin_a,
                cos_a=cos_a,
                tan_phi=tan_phi,
                cohesion_base=cohesion_base,
                denominator=denominator,
                scale_force=scale_force,
            )

        def residuals(vec: np.ndarray) -> np.ndarray:
            fos = max(float(vec[0]), 1e-6)
            lambda_value = float(vec[1])
            try:
                state = evaluate_state(fos, lambda_value)
            except ConvergenceError:
                return np.array([1e6, 1e6], dtype=float)
            return np.array([state.force_residual_norm, state.moment_residual], dtype=float)

        def solve_lambda_zero_fallback() -> tuple[_SpencerState | None, int, dict[str, float | bool | str]]:
            fallback_meta: dict[str, float | bool | str] = {
                "attempted": False,
                "accepted": False,
                "bracket_found": False,
            }

            if not has_horizontal_external:
                fallback_meta["reason"] = "no_horizontal_external_force"
                return None, 0, fallback_meta

            fallback_meta["attempted"] = True

            probe_values = [
                1e-4,
                5e-4,
                1e-3,
                2e-3,
                5e-3,
                1e-2,
                2e-2,
                5e-2,
                1e-1,
                2e-1,
                3.5e-1,
                5e-1,
                7.5e-1,
                1.0,
                1.25,
                1.5,
                2.0,
                2.5,
                3.0,
                4.0,
                5.0,
                7.5,
                10.0,
                15.0,
                20.0,
            ]
            probe_values.append(max(self._analysis.f_init, 1e-6))
            probe_values = sorted(set(probe_values))

            bracket: tuple[float, float] | None = None
            last_f: float | None = None
            last_r: float | None = None
            eval_calls = 0

            for fos_probe in probe_values:
                try:
                    probe_state = evaluate_state(float(fos_probe), 0.0)
                except ConvergenceError:
                    continue
                eval_calls += 1
                residual = float(probe_state.force_residual_norm)
                if not math.isfinite(residual):
                    continue
                if abs(residual) <= self._analysis.tolerance:
                    bracket = (float(fos_probe), float(fos_probe))
                    break
                if last_f is not None and last_r is not None and residual * last_r < 0.0:
                    bracket = (float(last_f), float(fos_probe))
                    break
                last_f = float(fos_probe)
                last_r = residual

            if bracket is None:
                fallback_meta["reason"] = "lambda_zero_bracket_not_found"
                fallback_meta["eval_calls"] = float(eval_calls)
                return None, eval_calls, fallback_meta

            fallback_meta["bracket_found"] = True
            fallback_meta["bracket_left"] = float(bracket[0])
            fallback_meta["bracket_right"] = float(bracket[1])

            if abs(bracket[1] - bracket[0]) <= 1e-15:
                try:
                    state = evaluate_state(float(bracket[0]), 0.0)
                except ConvergenceError:
                    fallback_meta["reason"] = "lambda_zero_state_failed_at_exact_probe"
                    return None, eval_calls, fallback_meta
            else:
                def force_residual_lambda_zero(fos_value: float) -> float:
                    return float(evaluate_state(float(fos_value), 0.0).force_residual_norm)

                try:
                    root_fos, root_info = brentq(
                        force_residual_lambda_zero,
                        float(bracket[0]),
                        float(bracket[1]),
                        xtol=max(1e-9, self._analysis.tolerance * 0.1),
                        rtol=1e-12,
                        maxiter=max(100, self._analysis.max_iter * 10),
                        full_output=True,
                        disp=False,
                    )
                except (ValueError, RuntimeError, ConvergenceError):
                    fallback_meta["reason"] = "lambda_zero_brentq_failed"
                    fallback_meta["eval_calls"] = float(eval_calls)
                    return None, eval_calls, fallback_meta

                eval_calls += int(getattr(root_info, "function_calls", 0))
                try:
                    state = evaluate_state(float(root_fos), 0.0)
                except ConvergenceError:
                    fallback_meta["reason"] = "lambda_zero_state_failed_after_brentq"
                    fallback_meta["eval_calls"] = float(eval_calls)
                    return None, eval_calls, fallback_meta

            fallback_meta["force_residual_norm"] = float(state.force_residual_norm)
            fallback_meta["moment_residual"] = float(state.moment_residual)
            fallback_meta["min_m_alpha"] = float(np.min(state.m_alpha))
            fallback_meta["eval_calls"] = float(eval_calls)

            if abs(state.force_residual_norm) > self._analysis.tolerance:
                fallback_meta["reason"] = "lambda_zero_force_residual_exceeds_tolerance"
                return None, eval_calls, fallback_meta
            if abs(state.moment_residual) > self._analysis.tolerance:
                fallback_meta["reason"] = "lambda_zero_moment_residual_exceeds_tolerance"
                return None, eval_calls, fallback_meta
            if np.any(state.m_alpha < self._M_ALPHA_MIN):
                fallback_meta["reason"] = "lambda_zero_m_alpha_below_threshold"
                return None, eval_calls, fallback_meta

            fallback_meta["accepted"] = True
            fallback_meta["reason"] = "accepted"
            return state, eval_calls, fallback_meta

        has_horizontal_external = bool(np.any(np.abs(external_force_x) > 1e-12))
        if has_horizontal_external:
            starts = (
                (max(self._analysis.f_init, 1e-3), 0.35),
                (max(self._analysis.f_init, 1e-3), 0.20),
                (max(self._analysis.f_init, 1e-3), 0.60),
                (1.0, 0.35),
                (0.90, 0.20),
                (1.05, 0.10),
                (1.05, 0.30),
                (1.05, -0.10),
                (1.20, 0.10),
                (1.20, 0.30),
                (2.0, 0.20),
                (2.5, 0.35),
                (3.0, 0.20),
                (1.0, 0.00),
                (2.0, 0.00),
                (1.0, -0.20),
                (2.0, -0.20),
            )
        else:
            starts = (
                (max(self._analysis.f_init, 1e-3), 0.35),
                (max(self._analysis.f_init, 1e-3), 0.20),
                (max(self._analysis.f_init, 1e-3), 0.60),
                (1.0, 0.35),
            )

        best_state: _SpencerState | None = None
        best_sol = None
        best_norm = float("inf")
        best_any_norm = float("inf")
        best_any_min_m_alpha: float | None = None
        for start in starts:
            sol = root(
                residuals,
                np.array(start, dtype=float),
                method="hybr",
                options={"maxfev": max(200, self._analysis.max_iter * 25)},
            )
            fos = max(float(sol.x[0]), 1e-6)
            lambda_value = float(sol.x[1])

            if not sol.success:
                continue
            if lambda_value < self._LAMBDA_BOUNDS[0] or lambda_value > self._LAMBDA_BOUNDS[1]:
                continue

            try:
                state = evaluate_state(fos, lambda_value)
            except ConvergenceError:
                continue

            residual_norm = abs(state.force_residual_norm) + abs(state.moment_residual)
            if residual_norm < best_any_norm:
                best_any_norm = residual_norm
                best_any_min_m_alpha = float(np.min(state.m_alpha))

            if has_horizontal_external and np.any(state.m_alpha < self._M_ALPHA_MIN):
                continue

            if residual_norm < best_norm:
                best_norm = residual_norm
                best_state = state
                best_sol = sol

        solve_path = "two_dimensional"
        solver_evaluations = int(getattr(best_sol, "nfev", 0)) if best_sol is not None else 0
        lambda_zero_meta: dict[str, float | bool | str] = {
            "attempted": False,
            "accepted": False,
        }
        if best_state is None:
            fallback_state, fallback_evals, fallback_meta = solve_lambda_zero_fallback()
            lambda_zero_meta = fallback_meta
            solver_evaluations = max(solver_evaluations, int(fallback_evals))
            if fallback_state is None:
                raise ConvergenceError(
                    "Spencer method did not converge from deterministic 2D solve and lambda=0 fallback; "
                    f"best_2d_residual={best_any_norm if math.isfinite(best_any_norm) else 'none'}, "
                    f"best_2d_min_m_alpha={best_any_min_m_alpha if best_any_min_m_alpha is not None else 'none'}, "
                    f"lambda0_reason={fallback_meta.get('reason', 'not_attempted')}."
                )
            best_state = fallback_state
            solve_path = "lambda_zero_fallback"

        if abs(best_state.force_residual_norm) > self._analysis.tolerance:
            raise ConvergenceError(
                f"Spencer force-equilibrium residual {best_state.force_residual_norm} exceeds tolerance."
            )
        if abs(best_state.moment_residual) > self._analysis.tolerance:
            raise ConvergenceError(
                f"Spencer moment-equilibrium residual {best_state.moment_residual} exceeds tolerance."
            )

        below_threshold = best_state.m_alpha < self._M_ALPHA_MIN
        if np.any(below_threshold):
            bad_idx = int(np.flatnonzero(below_threshold)[0])
            raise ConvergenceError(
                (
                    f"Slice {int(slice_ids[bad_idx])}: final m_alpha "
                    f"({float(best_state.m_alpha[bad_idx])}) is below minimum 0.2."
                )
            )

        driving_moment = float(abs(np.sum(driving_moment_component)))
        resisting_moment = best_state.fos * driving_moment
        friction = best_state.shear_strength - best_state.cohesion_base

        history = [
            IterationState(
                iteration=1,
                fos=best_state.fos,
                delta=max(abs(best_state.force_residual_norm), abs(best_state.moment_residual)),
                numerator=float(np.sum(best_state.shear_strength)),
                denominator=best_state.denominator,
            )
        ]

        slice_results: list[SliceResult] = []
        for idx, s in enumerate(slices):
            slice_results.append(
                SliceResult(
                    slice_id=s.slice_id,
                    x_left=s.x_left,
                    x_right=s.x_right,
                    width=s.width,
                    area=s.area,
                    weight=s.weight,
                    external_force_x=s.external_force_x,
                    external_force_y=s.external_force_y,
                    external_x_app=s.external_x_app,
                    external_y_app=s.external_y_app,
                    seismic_force_x=s.seismic_force_x,
                    seismic_force_y=s.seismic_force_y,
                    pore_force=s.pore_force,
                    pore_x_app=s.pore_x_app,
                    pore_y_app=s.pore_y_app,
                    base_material_id=s.base_material_id,
                    base_cohesion=s.base_cohesion,
                    base_phi_deg=s.base_phi_deg,
                    material_weight_contributions=s.material_weight_contributions,
                    alpha_deg=math.degrees(s.alpha_rad),
                    base_length=s.base_length,
                    normal=float(best_state.normal[idx]),
                    shear_strength=float(best_state.shear_strength[idx]),
                    driving_component=float(driving_component[idx]),
                    friction_component=float(friction[idx]),
                    cohesion_component=float(best_state.cohesion_base[idx]),
                    m_alpha=float(best_state.m_alpha[idx]),
                )
            )

        return AnalysisResult(
            fos=best_state.fos,
            converged=True,
            iterations=max(1, solver_evaluations),
            residual=history[-1].delta,
            driving_moment=driving_moment,
            resisting_moment=resisting_moment,
            warnings=[],
            slice_results=slice_results,
            iteration_history=history,
            metadata={
                "spencer": {
                    "lambda": best_state.lambda_value,
                    "force_residual_norm": best_state.force_residual_norm,
                    "moment_residual": best_state.moment_residual,
                    "nfev": solver_evaluations,
                    "solve_path": solve_path,
                    "best_2d_residual": (
                        float(best_any_norm) if math.isfinite(best_any_norm) else None
                    ),
                    "best_2d_min_m_alpha": best_any_min_m_alpha,
                    "lambda_zero": lambda_zero_meta,
                }
            },
        )
