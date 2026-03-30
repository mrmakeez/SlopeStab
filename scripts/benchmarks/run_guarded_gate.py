from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Any


DEFAULT_VERIFY_TIMEOUT_MS = 1_200_000
DEFAULT_TEST_TIMEOUT_MS = 2_700_000
DEFAULT_RETRY_TIMEOUT_SCALE = 1.5


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


ROOT = _repo_root()


def _iso_timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id_from_timestamp(ts_utc: str) -> str:
    return ts_utc.replace("-", "").replace(":", "").replace("T", "T").replace("Z", "Z")


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


def _is_wsl() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    release = platform.release().lower()
    version = platform.version().lower()
    return "microsoft" in release or "microsoft" in version


def _pool_probe_task(value: int) -> int:
    return value * value


def _run_process_pool_preflight(force_fork_start_method: bool) -> dict[str, Any]:
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "ok": False,
        "context": "default",
        "elapsed_seconds": None,
    }
    try:
        kwargs: dict[str, Any] = {"max_workers": 2}
        if force_fork_start_method:
            kwargs["mp_context"] = mp.get_context("fork")
            payload["context"] = "fork"
        with ProcessPoolExecutor(**kwargs) as executor:
            result = list(executor.map(_pool_probe_task, [2, 3]))
        payload["ok"] = True
        payload["result"] = result
    except Exception as exc:  # pragma: no cover - diagnostics path
        payload["error_type"] = type(exc).__name__
        payload["error_message"] = str(exc)
    payload["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return payload


def _build_verify_cli_args(serial: bool, workers: int | None, output_path: Path) -> list[str]:
    args = ["verify"]
    if serial:
        args.append("--serial")
    elif workers is not None:
        args.extend(["--workers", str(workers)])
    args.extend(["--output", str(output_path)])
    return args


def _build_test_cli_args(
    *,
    serial: bool,
    workers: int | None,
    output_path: Path,
    start_directory: str,
    pattern: str,
    top_level_directory: str | None,
) -> list[str]:
    args = ["test"]
    if serial:
        args.append("--serial")
    elif workers is not None:
        args.extend(["--workers", str(workers)])
    args.extend(
        [
            "--output",
            str(output_path),
            "--start-directory",
            start_directory,
            "--pattern",
            pattern,
        ]
    )
    if top_level_directory is not None:
        args.extend(["--top-level-directory", top_level_directory])
    return args


def _build_stage_argv(cli_args: list[str], force_fork_start_method: bool) -> list[str]:
    if not force_fork_start_method:
        return [sys.executable, "-m", "slope_stab.cli", *cli_args]
    runner = (
        "import multiprocessing as mp; "
        "mp.set_start_method('fork', force=True); "
        "from slope_stab.cli import main; "
        f"raise SystemExit(main({cli_args!r}))"
    )
    return [sys.executable, "-c", runner]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _normalize_optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def _next_timeout_ms(current_timeout_ms: int, retry_scale: float) -> int:
    return max(current_timeout_ms + 1, int(round(current_timeout_ms * retry_scale)))


def _read_all_passed(output_path: Path) -> tuple[bool | None, str | None]:
    if not output_path.exists():
        return None, "output_file_missing"
    try:
        parsed = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{exc.__class__.__name__}: {exc}"
    if not isinstance(parsed, dict):
        return None, "output_json_root_not_object"
    all_passed = parsed.get("all_passed")
    if isinstance(all_passed, bool):
        return all_passed, None
    return None, "output_all_passed_missing_or_non_bool"


def _run_stage(
    *,
    name: str,
    cli_args: list[str],
    env: dict[str, str],
    run_dir: Path,
    timeout_ms: int,
    retry_timeout_scale: float,
    force_fork_start_method: bool,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    current_timeout_ms = timeout_ms
    output_path = Path(cli_args[cli_args.index("--output") + 1])
    stage_started_at = _iso_timestamp_utc()

    for attempt_index in (1, 2):
        attempt_started = time.perf_counter()
        attempt_started_utc = _iso_timestamp_utc()
        argv = _build_stage_argv(cli_args, force_fork_start_method=force_fork_start_method)
        timed_out = False
        returncode: int | None
        stdout_text = ""
        stderr_text = ""
        timeout_error_message: str | None = None
        try:
            completed = subprocess.run(
                argv,
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=current_timeout_ms / 1000.0,
            )
            returncode = int(completed.returncode)
            stdout_text = completed.stdout
            stderr_text = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = None
            timeout_error_message = str(exc)
            if isinstance(exc.stdout, str):
                stdout_text = exc.stdout
            elif isinstance(exc.stdout, bytes):
                stdout_text = exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, str):
                stderr_text = exc.stderr
            elif isinstance(exc.stderr, bytes):
                stderr_text = exc.stderr.decode("utf-8", errors="replace")

        elapsed_seconds = round(time.perf_counter() - attempt_started, 3)
        attempt_finished_utc = _iso_timestamp_utc()

        stdout_file = run_dir / f"{name}_attempt{attempt_index}_stdout.txt"
        stderr_file = run_dir / f"{name}_attempt{attempt_index}_stderr.txt"
        _write_text(stdout_file, stdout_text)
        _write_text(stderr_file, stderr_text)

        attempt_payload = {
            "attempt": attempt_index,
            "argv": argv,
            "timeout_ms": current_timeout_ms,
            "timed_out": timed_out,
            "timeout_error": timeout_error_message,
            "returncode": returncode,
            "started_at_utc": attempt_started_utc,
            "finished_at_utc": attempt_finished_utc,
            "seconds": elapsed_seconds,
            "stdout_file": str(stdout_file.relative_to(ROOT).as_posix()),
            "stderr_file": str(stderr_file.relative_to(ROOT).as_posix()),
        }
        attempts.append(attempt_payload)

        if not timed_out:
            break
        if attempt_index == 1:
            current_timeout_ms = _next_timeout_ms(current_timeout_ms, retry_timeout_scale)

    stage_finished_at = _iso_timestamp_utc()
    stage_seconds = round(sum(float(item["seconds"]) for item in attempts), 3)
    final_attempt = attempts[-1]
    output_all_passed, output_parse_error = _read_all_passed(output_path)
    stage_passed = (
        final_attempt["returncode"] == 0
        and final_attempt["timed_out"] is False
        and output_all_passed is True
        and output_parse_error is None
    )
    retried_after_timeout = len(attempts) == 2 and attempts[0]["timed_out"] is True

    return {
        "name": name,
        "passed": stage_passed,
        "retried_after_timeout": retried_after_timeout,
        "timeout_policy": {
            "initial_timeout_ms": timeout_ms,
            "retry_timeout_scale": retry_timeout_scale,
            "retry_timeout_ms": _next_timeout_ms(timeout_ms, retry_timeout_scale),
        },
        "started_at_utc": stage_started_at,
        "finished_at_utc": stage_finished_at,
        "seconds_total": stage_seconds,
        "output_file": str(output_path.relative_to(ROOT).as_posix()),
        "output_all_passed": output_all_passed,
        "output_parse_error": output_parse_error,
        "attempts": attempts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run guarded verify/test gate sequentially with process-pool preflight, "
            "standardized timeouts, and timeout-retry behavior."
        )
    )
    parser.add_argument("--output-root", default="tmp/gate_guarded", help="Run artifact directory root.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip `cli verify` stage.")
    parser.add_argument("--skip-test", action="store_true", help="Skip `cli test` stage.")
    parser.add_argument("--serial", action="store_true", help="Run both stages in serial mode.")
    parser.add_argument("--verify-workers", type=int, default=None, help="Workers for verify when not serial.")
    parser.add_argument("--test-workers", type=int, default=None, help="Workers for test when not serial.")
    parser.add_argument("--verify-timeout-ms", type=int, default=DEFAULT_VERIFY_TIMEOUT_MS)
    parser.add_argument("--test-timeout-ms", type=int, default=DEFAULT_TEST_TIMEOUT_MS)
    parser.add_argument("--retry-timeout-scale", type=float, default=DEFAULT_RETRY_TIMEOUT_SCALE)
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
        "--force-fork-start-method",
        action="store_true",
        help="Force fork start method for CLI commands (mainly for WSL long parallel runs).",
    )
    args = parser.parse_args()

    if args.skip_verify and args.skip_test:
        raise ValueError("At least one stage must run (cannot skip both verify and test).")
    if args.verify_workers is not None and args.verify_workers < 0:
        raise ValueError("--verify-workers must be greater than or equal to zero.")
    if args.test_workers is not None and args.test_workers < 0:
        raise ValueError("--test-workers must be greater than or equal to zero.")
    if args.verify_timeout_ms <= 0:
        raise ValueError("--verify-timeout-ms must be greater than zero.")
    if args.test_timeout_ms <= 0:
        raise ValueError("--test-timeout-ms must be greater than zero.")
    if args.retry_timeout_scale <= 1.0:
        raise ValueError("--retry-timeout-scale must be greater than 1.0.")

    auto_force_fork = _is_wsl()
    force_fork_start_method = bool(args.force_fork_start_method or auto_force_fork)

    ts_utc = _iso_timestamp_utc()
    run_id = _run_id_from_timestamp(ts_utc)
    run_dir = (ROOT / args.output_root / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = _compose_pythonpath()

    preflight = _run_process_pool_preflight(force_fork_start_method=force_fork_start_method)

    stages: dict[str, dict[str, Any]] = {}
    if preflight.get("ok"):
        if not args.skip_verify:
            verify_output = (run_dir / "verify.json").resolve()
            verify_cli_args = _build_verify_cli_args(args.serial, args.verify_workers, verify_output)
            stages["verify"] = _run_stage(
                name="verify",
                cli_args=verify_cli_args,
                env=env,
                run_dir=run_dir,
                timeout_ms=args.verify_timeout_ms,
                retry_timeout_scale=args.retry_timeout_scale,
                force_fork_start_method=force_fork_start_method,
            )

        if not args.skip_test:
            test_output = (run_dir / "test.json").resolve()
            test_start = _normalize_optional_path(args.test_start_directory)
            assert test_start is not None
            test_top = _normalize_optional_path(args.test_top_level_directory)
            test_cli_args = _build_test_cli_args(
                serial=args.serial,
                workers=args.test_workers,
                output_path=test_output,
                start_directory=test_start,
                pattern=args.test_pattern,
                top_level_directory=test_top,
            )
            stages["test"] = _run_stage(
                name="test",
                cli_args=test_cli_args,
                env=env,
                run_dir=run_dir,
                timeout_ms=args.test_timeout_ms,
                retry_timeout_scale=args.retry_timeout_scale,
                force_fork_start_method=force_fork_start_method,
            )

    executed_stage_names = [name for name in ("verify", "test") if name in stages]
    overall_passed = bool(preflight.get("ok")) and all(stages[name]["passed"] for name in executed_stage_names)

    manifest = {
        "schema_version": "guarded-gate-v1",
        "run_id": run_id,
        "generated_at_utc": ts_utc,
        "overall_passed": overall_passed,
        "sequential_policy": True,
        "executed_stages": executed_stage_names,
        "policy": {
            "verify_timeout_ms": args.verify_timeout_ms,
            "test_timeout_ms": args.test_timeout_ms,
            "retry_timeout_scale": args.retry_timeout_scale,
            "retry_once_on_timeout": True,
            "force_fork_start_method": force_fork_start_method,
            "force_fork_reason": "wsl_auto" if auto_force_fork else "explicit_or_disabled",
        },
        "environment": {
            "repo_root": str(ROOT),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "os_cpu_count": os.cpu_count(),
            "pythonpath": env["PYTHONPATH"],
        },
        "preflight": preflight,
        "stages": stages,
    }

    manifest_path = run_dir / "manifest.json"
    _write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")

    latest_path = (ROOT / args.output_root / "latest.json").resolve()
    latest_payload = {
        "schema_version": "guarded-gate-latest-pointer-v1",
        "run_id": run_id,
        "generated_at_utc": ts_utc,
        "overall_passed": overall_passed,
        "manifest_file": str(manifest_path.relative_to(ROOT).as_posix()),
    }
    _write_text(latest_path, json.dumps(latest_payload, indent=2) + "\n")

    print(json.dumps(manifest, indent=2))
    return 0 if overall_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
