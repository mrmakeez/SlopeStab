from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest


def _load_module(module_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location("extract_case11_case12_manifest", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Case11Case12ManifestTests(unittest.TestCase):
    def test_committed_manifest_matches_fresh_extraction(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        module = _load_module(root / "scripts" / "diagnostics" / "extract_case11_case12_manifest.py")
        committed = json.loads(
            (root / "src" / "slope_stab" / "verification" / "data" / "case11_case12_slide2_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        fresh = module.build_manifest()
        self.assertEqual(fresh, committed)

    def test_manifest_source_agreement_passes_for_all_methods(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[2]
        committed = json.loads(
            (root / "src" / "slope_stab" / "verification" / "data" / "case11_case12_slide2_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for scenario in committed["scenarios"].values():
            for method in scenario["methods"].values():
                self.assertTrue(method["agreement"]["pass_fos_1e6"])
                self.assertLessEqual(method["agreement"]["fos_abs_delta"], 1e-6)


if __name__ == "__main__":
    unittest.main()
