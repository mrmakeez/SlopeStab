# SlopeStab

Verification-first slope stability program supporting Bishop simplified and Spencer methods.

## Runtime Dependencies

- Python `>=3.11`
- `numpy`
- `scipy`
- `cma` (pycma)

The `cmaes_global_circular` path requires `scipy` and `cma`; fallback implementations are intentionally not provided.

## Quick Start

1. `python -m slope_stab.cli analyze --input tests/fixtures/case1.json`
2. `python -m slope_stab.cli verify` (default auto-parallel case scheduling)
3. `python -m slope_stab.cli test` (default auto-parallel unittest scheduling)

## Canonical Gate Baseline Capture

Use a single run-id bundle for verification/test evidence to avoid mismatched snapshots:

1. `python scripts/benchmarks/capture_gate_baseline.py`
2. Read the latest pointer: `tmp/gate_baselines/latest.json`
3. Open the corresponding run manifest: `tmp/gate_baselines/<run_id>/manifest.json`

Each run bundle stores paired `verify` and `test` stdout/stderr files, parsed JSON payload files, checksums, and an `overall_passed` status in one manifest.

To force and enforce process-parallel execution in both stages:

- `python scripts/benchmarks/capture_gate_baseline.py --verify-workers 4 --test-workers 4 --require-process-parallel`

## Guarded Gate Runner (Timeout-Safe)

For agent and CI-like local runs where orchestration timeouts have caused false failures, use:

- `python scripts/benchmarks/run_guarded_gate.py`

Default behavior:

- Runs process-pool preflight first.
- Runs `cli verify` then `cli test` sequentially (never in parallel).
- Uses standardized stage timeouts (`verify=20 min`, `test=45 min`).
- Retries a timed-out stage once with a larger timeout.
- Persists stage JSON/stdout/stderr artifacts under `tmp/gate_guarded/<run_id>/`.

You can tune timeout policy for constrained environments:

- `python scripts/benchmarks/run_guarded_gate.py --verify-timeout-ms 1500000 --test-timeout-ms 3000000`

## Rolling p95 Wall-Time Observability

To track drift in gate wall times from baseline capture artifacts:

1. Run baseline captures periodically:
   - `python scripts/benchmarks/capture_gate_baseline.py`
2. Summarize rolling p95 over the latest N runs:
   - `python scripts/benchmarks/summarize_gate_p95.py --input-root tmp/gate_baselines --window 20`

If rolling p95 drifts upward materially, raise orchestration timeout budgets first and investigate runtime hot spots before changing solver behavior.

## Documentation

- Auto-refine algorithm explainer (beginner-friendly, with step-by-step SVG diagrams and formulas): `docs/auto-refine-explainer.md`
- DIRECT global algorithm explainer (implementation-accurate): `docs/direct-global-explainer.md`
- Cuckoo global algorithm explainer (seeded stochastic global search): `docs/cuckoo-global-explainer.md`
- CMAES global algorithm explainer (hybrid DIRECT + CMA-ES + polish): `docs/cmaes-global-explainer.md`
- Spencer solver explainer (force and moment equilibrium with lambda coupling): `docs/spencer-explainer.md`
- Uniform surcharge v1 explainer: `docs/surcharge-explainer.md`
- Groundwater v1 explainer (Water Surfaces + Ru Coefficient): `docs/groundwater-explainer.md`

## GitHub Plugin Workflow (Codex)

When using Codex with the GitHub plugin enabled, repository publishing and review operations should follow a connector-first hybrid model:

- Keep local `git` as source-of-truth for edits, staging, commits, and pushes.
- Prefer the GitHub app connector for PR/issue metadata, PR creation, labels, reactions, and review context.
- Use plugin specialist workflows when applicable:
  - `GitHub:yeet` for publish flow (branch/stage/commit/push/draft PR).
  - `GitHub:gh-address-comments` for addressing actionable PR review feedback.
  - `GitHub:gh-fix-ci` for failing checks and CI debugging workflows.
- Use `gh` CLI as fallback when connector coverage is insufficient (auth status/login, current-branch PR discovery, cross-repo/fork PR edge cases, GitHub Actions logs).
- Default to draft PRs unless the user explicitly requests a ready-for-review PR.

## Analysis Methods

- `analysis.method = bishop_simplified` for Bishop simplified LEM solving.
- `analysis.method = spencer` for Spencer LEM solving.
- Both methods are supported for prescribed surfaces and all circular search methods.

## Loads (v1)

`loads` is optional. When omitted, baseline no-load behavior is unchanged.

Supported in v1:

- `loads.uniform_surcharge` with:
  - `magnitude_kpa >= 0`
  - `placement = crest_infinite` (covers crest for `x >= crest_x`)
  - `placement = crest_range` with explicit `x_start/x_end` constrained to crest (`x >= crest_x`)
- `loads.groundwater` with:
  - `model = water_surfaces`
  - required `surface = [[x, y], ...]` (strictly increasing `x`, at least two points)
  - required `hu.mode = custom|auto`
  - `hu.value` required when `hu.mode = custom` (`0 <= hu.value <= 1`)
  - optional `gamma_w` (defaults to `9.81`)
  - `model = ru_coefficient` with required `ru` (`0 <= ru <= 1`)

Reserved interfaces (v2-ready stubs in v1):

