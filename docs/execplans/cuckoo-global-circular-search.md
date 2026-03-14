# Implement Seeded Cuckoo Global Circular Search with Oracle Global-Minimum Gates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This document is maintained in accordance with `PLANS.md`.

## Purpose / Big Picture

Users can now run `search.method = "cuckoo_global_circular"` to perform seeded stochastic global circular-surface search using Bishop simplified FOS as the objective. The new method is additive and preserves existing prescribed, auto-refine, and DIRECT verification behavior. The method is tuned for global exploration and uses oracle-style bounded baseline checks to reduce local-minimum trapping risk in regression tests.

## Progress

- [x] (2026-03-14 23:xx +13:00) Added public model/interface support for `CuckooGlobalSearchInput` and `SearchInput.cuckoo_global_circular`.
- [x] (2026-03-14 23:xx +13:00) Added JSON parser support and validation for `search.method = "cuckoo_global_circular"` with defaults and explicit range checks.
- [x] (2026-03-14 23:xx +13:00) Implemented seeded cuckoo search engine in `src/slope_stab/search/cuckoo_global.py` with bounded repair, Levy variation, random replacement, abandonment/regeneration, cache, and deterministic tie-breaks.
- [x] (2026-03-14 23:xx +13:00) Wired analysis dispatch and metadata output for cuckoo mode in `src/slope_stab/analysis.py`.
- [x] (2026-03-14 23:xx +13:00) Extended built-in verification with additive cuckoo benchmark cases for Cases 2-4.
- [x] (2026-03-14 23:xx +13:00) Added cuckoo fixtures and regression coverage for benchmark gating, same-seed repeatability, and dense-grid oracle parity fixtures.
- [x] (2026-03-14 23:xx +13:00) Updated README and added `docs/cuckoo-global-explainer.md`.
- [x] (2026-03-14 23:xx +13:00) Added cuckoo SVG diagrams and corrected slip-surface exits so arc endpoints are at ground level.
- [x] (2026-03-14 23:xx +13:00) Ran required verification gate and full unittest discovery; all passed.

## Surprises & Discoveries

- Observation: Dense-grid baselines in normalized parameter space converge slowly for Case 4 relative to Case 2/3 due narrow low-FOS basin geometry.
  Evidence: `61^3` grid resolved Case 3 close to benchmark (`~0.9865`) but remained higher for Case 4 (`~1.2502`) compared to search minima near `~1.2348`.

- Observation: Cuckoo search with deterministic post-polish materially improves parity in this circular domain while preserving seeded repeatability.
  Evidence: Cuckoo benchmark verification cases for Cases 2-4 all passed under `FOS <= benchmark + 0.01`, and repeat runs produced identical metadata for fixed seed.

- Observation: SVG geometry in documentation needed explicit endpoint checks to keep slip exits on the ground profile.
  Evidence: Initial cuckoo SVG draft showed elevated right-end exits; diagrams were corrected so both entry and exit points are on ground level.

## Decision Log

- Decision: Keep the implementation additive via `search.method = "cuckoo_global_circular"` rather than replacing existing global methods.
  Rationale: Maintain non-regression and existing diagnostic/verification paths.
  Date/Author: 2026-03-14 / Codex

- Decision: Support parser defaults for cuckoo settings while still validating all constraints.
  Rationale: Enables concise fixture templates and consistent baseline behavior.
  Date/Author: 2026-03-14 / Codex

- Decision: Use one-sided oracle gate (`FOS(method) <= FOS(dense_grid_oracle) + margin`) for oracle fixtures.
  Rationale: Dense grid is an empirical bounded baseline; one-sided gate avoids false failures when stochastic search plus local polish beats coarse-grid baseline.
  Date/Author: 2026-03-14 / Codex

## Outcomes & Retrospective

The repository now supports seeded cuckoo global circular search end-to-end:

- public input schema and parser support,
- core search implementation,
- analysis dispatch and metadata diagnostics,
- built-in verification integration,
- dedicated regression tests for benchmark and oracle parity,
- updated user-facing documentation.

All required validation gates succeeded:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Remaining caveat: cuckoo remains a stochastic finite-budget method and does not provide a theorem-level finite-iteration global-optimality guarantee on this discontinuous objective; verification therefore relies on benchmark/oracle empirical gates.

Plan revision note: Updated to implementation-complete status on 2026-03-14 with full gate evidence.
