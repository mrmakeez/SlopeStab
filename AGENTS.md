# AGENTS.md

## Purpose
This repository is a verification-first slope stability program.
Primary goal: preserve correctness of Bishop simplified calculations for prescribed circular surfaces before adding search or additional physics.

## Current Baseline (Do Not Regress)
Supported:
- 2D plane-strain, unit thickness
- Uniform slope geometry with infinite flat toe/crest extent
- Homogeneous Mohr-Coulomb soil
- Circular slip surface input (prescribed geometry)
- Bishop simplified factor-of-safety solver
- Vertical slice discretization
- JSON CLI analysis + built-in verification suite

Not supported in baseline:
- Critical surface search (grid, auto-refine, random, GA, etc.)
- Spencer or other rigorous methods
- Non-circular surfaces
- Multi-soil zoning/internal boundaries
- Surcharge loads
- Seismic loading
- Groundwater/pore-pressure model

## Non-Negotiable Rules
- Verification-first always: do not add new feature paths until baseline verification remains passing.
- Do not alter Case 1/Case 2 benchmark targets or tolerances without explicit approval and documented rationale.
- Preserve deterministic numerical behavior for existing verification paths.
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

## Required Verification Gate
Before merging any change, run:
1. `python -m slope_stab.cli verify`
2. `python -m unittest discover -s tests -p "test_*.py"`

Expected:
- Verification suite reports all cases passed.
- Unit/integration/regression tests pass.

## Implementation Guidance for Agents
- Keep module boundaries clean:
  - geometry
  - materials
  - surfaces
  - slicing
  - lem_core
  - io
  - verification
- Avoid solver lock-in in shared data models.
- Expose diagnostics that help reconcile per-slice terms and iteration history.
- Prefer explicit validation errors over silent fallback behavior.

## Change Policy
When proposing extensions, sequence strictly:
1. Baseline Bishop prescribed-surface integrity maintained.
2. Add interfaces/abstractions first.
3. Add new method/feature behind isolated paths.
4. Add tests + regression fixtures.
5. Re-run full verification gate.

## Future Roadmap (Deferred)
Deferred until explicitly approved:
- Search algorithms
- Spencer integration
- Non-circular surfaces
- Layered/zoned soils
- Loads/seismic/groundwater

Any roadmap implementation must be additive and must not alter baseline prescribed Bishop outputs.
