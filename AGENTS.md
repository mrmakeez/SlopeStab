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
- Homogeneous Mohr-Coulomb soil
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
- Multi-soil zoning/internal boundaries
- Surcharge loads
- Seismic loading
- Groundwater/pore-pressure model

## Non-Negotiable Rules
- Verification-first always: do not add new feature paths until baseline verification remains passing.
- Do not alter Case 1/Case 2 benchmark targets or tolerances without explicit approval and documented rationale.
- Preserve deterministic numerical behavior for existing verification paths.
- Where possible code shall be written to be extensible to Future Roadmap items, such that they are easier to implement at a later date.
- Runtime dependencies for optimization paths are required (no fallback paths): `numpy`, `scipy`, and `cma`.
- Do not commit runtime cache artifacts (`__pycache__/`, `*.pyc`).
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
2. `python -m unittest discover -s tests -p "test_*.py"`

Expected:
- Verification suite reports all cases passed.
- Unit/integration/regression tests pass.
- Built-in `cli verify` includes Bishop and Spencer verification coverage:
  - Bishop: Case 1, Case 2, Case 3, Case 4, plus Cases 2-4 global benchmark checks for `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`.
  - Spencer: prescribed benchmarks for Cases 2-4, auto-refine parity for Cases 3-4, and Cases 2-4 global benchmark checks for `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`.
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
- Layered/zoned soils
- Loads/seismic/groundwater

Any roadmap implementation must be additive and must not alter baseline prescribed Bishop/Spencer outputs.
