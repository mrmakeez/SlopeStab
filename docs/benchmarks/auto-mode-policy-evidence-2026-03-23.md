# Auto Mode Policy Evidence (2026-03-23)

This note records the benchmark evidence used to validate the default `search.parallel.mode = auto` policy.

Raw artifact:

- `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json`

Command (from repo root):

- `python scripts/benchmarks/auto_mode_matrix.py --output docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json`

Machine metadata captured in artifact:

- platform: `Windows-11-10.0.26200-SP0`
- python: `3.14.3`
- `os.cpu_count()`: `20`
- `effective_cpu_count()`: `20`
- `evidence_version`: `auto-v1`

Benchmarked fixtures:

- `tests/fixtures/case3_auto_refine.json`
- `tests/fixtures/case3_auto_refine_spencer.json`
- `tests/fixtures/case2_cmaes_global.json`
- `tests/fixtures/case2_cmaes_global_spencer.json`

Observed behavior summary:

- `auto` resolved `serial` for all measured fixtures with `decision_reason=policy_threshold_serial`.
- forced `parallel` resolved to backend `thread` in this environment.
- forced `parallel` was slower than forced `serial` on all measured fixtures.

Representative elapsed-time comparisons (seconds):

- `case3_auto_refine`: serial `4.71`, auto `4.79`, parallel `7.00`
- `case3_auto_refine_spencer`: serial `46.40`, auto `46.51`, parallel `53.97`
- `case2_cmaes_global`: serial `3.33`, auto `2.60`, parallel `3.44`
- `case2_cmaes_global_spencer`: serial `44.49`, auto `44.53`, parallel `46.92`

Policy implication:

- v1 remains conservative for `auto`: unknown/non-promoted workload classes stay serial.
- thread backend remains fallback-focused; auto mode does not promote thread parallelism by default.
- policy evidence is static and versioned (`auto-v1`), with runtime decisions deterministic from configuration and classification metadata.
