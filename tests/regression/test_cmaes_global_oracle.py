from __future__ import annotations

import json
import math
import pathlib
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import load_project_input


ORACLE_FIXTURES = (
    "case2_cmaes_oracle.json",
    "case3_cmaes_oracle.json",
)


class CmaesGlobalOracleRegressionTests(unittest.TestCase):
    def test_oracle_fos_parity_and_seed_repeatability(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        fixtures_dir = root / "tests" / "fixtures"

        for fixture_name in ORACLE_FIXTURES:
            with self.subTest(fixture=fixture_name):
                raw = json.loads((fixtures_dir / fixture_name).read_text(encoding="utf-8"))
                oracle = raw["oracle"]
                project = load_project_input(fixtures_dir / fixture_name)

                result1 = run_analysis(project)
                result2 = run_analysis(project)

                self.assertLessEqual(abs(result1.fos - result2.fos), 1e-4)
                surf1 = result1.metadata["prescribed_surface"]
                surf2 = result2.metadata["prescribed_surface"]
                for key in ("x_left", "y_left", "x_right", "y_right"):
                    self.assertLessEqual(abs(float(surf1[key]) - float(surf2[key])), 0.05)

                threshold = float(oracle["benchmark_fos"]) + float(oracle["margin"])
                self.assertLessEqual(
                    result1.fos,
                    threshold,
                    msg=(
                        f"{fixture_name}: fos={result1.fos:.12f} exceeds oracle threshold "
                        f"{threshold:.12f} (benchmark={oracle['benchmark_fos']}, margin={oracle['margin']})"
                    ),
                )

                expected_surface = oracle["benchmark_surface"]
                actual_surface = result1.metadata["prescribed_surface"]
                endpoint_tol = float(oracle["endpoint_abs_tolerance"])
                for key in ("x_left", "y_left", "x_right", "y_right"):
                    self.assertTrue(math.isfinite(float(actual_surface[key])))
                    self.assertLessEqual(abs(float(actual_surface[key]) - float(expected_surface[key])), endpoint_tol)


if __name__ == "__main__":
    unittest.main()
