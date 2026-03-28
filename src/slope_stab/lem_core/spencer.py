from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import root

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
        material: MohrCoulombMaterial,
        analysis: AnalysisInput,
        surface: CircularSlipSurface,
    ) -> None:
        self._material = material
        self._analysis = analysis
        self._surface = surface

    def _compute_state(
        self,
        f_k: float,
        lambda_value: float,
        weights: np.ndarray,
        external_force_x: np.ndarray,
        horizontal_coupling_scale: float,
        pore_forces: np.ndarray,
        sin_a: np.ndarray,
        cos_a: np.ndarray,
        tan_phi: float,
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
            + (horizontal_coupling_scale * external_force_x * b_term)
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
        tan_phi = self._material.tan_phi
        cohesion = self._material.cohesion

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

        cohesion_base = cohesion * base_lengths
        scale_force = max(float(np.sum(np.abs(weights))), 1.0)

        def evaluate_state(
            fos: float,
            lambda_value: float,
            horizontal_coupling_scale: float,
        ) -> _SpencerState:
            return self._compute_state(
                f_k=fos,
                lambda_value=lambda_value,
                weights=weights,
                external_force_x=external_force_x,
                horizontal_coupling_scale=horizontal_coupling_scale,
                pore_forces=pore_forces,
                sin_a=sin_a,
                cos_a=cos_a,
                tan_phi=tan_phi,
                cohesion_base=cohesion_base,
                denominator=denominator,
                scale_force=scale_force,
            )

        def residuals(vec: np.ndarray, horizontal_coupling_scale: float) -> np.ndarray:
            fos = max(float(vec[0]), 1e-6)
            lambda_value = float(vec[1])
            try:
                state = evaluate_state(fos, lambda_value, horizontal_coupling_scale)
            except ConvergenceError:
                return np.array([1e6, 1e6], dtype=float)
            return np.array([state.force_residual_norm, state.moment_residual], dtype=float)

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
            horizontal_scales = (1.0, 0.5, 0.0)
        else:
            starts = (
                (max(self._analysis.f_init, 1e-3), 0.35),
                (max(self._analysis.f_init, 1e-3), 0.20),
                (max(self._analysis.f_init, 1e-3), 0.60),
                (1.0, 0.35),
            )
            horizontal_scales = (0.0,)

        best_state: _SpencerState | None = None
        best_sol = None
        best_norm = float("inf")
        for horizontal_coupling_scale in horizontal_scales:
            for start in starts:
                sol = root(
                    lambda vec: residuals(vec, horizontal_coupling_scale),
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
                    state = evaluate_state(fos, lambda_value, horizontal_coupling_scale)
                except ConvergenceError:
                    continue
                if has_horizontal_external and np.any(state.m_alpha < self._M_ALPHA_MIN):
                    continue

                residual_norm = abs(state.force_residual_norm) + abs(state.moment_residual)
                if residual_norm < best_norm:
                    best_norm = residual_norm
                    best_state = state
                    best_sol = sol

        if best_state is None or best_sol is None:
            raise ConvergenceError("Spencer method did not converge from deterministic starting points.")

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
                    pore_force=s.pore_force,
                    pore_x_app=s.pore_x_app,
                    pore_y_app=s.pore_y_app,
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
            iterations=max(1, int(getattr(best_sol, "nfev", 1))),
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
                    "nfev": int(getattr(best_sol, "nfev", 0)),
                }
            },
        )