- `loads.seismic.model` supports only `"none"` in v1.

Example:

```json
{
  "loads": {
    "uniform_surcharge": {
      "magnitude_kpa": 10.0,
      "placement": "crest_infinite"
    },
    "seismic": { "model": "none" },
    "groundwater": {
      "model": "water_surfaces",
      "surface": [[0.0, 15.0], [18.0, 15.0], [30.0, 23.0], [48.0, 29.0], [66.0, 32.0]],
      "hu": { "mode": "auto" },
      "gamma_w": 9.81
    }
  }
}
```

## Search Methods

- `search.method = auto_refine_circular` for deterministic Slide2-style narrowing search.
- `search.method = direct_global_circular` for deterministic DIRECT-style global search.
- `search.method = cuckoo_global_circular` for seeded stochastic Cuckoo global search with deterministic repeatability per seed.
- `search.method = cmaes_global_circular` for seeded hybrid DIRECT prescan + CMA-ES + Nelder-Mead polish.
- Input settings and output diagnostics for each method are documented in the explainer files above.

## Search Architecture

- Shared circular geometry and candidate validity rules: `src/slope_stab/search/common.py`
- Shared objective/caching/evaluation counters for global methods: `src/slope_stab/search/objective_evaluator.py`
- Shared DIRECT partition primitive used by DIRECT and CMAES prescan: `src/slope_stab/search/direct_partition.py`
- Shared deterministic post-polish config for global methods: `src/slope_stab/search/post_polish.py`

This keeps the method-specific files focused on their search strategy while preserving consistent scoring, tie-break, and invalid-candidate behavior.

## Parallel Execution (Default `auto` Mode)

Search execution mode is configured through `search.parallel.mode`:

- `auto` (default): deterministic resolver chooses serial vs parallel using static in-code policy evidence.
- `serial`: force serial candidate evaluation.
- `parallel`: force parallel candidate evaluation (still deterministic ordered-merge semantics).

Supported config fields:

- `search.parallel.mode` (`auto|serial|parallel`, default `auto`)
- `search.parallel.workers` (int, default `0`)
- `search.parallel.min_batch_size` (int, default `1`)
- `search.parallel.timeout_seconds` (optional float)

Worker rules:

- `workers = 0` resolves deterministically to `min(4, effective_cpu_count)`.
- explicit `workers >= 1` is clamped to available workers.
- if resolved workers are `<= 1`, execution resolves serial.

Backward compatibility:

- `search.parallel.enabled = false` maps to `mode = serial`.
- `search.parallel.enabled = true` maps to `mode = parallel`.
- conflicting `enabled` and `mode` values are rejected.

Thread backend posture:

- auto mode is process-policy-first.
- if a thread backend is used, auto mode resolves serial unless an explicit thread whitelist entry exists (v1 whitelist is intentionally empty).
- explicit `mode = parallel` remains parallel on both process and thread backends.

The implementation preserves ordered deterministic merge semantics for cache/budget/incumbent updates. Worker failures raise explicit runtime errors; silent partial continuation is not allowed.

`analyze` CLI overrides:

- `--parallel-mode auto|serial|parallel`
- `--parallel-workers <int>` (`0` allowed)

Override precedence is `CLI > JSON > defaults`.

Parallel decision metadata is emitted at `result.metadata.search.parallel` with:

- `requested_mode`, `resolved_mode`, `decision_reason`, `evidence_version`
- `backend`, `requested_workers`, `resolved_workers`
- `workload_class`, `batching_class`, `min_batch_size`, `timeout_seconds`

## Performance and Repeatability Notes

- Deterministic paths (`auto_refine_circular`, `direct_global_circular`) remain deterministic.
- Seeded stochastic paths (`cuckoo_global_circular`, `cmaes_global_circular`) remain repeatable for fixed seeds.
- Surcharge benchmark policy: Case 3 surcharge 50 kPa is the primary benchmark in `cli verify` (Bishop + Spencer); Case 3 surcharge 100 kPa remains a non-verify stress regression in unittest.
- `cli test` defaults to auto-parallel unittest scheduling with deterministic worker resolution (`workers=0 => min(4, effective_cpu_count)`).
- `cli test --serial` is the canonical serial unittest debugging path.
- `cli test --workers N` sets explicit requested unittest workers in auto-parallel mode (`N=0` is allowed).
- `cli test --serial` cannot be combined with `--workers`.
- `cli verify` defaults to auto-parallel case scheduling with deterministic worker resolution (`workers=0 => min(4, effective_cpu_count)`).
- `cli verify --serial` is the canonical serial debugging path.
- `cli verify --workers N` sets explicit requested workers in auto-parallel mode (`N=0` is allowed).
- `cli verify --serial` cannot be combined with `--workers`.
- Verify output includes top-level `execution` metadata with `requested_mode`, `resolved_mode`, `decision_reason`, `backend`, `requested_workers`, `resolved_workers`, and `evidence_version`.
- Case ordering in verify output remains deterministic and follows built-in verification case definition order.
- Non-gating auto-mode evidence can be captured with `python scripts/benchmarks/auto_mode_matrix.py` (latest captured artifact: `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json`).

## Solver Validity Rules

- Any converged slip surface with final-iteration `m_alpha < 0.2` in any slice is treated as invalid.
- Base tension induced negative slice shear strength is clamped to zero.
