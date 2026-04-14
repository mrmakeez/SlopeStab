# AGENTS.md

## Purpose
This repository is a verification-first slope stability program.
Primary goal: preserve correctness of Bishop simplified and Spencer calculations for prescribed circular surfaces while supporting circular search via:
- `search.method = auto_refine_circular`
- `search.method = direct_global_circular`
- `search.method = cuckoo_global_circular`
- `search.method = cmaes_global_circular`

## Current Baseline (Do Not Regress)
Supported:
- 2D plane-strain, unit thickness
- Uniform slope geometry with infinite flat toe/crest extent
- Uniform and non-uniform Mohr-Coulomb soils via `soils.materials`, `material_boundaries`, and `region_assignments`
- Uniform surcharge loading on crest region (`loads.uniform_surcharge` with `crest_infinite` or `crest_range`)
- Groundwater loading via `loads.groundwater`:
  - `model = water_surfaces` with `hu.mode = custom|auto`
  - `model = ru_coefficient` with `0 <= ru <= 1`
- Circular slip surface input (prescribed geometry)
- Deterministic circular critical-surface search via `search.method = auto_refine_circular`
- Deterministic DIRECT-based circular global search via `search.method = direct_global_circular`
- Seeded stochastic cuckoo-based circular global search via `search.method = cuckoo_global_circular` (repeatable for fixed seed)
- Seeded stochastic hybrid CMA-ES circular global search via `search.method = cmaes_global_circular` (repeatable for fixed seed)
- Bishop simplified factor-of-safety solver
- Spencer factor-of-safety solver
- Vertical slice discretization
- JSON CLI analysis + built-in verification suite

Not supported in baseline:
- Additional/alternative search algorithms beyond current auto-refine, direct-global, cuckoo-global, and CMAES-global circular search (grid, random, GA, etc.)
- Non-circular surfaces

## Non-Negotiable Rules
- Verification-first always: do not add new feature paths until baseline verification remains passing.
- Do not alter Case 1/Case 2 benchmark targets or tolerances without explicit approval and documented rationale.
- Preserve deterministic numerical behavior for existing verification paths.
- Where possible code shall be written to be extensible to Future Roadmap items, such that they are easier to implement at a later date.
- Runtime dependencies for optimization paths are required (no fallback paths): `numpy`, `scipy`, and `cma`.
- Do not commit runtime cache artifacts (`__pycache__/`, `*.pyc`).
- Search parallel execution resolves through `search.parallel.mode` with default `auto` (`serial` and `parallel` remain explicit overrides).
- Legacy `search.parallel.enabled` is removed; inputs must use `search.parallel.mode`.
- Auto-mode resolution must remain deterministic and policy-table driven (no runtime calibration/probing).
- Worker resolution must remain deterministic: use effective CPU availability, clamp explicit requests to available workers, and resolve `workers=0` to `min(4, available)`.
- In auto mode, thread backend remains serial-by-default unless an explicit thread whitelist entry exists (v1 whitelist is intentionally empty).
- `cli test` defaults to auto-parallel unittest scheduling (`requested_mode=auto_parallel`, `requested_workers=0`).
- `cli test --serial` is the canonical serial unittest debug path and is mutually exclusive with `--workers`.
- `cli verify` defaults to auto-parallel case scheduling (`requested_mode=auto_parallel`, `requested_workers=0`).
- `cli verify --serial` is the canonical serial debug path and is mutually exclusive with `--workers`.
- Verification execution metadata must be emitted in CLI output (`requested_mode`, `resolved_mode`, `decision_reason`, `backend`, `requested_workers`, `resolved_workers`, `evidence_version`).
- Parallel candidate evaluation must preserve deterministic ordered-merge semantics:
  - normalize candidates in input order
  - cache lookup before evaluation-budget accounting
  - budget-cap uncached evaluations deterministically
  - apply cache/counter/incumbent updates in the same logical order as serial evaluation
