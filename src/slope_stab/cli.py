from __future__ import annotations

import argparse
from dataclasses import asdict
import errno
import json
import os
from pathlib import Path
import sys

from slope_stab.analysis import run_analysis
from slope_stab.errors.contracts import (
    ERROR_CODE_RUNTIME_WORKER,
    ERROR_CODE_STARTUP_BACKEND,
    ERROR_CODE_VALIDATION,
    STAGE_RUNTIME,
    STAGE_STARTUP,
    STAGE_VALIDATION,
    error_payload,
)
from slope_stab.io.json_io import dump_result_json, load_project_input
from slope_stab.testing import (
    TEST_MODE_AUTO_PARALLEL,
    TEST_MODE_SERIAL,
    run_unittest_suite_with_execution,
)
from slope_stab.verification.runner import (
    VERIFY_MODE_AUTO_PARALLEL,
    VERIFY_MODE_SERIAL,
    run_verification_suite_with_execution,
)

_DEVNULL_STDOUT = None


def _is_closed_stdout_error(exc: OSError) -> bool:
    if isinstance(exc, BrokenPipeError):
        return True
    if exc.errno in {errno.EPIPE, errno.EINVAL, errno.EBADF}:
        return True
    return getattr(exc, "winerror", None) in {109, 232}


def _redirect_stdout_to_devnull() -> None:
    global _DEVNULL_STDOUT
    # Avoid interpreter-shutdown flush noise after downstream stdout is closed.
    if _DEVNULL_STDOUT is None or _DEVNULL_STDOUT.closed:
        _DEVNULL_STDOUT = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = _DEVNULL_STDOUT


def _emit_stdout_text(text: str) -> bool:
    try:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        sys.stdout.flush()
    except OSError as exc:
        if _is_closed_stdout_error(exc):
            _redirect_stdout_to_devnull()
            return False
        raise
    return True


def _emit_failure_summary(*, code: str, message: str, stage: str, exit_code: int) -> int:
    summary = {
        "all_passed": False,
        "error": error_payload(code=code, message=message, stage=stage),
    }
    _emit_stdout_text(json.dumps(summary, indent=2))
    return exit_code


