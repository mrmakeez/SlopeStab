from __future__ import annotations

import argparse
import json
import sys

from slope_stab.analysis import run_analysis
from slope_stab.io.json_io import dump_result_json, load_project_input
from slope_stab.verification.runner import run_verification_suite


def _cmd_analyze(args: argparse.Namespace) -> int:
    project = load_project_input(args.input)
    result = run_analysis(project)
    text = dump_result_json(result, path=args.output, pretty=not args.compact)
    if args.output is None:
        print(text)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    outcomes = run_verification_suite(workers=max(1, int(args.workers)))
    all_passed = all(o.passed for o in outcomes)

    summary = {
        "all_passed": all_passed,
        "cases": [
            {
                "name": o.name,
                "case_type": o.case_type,
                "analysis_method": o.analysis_method,
                "passed": o.passed,
                "solver": {
                    "fos": o.result.fos,
                    "driving_moment": o.result.driving_moment,
                    "resisting_moment": o.result.resisting_moment,
                    "iterations": o.result.iterations,
                    "residual": o.result.residual,
                    "converged": o.result.converged,
                },
                "hard_checks": o.hard_checks,
                "diagnostics": o.diagnostics,
            }
            for o in outcomes
        ],
    }

    text = json.dumps(summary, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0 if all_passed else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Slope stability (Bishop simplified + Spencer)")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Run prescribed-surface or search analysis from JSON input")
    analyze.add_argument("--input", required=True, help="Path to input JSON")
    analyze.add_argument("--output", help="Optional output JSON path")
    analyze.add_argument("--compact", action="store_true", help="Emit compact JSON")
    analyze.set_defaults(func=_cmd_analyze)

    verify = sub.add_parser("verify", help="Run built-in verification cases")
    verify.add_argument("--output", help="Optional output JSON path")
    verify.add_argument("--workers", type=int, default=1, help="Number of parallel verification workers")
    verify.set_defaults(func=_cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
