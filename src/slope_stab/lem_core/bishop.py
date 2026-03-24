from __future__ import annotations

import math

import numpy as np

from slope_stab.exceptions import ConvergenceError
from slope_stab.lem_core.base import LEMSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.models import AnalysisInput, AnalysisResult, IterationState, SliceGeometry, SliceResult
from slope_stab.surfaces.circular import CircularSlipSurface


class BishopSimplifiedSolver(LEMSolver):
    def __init__(
        self,
        material: MohrCoulombMaterial,
        analysis: AnalysisInput,
        surface: CircularSlipSurface,
    ) -> None:
        self._material = material
        self._analysis = analysis
        self._surface = surface

    def solve(self, slices: list[SliceGeometry]) -> AnalysisResult:
        tan_phi = self._material.tan_phi
        cohesion = self._material.cohesion

        f_k = self._analysis.f_init
        history: list[IterationState] = []
        warnings: list[str] = []
        converged = False

        if f_k <= 0:
            raise ConvergenceError("Initial FOS must be greater than zero.")

        slice_ids = np.fromiter((s.slice_id for s in slices), dtype=int)
        x_left = np.fromiter((s.x_left for s in slices), dtype=float)
        x_right = np.fromiter((s.x_right for s in slices), dtype=float)
        weights = np.fromiter((s.total_vertical_force for s in slices), dtype=float)
        alpha = np.fromiter((s.alpha_rad for s in slices), dtype=float)
        base_lengths = np.fromiter((s.base_length for s in slices), dtype=float)

        sin_a = np.sin(alpha)
        cos_a = np.cos(alpha)
        small_cos_mask = np.abs(cos_a) < 1e-10
        if np.any(small_cos_mask):
            for bad_idx in np.flatnonzero(small_cos_mask):
                warnings.append(f"Slice {int(slice_ids[bad_idx])}: cos(alpha) is very small ({float(cos_a[bad_idx])}).")

        x_mid = 0.5 * (x_left + x_right)
        x_offset = x_mid - self._surface.xc
        driving_component = weights * (x_offset / self._surface.r)
        denominator = float(np.sum(driving_component))
        if abs(denominator) < 1e-12:
            raise ConvergenceError("Driving denominator is numerically zero.")

        cohesion_base = cohesion * base_lengths
        cohesion_base_sin = cohesion_base * sin_a

        for iteration in range(1, self._analysis.max_iter + 1):
            m_alpha = cos_a + (sin_a * tan_phi) / f_k
            near_zero = np.abs(m_alpha) < 1e-12
            if np.any(near_zero):
                bad_idx = int(np.flatnonzero(near_zero)[0])
                raise ConvergenceError(
                    f"Slice {int(slice_ids[bad_idx])}: m_alpha approaches zero at iteration {iteration}."
                )

            normal = (weights - (cohesion_base_sin / f_k)) / m_alpha
            friction_raw = normal * tan_phi
            shear_strength_raw = cohesion_base + friction_raw
            shear_strength = np.maximum(shear_strength_raw, 0.0)
            numerator = float(np.sum(shear_strength))

            f_next = numerator / denominator
            if not math.isfinite(f_next):
                raise ConvergenceError("Non-finite FOS encountered during Bishop iteration.")

            delta = abs(f_next - f_k)
            history.append(
                IterationState(
                    iteration=iteration,
                    fos=f_next,
                    delta=delta,
                    numerator=numerator,
                    denominator=denominator,
                )
            )

            f_k = f_next
            if delta <= self._analysis.tolerance:
                converged = True
                break

        if not converged:
            raise ConvergenceError(
                f"Bishop simplified did not converge in {self._analysis.max_iter} iterations."
            )

        m_alpha = cos_a + (sin_a * tan_phi) / f_k
        below_threshold = m_alpha < 0.2
        if np.any(below_threshold):
            bad_idx = int(np.flatnonzero(below_threshold)[0])
            raise ConvergenceError(
                (
                    f"Slice {int(slice_ids[bad_idx])}: final m_alpha "
                    f"({float(m_alpha[bad_idx])}) is below minimum 0.2."
                )
            )

        normal = (weights - (cohesion_base_sin / f_k)) / m_alpha
        friction_raw = normal * tan_phi
        shear_strength_raw = cohesion_base + friction_raw
        shear_strength = np.maximum(shear_strength_raw, 0.0)
        friction = shear_strength - cohesion_base

        driving_moment = float(np.sum(weights * x_offset))
        resisting_moment = f_k * driving_moment

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
                    normal=float(normal[idx]),
                    shear_strength=float(shear_strength[idx]),
                    driving_component=float(driving_component[idx]),
                    friction_component=float(friction[idx]),
                    cohesion_component=float(cohesion_base[idx]),
                    m_alpha=float(m_alpha[idx]),
                )
            )

        return AnalysisResult(
            fos=f_k,
            converged=True,
            iterations=len(history),
            residual=history[-1].delta,
            driving_moment=driving_moment,
            resisting_moment=resisting_moment,
            warnings=warnings,
            slice_results=slice_results,
            iteration_history=history,
        )
