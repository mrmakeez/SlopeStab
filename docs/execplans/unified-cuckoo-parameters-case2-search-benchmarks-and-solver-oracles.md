# ExecPlan: Unified Cuckoo Parameters + Case 2 Search Benchmarks + Solver-Specific Dense-Grid Oracles

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md`; this plan is maintained in accordance with it.

## Purpose / Big Picture

After this change, cuckoo search uses one consistent parameter profile everywhere: Bishop and Spencer, verification and non-verification defaults. Case 2 global benchmark checks use true Slide2 search minima (`Case2_Search`) instead of prescribed-surface-derived values. Oracle checks remain enabled and Spencer oracle metadata is solver-specific from dense-grid provenance.

## Progress

- [x] (2026-03-29 +13:00) Verified current cuckoo configs were Bishop/Spencer-matched per case but not fully aligned with runtime defaults.
- [x] (2026-03-29 +13:00) Confirmed owner preference: same cuckoo profile across verification and default behavior outside verification.
- [x] (2026-03-29 +13:00) Feasibility-tested unified profile `40/300/7000` with `discovery_rate=0.25`; benchmark/oracle dry-run checks passed.
- [x] (2026-03-29 +13:00) Implemented unified cuckoo profile in parser defaults, verification benchmark cases, and cuckoo fixtures.
- [x] (2026-03-29 +13:00) Replaced Case 2 global benchmark baselines (all global methods, Bishop + Spencer) with Slide2 `Case2_Search` values.
- [x] (2026-03-29 +13:00) Refreshed Spencer oracle metadata to solver-specific dense-grid values and kept Bishop dense-grid oracle policy.
- [x] (2026-03-29 +13:00) Added a reusable dense-grid oracle generation script for reproducible Spencer oracle updates.
- [x] (2026-03-29 +13:00) Ran targeted regressions plus full gate (`cli verify`, `cli test`) successfully.

## Surprises & Discoveries

- Observation: Oracle tests compare runtime output to frozen fixture metadata, so parameter changes can fail oracle checks unless fixture oracle metadata is updated atomically.
  Evidence: Case 2 Spencer oracle behavior shifted when `discovery_rate` changed from `0.20` to `0.25`; metadata refresh restored green checks.

- Observation: A single unified cuckoo profile can satisfy both benchmark and oracle gates for Bishop and Spencer without solver-specific forks.
  Evidence: Unified `population_size=40`, `max_iterations=300`, `max_evaluations=7000`, `discovery_rate=0.25` passed targeted cuckoo benchmark and oracle regressions for both solvers.

- Observation: Case 2 search baselines from prescribed-surface values overstated acceptable search thresholds.
  Evidence: Replacing with Slide2 `Case2_Search` (`2.10296` Bishop, `2.09717` Spencer) remained green under the existing `+0.01` benchmark margin in verify and regression checks.

## Decision Log

- Decision: Use one shared cuckoo profile for Bishop + Spencer, verification + runtime defaults.
  Rationale: Owner requested no policy split between verification and non-verification behavior.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Canonical shared profile is `population_size=40`, `max_iterations=300`, `max_evaluations=7000`, `discovery_rate=0.25`, `levy_beta=1.5`, `alpha_max=0.5`, `alpha_min=0.05`, `min_improvement=1e-4`, `stall_iterations=25`, `seed=0`, `post_polish=true`.
  Rationale: Owner-selected balance from tested options with acceptable gate reliability and runtime.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Case 2 global benchmark baselines switch to Slide2 `Case2_Search` values for all global methods: Bishop `2.10296`, Spencer `2.09717`.
  Rationale: Search benchmarks should be search-derived, not prescribed-surface-derived.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Keep oracle checks enabled, with Spencer oracle metadata made solver-specific and dense-grid-derived.
  Rationale: Shared Bishop/Spencer oracle baselines are semantically inconsistent for different objective landscapes.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Add `scripts/diagnostics/generate_dense_grid_oracle.py` to support reproducible dense-grid oracle regeneration.
  Rationale: Reduces future drift risk and makes oracle provenance updates repeatable.
  Date/Author: 2026-03-29 / Codex

## Outcomes & Retrospective

Implemented outcomes:

- Runtime defaults and explicit verification/fixture cuckoo configs are now aligned to one canonical profile across Bishop and Spencer.
- Case 2 global benchmark constants now use Slide2 `Case2_Search` values in verification registry and regression benchmark checks.
- Spencer oracle fixtures now use solver-specific dense-grid benchmarks for Case 2 and Case 3 across cuckoo and CMA-ES oracle fixtures.
- A reusable dense-grid oracle generation utility was added for future provenance refreshes.
- Full gate is green (`cli verify` and `cli test` both passed).

Remaining work:

- None for this plan scope.

Lesson learned:

- For seeded stochastic search, configuration updates and oracle metadata updates should be applied and validated as one atomic change-set to prevent false drift failures.

## Context and Orientation

The key runtime defaults are in `src/slope_stab/io/json_io.py` under `_parse_cuckoo_global_search`. Verification benchmark cases live in `src/slope_stab/verification/cases.py` and are consumed by `python -m slope_stab.cli verify`. Regression benchmark and oracle checks are in `tests/regression/test_*global_search_benchmark.py`, `tests/regression/test_parallel_search_behavior.py`, and `tests/regression/test_*oracle.py`. Oracle fixture metadata is in `tests/fixtures/*oracle*.json`. Case 2 search provenance comes from `Verification/Bishop/Case 2/Case2_Search/Case2_Search-i.rfcreport`.

In this repository, a "benchmark" gate means runtime search FOS must satisfy `FOS(method) <= FOS(benchmark) + 0.01`. An "oracle" gate means runtime search FOS must satisfy a one-sided bound against a dense-grid baseline and margin in the fixture metadata.

## Plan of Work

This implementation changed parser defaults to the canonical cuckoo profile, then updated explicit cuckoo configs in verification and fixtures so runtime and verification behavior are aligned. Next, Case 2 global benchmark constants were replaced with Slide2 search-derived minima for both solvers across verify and regression benchmark tests, with concise provenance comments near the constants. Then Spencer oracle fixture metadata was regenerated from dense-grid evaluation and applied consistently to both cuckoo and CMA-ES Spencer oracle fixtures, preserving active oracle tests. Finally, targeted regressions and full `cli verify`/`cli test` were run to confirm the gate.

## Concrete Steps

From repository root with `PYTHONPATH=src`:

- Update defaults and verification/test constants in:
  - `src/slope_stab/io/json_io.py`
  - `src/slope_stab/verification/cases.py`
  - `tests/regression/test_*global_search_benchmark.py`
  - `tests/regression/test_parallel_search_behavior.py`
  - `tests/unit/test_search_auto_refine.py`
  - `docs/cuckoo-global-explainer.md`
- Update explicit cuckoo fixture configs in all Case 2/3/4 Bishop + Spencer cuckoo fixtures.
- Regenerate Spencer dense-grid oracle metadata using:
  - `scripts/diagnostics/generate_dense_grid_oracle.py`
- Update Spencer oracle fixtures:
  - `tests/fixtures/case2_cuckoo_oracle_spencer.json`
  - `tests/fixtures/case3_cuckoo_oracle_spencer.json`
  - `tests/fixtures/case2_cmaes_oracle_spencer.json`
  - `tests/fixtures/case3_cmaes_oracle_spencer.json`
- Run targeted regressions and full gates:
  - `python -m slope_stab.cli verify`
  - `python -m slope_stab.cli test`

Observed gate outcome:

- `cli verify`: `"all_passed": true`
- `cli test`: `"all_passed": true`

## Validation and Acceptance

Acceptance criteria were validated by code inspection and test execution:

- One canonical cuckoo profile is used in parser defaults and explicit verification/fixture cuckoo configs.
- Bishop and Spencer cuckoo settings are aligned in verification and non-verification defaults.
- Case 2 global benchmark baselines are search-derived (`2.10296` Bishop, `2.09717` Spencer) for direct/cuckoo/CMA-ES benchmark checks.
- Oracle regressions remain enabled and pass with solver-specific Spencer dense-grid metadata.
- Full verify/test gate passes.

## Idempotence and Recovery

The changes are deterministic config/test/fixture updates and are safe to reapply. If a future oracle drift appears, rerun dense-grid oracle generation for the affected fixture and rerun paired oracle regressions before rerunning full `cli verify` and `cli test`. Keep config and oracle metadata updates in the same change-set to avoid transient red gates.

## Artifacts and Notes

Key solver-specific Spencer dense-grid oracle values applied:

- Case 2 Spencer dense-grid benchmark FOS: `2.0879000710096505`
- Case 3 Spencer dense-grid benchmark FOS: `0.9854122834550322`

These values were applied to both Spencer cuckoo and Spencer CMA-ES oracle fixtures for the corresponding cases.

## Interfaces and Dependencies

No new runtime dependency was introduced. Existing project dependencies (`numpy`, `scipy`, `cma`) are unchanged.

The new diagnostics helper script adds a small internal interface:

- `scripts/diagnostics/generate_dense_grid_oracle.py`
  - `generate_oracle(fixture_path: Path, *, analysis_method: str | None, resolution: int, margin: float, endpoint_abs_tolerance: float) -> DenseGridOracle`

It consumes existing search/solver utilities and emits oracle metadata for fixture updates.

Plan revision note (2026-03-29): Marked implementation complete, recorded final gate evidence (`cli verify` + `cli test` both green), and documented the added dense-grid oracle generation utility and resulting Spencer oracle provenance values.
