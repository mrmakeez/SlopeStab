from __future__ import annotations

from collections import Counter
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.verification.cases import (
    NON_UNIFORM_SEARCH_VERIFICATION_CASES_DEFAULT,
    NON_UNIFORM_SEARCH_VERIFICATION_CASES_FULL,
    VERIFICATION_CASES,
)


class VerificationIntegrationTests(unittest.TestCase):
    def test_built_in_case_catalog_matches_expected_contract(self) -> None:
        self.assertEqual(len(NON_UNIFORM_SEARCH_VERIFICATION_CASES_FULL), 32)
        self.assertEqual(len(NON_UNIFORM_SEARCH_VERIFICATION_CASES_DEFAULT), 8)
        self.assertEqual(len(VERIFICATION_CASES), 59)
        self.assertEqual({case.analysis_method for case in VERIFICATION_CASES}, {"bishop_simplified", "spencer"})
        self.assertEqual(sum(1 for case in VERIFICATION_CASES if case.analysis_method == "bishop_simplified"), 29)
        self.assertEqual(sum(1 for case in VERIFICATION_CASES if case.analysis_method == "spencer"), 30)
        self.assertEqual(
            Counter(case.case_type for case in VERIFICATION_CASES),
            Counter(
                {
                    "prescribed_benchmark": 29,
                    "auto_refine_parity": 4,
                    "global_search_benchmark": 6,
                    "cuckoo_global_search_benchmark": 6,
                    "cmaes_global_search_benchmark": 6,
                    "non_uniform_search_benchmark": 8,
                }
            ),
        )
        names = {case.name for case in VERIFICATION_CASES}
        for required_name in (
            "Case 11 (Non-Uniform Auto-Refine Search Benchmark)",
            "Case 11 (Water Seismic Surcharge Non-Uniform Cuckoo Global Search Benchmark)",
            "Case 12 (Non-Uniform Direct Global Search Benchmark)",
            "Case 12 (Water Surcharge Non-Uniform CMAES Global Search Benchmark)",
            "Case 11 (Spencer Non-Uniform CMAES Global Search Benchmark)",
            "Case 11 (Spencer Water Seismic Surcharge Non-Uniform Direct Global Search Benchmark)",
            "Case 12 (Spencer Non-Uniform Cuckoo Global Search Benchmark)",
            "Case 12 (Spencer Water Surcharge Non-Uniform Auto-Refine Search Benchmark)",
        ):
            self.assertIn(required_name, names)


if __name__ == "__main__":
    unittest.main()
