from __future__ import annotations

import math
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.lem_core.bishop import BishopSimplifiedSolver
from slope_stab.materials.mohr_coulomb import MohrCoulombMaterial
from slope_stab.analysis import run_analysis
from slope_stab.exceptions import ConvergenceError
from slope_stab.models import AnalysisInput, ProjectInput, SliceGeometry
from slope_stab.surfaces.circular import CircularSlipSurface
from slope_stab.verification.cases import VERIFICATION_CASES


class BishopSolverTests(unittest.TestCase):
    def test_case2_solver_matches_expected_fos(self) -> None:
        case2 = next(c for c in VERIFICATION_CASES if c.name == "Case 2")
        result = run_analysis(case2.project)
        self.assertTrue(result.converged)
        self.assertLess(abs(result.fos - case2.expected_fos), case2.fos_tolerance)

    def test_solver_raises_on_forced_non_convergence(self) -> None:
        case2 = next(c for c in VERIFICATION_CASES if c.name == "Case 2")
        project = ProjectInput(
            units=case2.project.units,
            geometry=case2.project.geometry,
            material=case2.project.material,
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=case2.project.analysis.n_slices,
                tolerance=1e-12,
                max_iter=1,
                f_init=1.0,
            ),
            prescribed_surface=case2.project.prescribed_surface,
        )
        with self.assertRaises(ConvergenceError):
            run_analysis(project)

    def test_final_m_alpha_gate_is_not_applied_to_initial_iteration(self) -> None:
        analysis = AnalysisInput(
            method="bishop_simplified",
            n_slices=2,
            tolerance=1e-4,
            max_iter=200,
            f_init=100000.0,
        )
        material = MohrCoulombMaterial(gamma=20.0, cohesion=0.45855419909180406, phi_deg=16.015800666147523)
        surface = CircularSlipSurface(xc=0.0, yc=100.0, r=33.14160570750562)
        slices = [
            SliceGeometry(
                slice_id=1,
                x_left=2.0,
                x_right=4.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=279.6292816196179,
                alpha_rad=1.390804808137109,
                base_length=4.534997848239748,
            ),
            SliceGeometry(
                slice_id=2,
                x_left=4.0,
                x_right=6.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=389.00939509244745,
                alpha_rad=1.3886294125707297,
                base_length=7.307633338188034,
            ),
        ]

        tan_phi = material.tan_phi
        initial_m_alpha_min = min(
            math.cos(s.alpha_rad) + (math.sin(s.alpha_rad) * tan_phi) / analysis.f_init for s in slices
        )
        self.assertLess(initial_m_alpha_min, 0.2)

        result = BishopSimplifiedSolver(material=material, analysis=analysis, surface=surface).solve(slices)
        self.assertTrue(result.converged)
        self.assertGreaterEqual(min(s.m_alpha for s in result.slice_results), 0.2)

    def test_solver_rejects_surface_when_final_m_alpha_below_threshold(self) -> None:
        analysis = AnalysisInput(
            method="bishop_simplified",
            n_slices=2,
            tolerance=1e-5,
            max_iter=200,
            f_init=1.0,
        )
        material = MohrCoulombMaterial(gamma=20.0, cohesion=4.237168684686163, phi_deg=7.015463661686018)
        surface = CircularSlipSurface(xc=0.0, yc=200.0, r=96.3774618976614)
        slices = [
            SliceGeometry(
                slice_id=1,
                x_left=2.0,
                x_right=4.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=162.37276619718455,
                alpha_rad=1.4381102681941302,
                base_length=2.4718083778387827,
            ),
            SliceGeometry(
                slice_id=2,
                x_left=4.0,
                x_right=6.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=212.89824318069074,
                alpha_rad=1.4775449524922604,
                base_length=0.7346489669355872,
            ),
        ]

        with self.assertRaisesRegex(ConvergenceError, "below minimum 0.2"):
            BishopSimplifiedSolver(material=material, analysis=analysis, surface=surface).solve(slices)

    def test_solver_clamps_negative_shear_strength_to_zero(self) -> None:
        analysis = AnalysisInput(
            method="bishop_simplified",
            n_slices=2,
            tolerance=1e-5,
            max_iter=200,
            f_init=1.0,
        )
        material = MohrCoulombMaterial(gamma=20.0, cohesion=3.0949810269214737, phi_deg=19.72096179474869)
        surface = CircularSlipSurface(xc=0.0, yc=100.0, r=43.763494556640865)
        slices = [
            SliceGeometry(
                slice_id=1,
                x_left=2.0,
                x_right=4.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=-121.6897521754104,
                alpha_rad=-0.24087479540709256,
                base_length=6.60316646047066,
            ),
            SliceGeometry(
                slice_id=2,
                x_left=4.0,
                x_right=6.0,
                y_top_left=0.0,
                y_top_right=0.0,
                y_base_left=0.0,
                y_base_right=0.0,
                width=2.0,
                area=2.0,
                weight=279.4887607719297,
                alpha_rad=-0.30262955352334997,
                base_length=6.356138217538069,
            ),
        ]

        result = BishopSimplifiedSolver(material=material, analysis=analysis, surface=surface).solve(slices)
        self.assertTrue(result.converged)
        self.assertTrue(all(s.shear_strength >= 0.0 for s in result.slice_results))

        raw_shear = [
            (material.cohesion * s.base_length) + (s.normal * material.tan_phi)
            for s in result.slice_results
        ]
        self.assertTrue(any(value < 0.0 for value in raw_shear))
        self.assertTrue(any(abs(s.shear_strength) <= 1e-12 for s in result.slice_results))


if __name__ == "__main__":
    unittest.main()