def _cmd_analyze(args: argparse.Namespace) -> int:
    project = load_project_input(args.input)
    forced_mode: str | None = args.parallel_mode
    forced_workers: int | None = args.parallel_workers
    if forced_workers is not None and forced_workers < 0:
        raise ValueError("--parallel-workers must be greater than or equal to zero.")

    result = run_analysis(project, forced_parallel_mode=forced_mode, forced_parallel_workers=forced_workers)
    text = dump_result_json(result, path=args.output, pretty=not args.compact)
    if args.output is None:
        _emit_stdout_text(text)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    if args.serial:
        requested_mode = VERIFY_MODE_SERIAL
        requested_workers = 1
    else:
        requested_mode = VERIFY_MODE_AUTO_PARALLEL
        requested_workers = 0 if args.workers is None else int(args.workers)

    if requested_workers < 0:
        return _emit_failure_summary(
            code=ERROR_CODE_VALIDATION,
            message="--workers must be greater than or equal to zero.",
            stage=STAGE_VALIDATION,
            exit_code=2,
        )

    try:
        run_result = run_verification_suite_with_execution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
        )
    except RuntimeError as exc:
        return _emit_failure_summary(
            code=ERROR_CODE_RUNTIME_WORKER,
            message=str(exc),
            stage=STAGE_RUNTIME,
            exit_code=2,
        )
    except (OSError, PermissionError) as exc:
        return _emit_failure_summary(
            code=ERROR_CODE_STARTUP_BACKEND,
            message=str(exc),
            stage=STAGE_STARTUP,
            exit_code=2,
        )
    outcomes = run_result.outcomes
    all_passed = run_result.error is None and all(o.passed for o in outcomes)

    summary = {
        "all_passed": all_passed,
        "error": run_result.error,
        "execution": asdict(run_result.execution),
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
    if not _emit_stdout_text(text):
        return 0
    return 0 if all_passed else 2


def _cmd_test(args: argparse.Namespace) -> int:
    if args.serial:
        requested_mode = TEST_MODE_SERIAL
        requested_workers = 1
    else:
        requested_mode = TEST_MODE_AUTO_PARALLEL
        requested_workers = 0 if args.workers is None else int(args.workers)

    if requested_workers < 0:
        return _emit_failure_summary(
            code=ERROR_CODE_VALIDATION,
            message="--workers must be greater than or equal to zero.",
            stage=STAGE_VALIDATION,
            exit_code=1,
        )

    try:
        run_result = run_unittest_suite_with_execution(
            requested_mode=requested_mode,
            requested_workers=requested_workers,
            start_directory=args.start_directory,
            pattern=args.pattern,
            top_level_directory=args.top_level_directory,
        )
    except RuntimeError as exc:
        return _emit_failure_summary(
            code=ERROR_CODE_RUNTIME_WORKER,
            message=str(exc),
            stage=STAGE_RUNTIME,
            exit_code=1,
        )
    except (OSError, PermissionError) as exc:
        return _emit_failure_summary(
            code=ERROR_CODE_STARTUP_BACKEND,
            message=str(exc),
            stage=STAGE_STARTUP,
            exit_code=1,
        )
    summary = {
        "all_passed": run_result.all_passed,
        "error": run_result.error,
        "execution": asdict(run_result.execution),
        "discovery": {
            "start_directory": run_result.start_directory,
            "pattern": run_result.pattern,
            "top_level_directory": run_result.top_level_directory,
            "error": run_result.discovery_error,
        },
        "targets": [asdict(item) for item in run_result.targets],
    }

    text = json.dumps(summary, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    if not _emit_stdout_text(text):
        return 0
    return 0 if run_result.all_passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Slope stability (Bishop simplified + Spencer)")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Run prescribed-surface or search analysis from JSON input")
    analyze.add_argument("--input", required=True, help="Path to input JSON")
    analyze.add_argument("--output", help="Optional output JSON path")
    analyze.add_argument("--parallel-mode", choices=["auto", "serial", "parallel"], help="Override search parallel mode")
    analyze.add_argument("--parallel-workers", type=int, help="Override parallel workers (0 = auto)")
    analyze.add_argument("--compact", action="store_true", help="Emit compact JSON")
    analyze.set_defaults(func=_cmd_analyze)

    verify = sub.add_parser("verify", help="Run built-in verification cases")
    verify.add_argument("--output", help="Optional output JSON path")
    verify_mode = verify.add_mutually_exclusive_group()
    verify_mode.add_argument(
        "--serial",
        action="store_true",
        help="Run verification in serial mode (canonical debug path)",
    )
    verify_mode.add_argument(
        "--workers",
        type=int,
        help="Requested verification workers (0 = auto; default is auto)",
    )
    verify.set_defaults(func=_cmd_verify)

    test = sub.add_parser("test", help="Run unittest discovery (default auto-parallel scheduling)")
    test.add_argument("--output", help="Optional output JSON path")
    test_mode = test.add_mutually_exclusive_group()
    test_mode.add_argument(
        "--serial",
        action="store_true",
        help="Run unittests in serial mode (canonical debug path)",
    )
    test_mode.add_argument(
        "--workers",
        type=int,
        help="Requested unittest workers (0 = auto; default is auto)",
    )
    test.add_argument(
        "--start-directory",
        default="tests",
        help="Directory to start unittest discovery from",
    )
    test.add_argument(
        "--pattern",
        default="test_*.py",
        help="Pattern to match unittest files",
    )
    test.add_argument(
        "--top-level-directory",
        default=str(Path(__file__).resolve().parents[2]),
        help="Top-level directory used for unittest discovery/import resolution",
    )
    test.set_defaults(func=_cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