- Batching classification must remain centralized and deterministic (`default_batching` vs `restricted_batching`) and shared by resolver, metadata, and tests.
- Worker failures (startup error, timeout, invalid payload, runtime exception) must fail deterministically via explicit error paths; never silently continue with partial state.
- Windows sandbox guidance: if process-pool startup is blocked by sandbox restrictions (for example `PermissionError` / `WinError 5`), the agent must explicitly prompt the user to approve rerunning required commands outside sandbox/full-access before continuing.
- Before running long verification commands where process-parallel behavior is relevant (for example `python -m slope_stab.cli verify` or `python -m slope_stab.cli test`), the agent must run a quick environment-appropriate process-pool preflight check first; if preflight indicates restriction, prompt for outside-sandbox/full-access **before** starting the long run.
- Agent orchestration timeout policy for long gate commands:
  - `cli verify`: use `timeout_ms = 1_200_000` (20 minutes) minimum.
  - `cli test`: use `timeout_ms = 2_700_000` (45 minutes) minimum.
  - Never execute `cli verify` and `cli test` in the same parallel tool call; run sequentially with independent timeouts.
  - If a stage times out, rerun that stage once with a larger timeout budget before treating it as a real failure.
  - When invoking CLI stages directly, pass `--output` and preserve stage JSON artifacts for post-timeout diagnostics.
- Preferred guarded gate command for agents:
  - `python scripts/benchmarks/run_guarded_gate.py`
  - This enforces preflight-first execution, sequential stage order, standardized timeouts, timeout retry-once behavior, and stage runtime artifacts under `tmp/gate_guarded/`.
- Runtime observability policy:
  - Periodically capture baseline runs with `python scripts/benchmarks/capture_gate_baseline.py`.
  - Track rolling p95 wall times with `python scripts/benchmarks/summarize_gate_p95.py --input-root tmp/gate_baselines --window 20`.
  - If p95 drifts upward, update timeout budgets and investigate runtime regressions before changing solver logic.
- GitHub publishing/review methodology (plugin-enabled):
  - Prefer the GitHub app connector for repository/PR/issue metadata, PR creation, labels, and review context.
  - For full local publish flow (branch/stage/commit/push/open PR), use the `GitHub:yeet` workflow; keep local `git` as source-of-truth for workspace changes.
  - For actionable review feedback loops, use `GitHub:gh-address-comments`.
  - For failing GitHub Actions checks and CI triage, use `GitHub:gh-fix-ci` (with `gh` for Actions log inspection when needed).
  - Use `gh` CLI as fallback for connector gaps (auth checks, current-branch PR discovery, cross-repo/fork PR edge cases, and Actions logs).
  - Default to draft PR creation unless explicitly asked to open a ready-for-review PR.
- Keep units consistent: metric (kN, m, kPa).
- Keep coordinate/sign conventions consistent:
  - x positive right
  - y positive up
  - angles in radians internally; degrees at interfaces

## Geometry and Solver Conventions
- Ground profile is piecewise:
  - toe flat: y = y_toe for x <= x_toe
  - slope segment: y = y_toe + (H/L) * (x - x_toe)
  - crest flat: y = y_toe + H for x >= x_toe + L
- Circular base ordinate uses the lower arc branch for failure base.
- Slice base angle is from base chord endpoints.
- Slice area/weight are boundary-consistent with current implementation.
- Bishop iteration must enforce finite-term checks and convergence limits.
- Spencer force/moment coupling iteration must enforce finite-term checks and convergence limits.
- Slip surfaces are invalid if any slice has final-iteration `m_alpha < 0.2` (applies to the converged/final iteration only).
- Base tension induced negative shear strength contributions are clamped to zero in solver resistance calculations.

## Required Verification Gate
Before merging any change, run:
1. `python -m slope_stab.cli verify`
2. `python -m slope_stab.cli test`

