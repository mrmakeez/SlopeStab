from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


EXPECTED_FILES = {
    "case11_direct_global_bishop.json": ("direct_global_circular", "bishop_simplified"),
    "case11_cuckoo_global_bishop_seed0.json": ("cuckoo_global_circular", "bishop_simplified"),
    "case11_cmaes_global_bishop_seed1.json": ("cmaes_global_circular", "bishop_simplified"),
    "case12_water_surcharge_direct_global_spencer.json": ("direct_global_circular", "spencer"),
    "case12_water_surcharge_cuckoo_global_spencer_seed0.json": ("cuckoo_global_circular", "spencer"),
    "case12_water_surcharge_cmaes_global_spencer_seed1.json": ("cmaes_global_circular", "spencer"),
}


def _validate_output(path: Path, expected_search_method: str, expected_solver: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fos = float(payload["fos"])
    metadata = payload["metadata"]
    actual_search_method = metadata["search"]["method"]
    actual_solver = metadata["method"]
    checks = {
        "finite_fos": math.isfinite(fos),
        "positive_fos": fos > 0.0,
        "converged": bool(payload["converged"]),
        "search_method_matches": actual_search_method == expected_search_method,
        "solver_matches": actual_solver == expected_solver,
    }
    return {
        "file": path.name,
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {
            "fos": fos,
            "search_method": actual_search_method,
            "solver": actual_solver,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate committed non-uniform smoke output payloads.")
    parser.add_argument("--input-dir", required=True, help="Directory containing smoke output JSON files.")
    parser.add_argument("--output", required=True, help="Path to write the summary JSON.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    present_files = sorted(path.name for path in input_dir.glob("*.json") if path.name in EXPECTED_FILES)
    rows = []
    for filename, (expected_search_method, expected_solver) in EXPECTED_FILES.items():
        path = input_dir / filename
        if not path.exists():
            rows.append(
                {
                    "file": filename,
                    "passed": False,
                    "checks": {"file_present": False},
                    "observed": {},
                }
            )
            continue
        rows.append(_validate_output(path, expected_search_method, expected_solver))

    summary = {
        "all_passed": len(present_files) == len(EXPECTED_FILES) and all(row["passed"] for row in rows),
        "checked_outputs": len(rows),
        "present_expected_outputs": len(present_files),
        "rows": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
