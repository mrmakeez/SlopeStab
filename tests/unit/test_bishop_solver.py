from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.exceptions import ConvergenceError
from slope_stab.models import AnalysisInput, ProjectInput
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


if __name__ == "__main__":
    unittest.main()
