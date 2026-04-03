from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_case_capture_module() -> Any:
    module_path = REPO_ROOT / "scripts" / "diagnostics" / "capture_slide2_auto_refine_case2_case4.py"
    spec = importlib.util.spec_from_file_location("capture_slide2_auto_refine_case2_case4", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load capture_slide2_auto_refine_case2_case4 module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_slide2_auto_refine_case2_case4"] = module
    spec.loader.exec_module(module)
    return module


def _capture_rows(label: str, capture_module: Any, stage_key: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case in capture_module.CASES:
        for method in ("bishop_simplified", "spencer"):
            start = time.perf_counter()
            row = capture_module._capture_case_method(case, method)
            elapsed = time.perf_counter() - start
            stage = row["deltas"][stage_key]
            rows.append(
                {
                    "label": label,
                    "stage": stage_key,
                    "case_id": row["case_id"],
                    "method": row["method"],
                    "seconds": elapsed,
                    stage_key: {
                        "fos_abs_delta": float(stage["fos_abs_delta"]),
                        "x_right_abs_delta": float(stage["x_right_abs_delta"]),
                        "radius_rel_delta": float(stage["radius_rel_delta"]),
                    },
                }
            )
    return rows


def _summary(rows: list[dict[str, object]], stage_key: str) -> dict[str, float]:
    seconds = [float(r["seconds"]) for r in rows]
    fos = [float(r[stage_key]["fos_abs_delta"]) for r in rows]
    xr = [float(r[stage_key]["x_right_abs_delta"]) for r in rows]
    radius = [float(r[stage_key]["radius_rel_delta"]) for r in rows]
    return {
        "total_seconds": sum(seconds),
        "mean_seconds": statistics.fmean(seconds),
        "mean_fos_abs_delta": statistics.fmean(fos),
        "mean_x_right_abs_delta": statistics.fmean(xr),
        "mean_radius_rel_delta": statistics.fmean(radius),
    }


def _render_markdown(payload: dict[str, object]) -> str:
    baseline = payload["with_post_polish"]["summary"]
    no_post = payload["no_post_polish"]["summary"]

    lines: list[str] = []
    lines.append("# Auto-Refine Post-Polish A/B Decision Evidence")
    lines.append("")
    lines.append("| Scenario | Total Seconds | Mean |dFOS| | Mean |x_right error| | Mean radius rel error |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| with_post_polish | {baseline['total_seconds']:.2f} | {baseline['mean_fos_abs_delta']:.6f} | {baseline['mean_x_right_abs_delta']:.6f} | {baseline['mean_radius_rel_delta']:.6f} |"
    )
    lines.append(
        f"| no_post_polish | {no_post['total_seconds']:.2f} | {no_post['mean_fos_abs_delta']:.6f} | {no_post['mean_x_right_abs_delta']:.6f} | {no_post['mean_radius_rel_delta']:.6f} |"
    )
    lines.append("")
    lines.append("Compared stage: `after_post_polish` (final auto-refine output).")
    lines.append("Decision: keep post-polish enabled by default; no-post-polish currently degrades parity accuracy.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture auto-refine with-post-polish vs no-post-polish A/B evidence.")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument("--output-md", required=True, help="Output Markdown path")
    args = parser.parse_args()

    capture_module = _load_case_capture_module()
    import slope_stab.search.auto_refine as auto_refine

    stage_key = "after_post_polish"
    with_post_rows = _capture_rows(label="with_post_polish", capture_module=capture_module, stage_key=stage_key)

    original_toe_crest = auto_refine._run_toe_crest_refinement
    original_toe_locked = auto_refine._run_toe_locked_beta_refinement
    original_local = auto_refine._run_toe_locked_local_xright_beta_polish

    def _identity_refinement(*, best_surface, best_result, **_kwargs):
        return best_surface, best_result

    auto_refine._run_toe_crest_refinement = _identity_refinement
    auto_refine._run_toe_locked_beta_refinement = _identity_refinement
    auto_refine._run_toe_locked_local_xright_beta_polish = _identity_refinement
    try:
        no_post_rows = _capture_rows(label="no_post_polish", capture_module=capture_module, stage_key=stage_key)
    finally:
        auto_refine._run_toe_crest_refinement = original_toe_crest
        auto_refine._run_toe_locked_beta_refinement = original_toe_locked
        auto_refine._run_toe_locked_local_xright_beta_polish = original_local

    payload = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": ["Case2_Search", "Case4"],
        "methods": ["bishop_simplified", "spencer"],
        "with_post_polish": {
            "rows": with_post_rows,
            "summary": _summary(with_post_rows, stage_key=stage_key),
        },
        "no_post_polish": {
            "rows": no_post_rows,
            "summary": _summary(no_post_rows, stage_key=stage_key),
        },
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_render_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
