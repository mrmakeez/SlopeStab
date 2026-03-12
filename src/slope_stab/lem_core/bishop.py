from __future__ import annotations

import math

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

        for iteration in range(1, self._analysis.max_iter + 1):
            numerator = 0.0
            denominator = 0.0

            for s in slices:
                sin_a = math.sin(s.alpha_rad)
                cos_a = math.cos(s.alpha_rad)
                if abs(cos_a) < 1e-10:
                    warnings.append(f"Slice {s.slice_id}: cos(alpha) is very small ({cos_a}).")

                m_alpha = cos_a + (sin_a * tan_phi) / f_k
                if abs(m_alpha) < 1e-12:
                    raise ConvergenceError(
                        f"Slice {s.slice_id}: m_alpha approaches zero at iteration {iteration}."
                    )

                normal = (s.weight - (cohesion * s.base_length * sin_a) / f_k) / m_alpha
                numerator += cohesion * s.base_length + normal * tan_phi

                x_mid = 0.5 * (s.x_left + s.x_right)
                denominator += s.weight * ((x_mid - self._surface.xc) / self._surface.r)

            if abs(denominator) < 1e-12:
                raise ConvergenceError("Driving denominator is numerically zero.")

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

        slice_results: list[SliceResult] = []
        driving_moment = 0.0

        for s in slices:
            sin_a = math.sin(s.alpha_rad)
            cos_a = math.cos(s.alpha_rad)
            m_alpha = cos_a + (sin_a * tan_phi) / f_k
            normal = (s.weight - (cohesion * s.base_length * sin_a) / f_k) / m_alpha

            friction = normal * tan_phi
            cohesion_component = cohesion * s.base_length
            shear_strength = cohesion_component + friction

            x_mid = 0.5 * (s.x_left + s.x_right)
            driving_component = s.weight * ((x_mid - self._surface.xc) / self._surface.r)
            driving_moment += s.weight * (x_mid - self._surface.xc)

            slice_results.append(
                SliceResult(
                    slice_id=s.slice_id,
                    x_left=s.x_left,
                    x_right=s.x_right,
                    width=s.width,
                    area=s.area,
                    weight=s.weight,
                    alpha_deg=math.degrees(s.alpha_rad),
                    base_length=s.base_length,
                    normal=normal,
                    shear_strength=shear_strength,
                    driving_component=driving_component,
                    friction_component=friction,
                    cohesion_component=cohesion_component,
                    m_alpha=m_alpha,
                )
            )

        resisting_moment = f_k * driving_moment

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
