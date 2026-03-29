from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


ROOT = _repo_root()


def _iso_timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id_from_timestamp(ts_utc: str) -> str:
    return ts_utc.replace("-", "").replace(":", "").replace("T", "T").replace("Z", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _git_head() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _git_is_dirty() -> bool | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return bool(completed.stdout.strip())


def _compose_pythonpath() -> str:
    src = str((ROOT / "src").resolve())
    existing = os.environ.get("PYTHONPATH", "")
    if not existing:
        return src
    parts: list[str] = [src]
    for entry in existing.split(os.pathsep):
        if entry and entry not in parts:
            parts.append(entry)
    return os.pathsep.join(parts)


def _run_cli_command(
    *,
    label: str,
    argv: list[str],
    env: dict[str, str],
    run_dir: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = round(time.perf_counter() - started, 3)

    stdout_path = run_dir / f"{label}_stdout.txt"
    stderr_path = run_dir / f"{label}_stderr.txt"
    _write_text(stdout_path, completed.stdout)
    _write_text(stderr_path, completed.stderr)

    parse_error: str | None = None
    payload_path: Path | None = None
    all_passed: bool | None = None
    parsed_payload: dict[str, Any] | None = None
    execution_summary: dict[str, Any] | None = None
    try:
        parsed = json.loads(completed.stdout)
        if isinstance(parsed, dict):
            parsed_payload = parsed
            payload_path = run_dir / f"{label}.json"
            _write_json(payload_path, parsed)
            ap = parsed.get("all_passed")
            all_passed = bool(ap) if isinstance(ap, bool) else None
            execution = parsed.get("execution")
            if isinstance(execution, dict):
                execution_summary = {
                    "requested_mode": execution.get("requested_mode"),
                    "resolved_mode": execution.get("resolved_mode"),
                    "decision_reason": execution.get("decision_reason"),
                    "backend": execution.get("backend"),
                    "requested_workers": execution.get("requested_workers"),
                    "resolved_workers": execution.get("resolved_workers"),
                }
        else:
            parse_error = "stdout JSON root is not an object."
    except json.JSONDecodeError as exc:
        parse_error = f"{exc.__class__.__name__}: {exc}"

    return {
        "label": label,
        "argv": argv,
        "returncode": completed.returncode,
        "seconds": elapsed,
        "all_passed": all_passed,
        "json_parse_error": parse_error,
        "stdout_file": _rel(stdout_path),
        "stderr_file": _rel(stderr_path),
        "stdout_sha256": _sha256(stdout_path),
        "stderr_sha256": _sha256(stderr_path),
        "payload_file": _rel(payload_path) if payload_path is not None else None,
        "payload_sha256": _sha256(payload_path) if payload_path is not None else None,
        "payload_keys": sorted(parsed_payload.keys()) if parsed_payload is not None else None,
        "execution": execution_summary,
    }


def _build_verify_argv(serial: bool, workers: int | None) -> list[str]:
    argv = [sys.executable, "-m", "slope_stab.cli", "verify"]
    if serial:
        argv.append("--serial")
    elif workers is not None:
        argv.extend(["--workers", str(workers)])
    return argv


def _build_test_argv(
    *,
    serial: bool,
    workers: int | None,
    start_directory: str,
    pattern: str,
    top_level_directory: str | None,
) -> list[str]:
    argv = [sys.executable, "-m", "slope_stab.cli", "test"]
    if serial:
        argv.append("--serial")
    elif workers is not None:
        argv.extend(["--workers", str(workers)])
    argv.extend(["--start-directory", start_directory, "--pattern", pattern])
    if top_level_directory is not None:
        argv.extend(["--top-level-directory", top_level_directory])
    return argv


def _normalize_optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def _executed_run_passed(stage: dict[str, Any]) -> bool:
    return (
        int(stage.get("returncode", -1)) == 0
        and stage.get("all_passed") is True
        and stage.get("json_parse_error") is None
    )


def _stage_is_process_parallel(stage: dict[str, Any]) -> bool:
    execution = stage.get("execution")
    if not isinstance(execution, dict):
        return False
    return (
        execution.get("backend") == "process"
        and execution.get("resolved_mode") == "parallel"
        and int(execution.get("resolved_workers", 0) or 0) > 1
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a paired verify/test gate baseline with a single run_id and "
            "a manifest that records command metadata, checksums, and pass/fail status."
        )
    )
    parser.add_argument(
        "--output-root",
        default="tmp/gate_baselines",
        help="Directory (relative to repo root) where run artifacts are written.",
    )
    parser.add_argument("--skip-verify", action="store_true", help="Do not run `cli verify`.")
    parser.add_argument("--skip-test", action="store_true", help="Do not run `cli test`.")
    parser.add_argument("--serial", action="store_true", help="Run both verify and test in serial mode.")
    parser.add_argument("--verify-workers", type=int, default=None, help="Workers for verify when not serial.")
    parser.add_argument("--test-workers", type=int, default=None, help="Workers for test when not serial.")
    parser.add_argument(
        "--test-start-directory",
        default="tests",
        help="Test discovery start directory passed to `cli test`.",
    )
    parser.add_argument(
        "--test-pattern",
        default="test_*.py",
        help="Test discovery pattern passed to `cli test`.",
    )
    parser.add_argument(
        "--test-top-level-directory",
        default=None,
        help="Optional top-level directory passed to `cli test`.",
    )
    parser.add_argument(
        "--require-process-parallel",
        action="store_true",
        help=(
            "Require each executed stage to resolve process-parallel "
            "(backend=process, resolved_mode=parallel, resolved_workers>1)."
        ),
    )
    args = parser.parse_args()

    if args.skip_verify and args.skip_test:
        raise ValueError("At least one of verify/test must run (cannot skip both).")
    if args.verify_workers is not None and args.verify_workers < 0:
        raise ValueError("--verify-workers must be greater than or equal to zero.")
    if args.test_workers is not None and args.test_workers < 0:
        raise ValueError("--test-workers must be greater than or equal to zero.")

    ts_utc = _iso_timestamp_utc()
    run_id = _run_id_from_timestamp(ts_utc)
    output_root = (ROOT / args.output_root).resolve()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = _compose_pythonpath()

    stages: dict[str, dict[str, Any]] = {}

    if not args.skip_verify:
        verify_argv = _build_verify_argv(serial=args.serial, workers=args.verify_workers)
        stages["verify"] = _run_cli_command(
            label="verify",
            argv=verify_argv,
            env=env,
            run_dir=run_dir,
        )

    if not args.skip_test:
        normalized_start = _normalize_optional_path(args.test_start_directory)
        assert normalized_start is not None
        normalized_top = _normalize_optional_path(args.test_top_level_directory)
        test_argv = _build_test_argv(
            serial=args.serial,
            workers=args.test_workers,
            start_directory=normalized_start,
            pattern=args.test_pattern,
            top_level_directory=normalized_top,
        )
        stages["test"] = _run_cli_command(
            label="test",
            argv=test_argv,
            env=env,
            run_dir=run_dir,
        )

    executed_stage_names = [name for name in ("verify", "test") if name in stages]
    overall_passed = all(_executed_run_passed(stages[name]) for name in executed_stage_names)
    parallel_requirements_met = all(_stage_is_process_parallel(stages[name]) for name in executed_stage_names)
    if args.require_process_parallel and not parallel_requirements_met:
        overall_passed = False

    manifest = {
        "schema_version": "gate-baseline-v1",
        "run_id": run_id,
        "generated_at_utc": ts_utc,
        "overall_passed": overall_passed,
        "executed_stages": executed_stage_names,
        "parallel_requirements": {
            "require_process_parallel": bool(args.require_process_parallel),
            "met_for_all_executed_stages": parallel_requirements_met,
        },
        "environment": {
            "repo_root": str(ROOT),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "os_cpu_count": os.cpu_count(),
            "pythonpath": env["PYTHONPATH"],
            "git_head": _git_head(),
            "git_dirty": _git_is_dirty(),
        },
        "stages": stages,
    }

    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    latest = {
        "schema_version": "gate-baseline-latest-pointer-v1",
        "run_id": run_id,
        "manifest_file": _rel(manifest_path),
        "generated_at_utc": ts_utc,
        "overall_passed": overall_passed,
    }
    latest_path = output_root / "latest.json"
    _write_json(latest_path, latest)

    print(json.dumps(manifest, indent=2))
    return 0 if overall_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