Expected:
- Verification suite reports all cases passed.
- Unit/integration/regression tests pass.
- Built-in `cli verify` includes Bishop and Spencer verification coverage:
  - Bishop: Case 1, Case 2, Case 3, Case 4, Case 5 (Water Surfaces Hu=1), Case 5 (Water Surfaces Hu=Auto), Case 6 (Ru Coefficient), Case 7 (Ponded Water Hu=Auto), Case 8 (Ponded Water Hu=Auto), plus Cases 2-4 global benchmark checks for `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`.
  - Spencer: prescribed benchmarks for Cases 2-8 (including Case 5 Hu=1/Hu=Auto, Case 6 Ru, and Cases 7-8 ponded water Hu=Auto), auto-refine parity for Cases 3-4, and Cases 2-4 global benchmark checks for `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`.
  - Surcharge benchmark policy: Case 3 surcharge 50 kPa prescribed benchmarks (Bishop + Spencer) are included in `cli verify`.
  - Case 3 surcharge 100 kPa remains a non-verify stress regression in unittest (`tests/regression/test_surcharge_case3.py`).
  - Global benchmark rule remains `FOS(method) <= FOS(benchmark) + 0.01`.
- Dedicated Case 3/4 regression tests remain for parity-focused diagnostics (`tests/regression/test_case3_auto_refine.py`, `tests/regression/test_case4_auto_refine.py`).
- Dedicated global benchmark regression test remains for direct-global diagnostics (`tests/regression/test_global_search_benchmark.py`).
- Dedicated cuckoo benchmark and oracle regression tests remain (`tests/regression/test_cuckoo_global_search_benchmark.py`, `tests/regression/test_cuckoo_global_oracle.py`).
- Dedicated CMAES benchmark and oracle regression tests remain (`tests/regression/test_cmaes_global_search_benchmark.py`, `tests/regression/test_cmaes_global_oracle.py`).
- Dedicated Spencer regression coverage remains for prescribed, benchmark, and oracle diagnostics (`tests/regression/test_spencer_*`).

## Implementation Guidance for Agents
- Keep module boundaries clean:
  - geometry
  - materials
  - surfaces
  - slicing
  - lem_core
  - search
  - io
  - verification
- Avoid solver lock-in in shared data models.
- Expose diagnostics that help reconcile per-slice terms and iteration history.
- Prefer explicit validation errors over silent fallback behavior.
- Keep deterministic behavior for deterministic paths and fixed-seed repeatability for cuckoo paths; do not alter Case 1/Case 2 benchmark behavior.
- For seeded stochastic paths (cuckoo/CMAES), random proposal generation and population state updates must remain deterministic in serial order even when candidate scoring is batched.
- In v1 load handling, `weight` remains soil self-weight; surcharge contribution is represented as `external_force_y` and consumed through total vertical force terms.
- In v1 groundwater handling, `slice.pore_force` stores base-normal pore resultant `U`; Bishop resistance paths consume its vertical projection (`U * cos(alpha)`), and Spencer uses effective-base coupling (`T = cL + (N-U)tan(phi)`).
- Keep global-search core logic centralized:
  - candidate objective/caching behavior belongs in shared search-core utilities
  - DIRECT partition selection/splitting behavior belongs in shared search-core utilities
  - avoid duplicating these primitives across `direct_global.py`, `cuckoo_global.py`, and `cmaes_global.py`

## Change Policy
When proposing extensions, sequence strictly:
1. Baseline Bishop prescribed-surface integrity maintained.
2. Add interfaces/abstractions first.
3. Add new method/feature behind isolated paths.
4. Add tests + regression fixtures.
5. Re-run full verification gate.

## ExecPlans
When writing complex features or significant refactors, use an ExecPlan (as described in `PLANS.md`) from design to implementation.

## Future Roadmap (Deferred)
Deferred until explicitly approved:
- Additional/alternative search algorithms (beyond current auto-refine, direct-global, cuckoo-global, and CMAES-global circular search)
- Non-circular surfaces
- Advanced load models beyond v1 uniform surcharge
- Advanced seismic models beyond horizontal pseudo-static loading
- Advanced groundwater models beyond v1 `water_surfaces` and `ru_coefficient`

Any roadmap implementation must be additive and must not alter baseline prescribed Bishop/Spencer outputs.
