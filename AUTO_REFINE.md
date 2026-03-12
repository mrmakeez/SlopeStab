# AUTO_REFINE

This document defines the current auto-refine circular search algorithm and the extension path toward Spencer and non-circular surfaces.

## Current Scope

- Method: Bishop simplified only.
- Surface type: circular only.
- Soil model: homogeneous Mohr-Coulomb only.
- Loading: dry only (`u = 0`, no surcharge/seismic/water effects).
- Search style: auto-refine only (no coarse grid fallback, no random restarts).

## Default Parameters

- `divisions = 20`
- `circles_per_pair = 10`
- `iterations = 10`
- `retain_ratio = 0.5`
- `toe_extension_h = 1.0`
- `crest_extension_h = 2.0`
- `min_span_h = 0.10`
- `radius_max_h = 10.0`
- `seed = 42`

## Parameter Definitions

- `divisions`: number of x-bins over the search domain.
- `circles_per_pair`: number of candidate circles sampled per bin-pair per iteration.
- `iterations`: number of refine loops.
- `retain_ratio`: fraction of best valid candidates retained each iteration.
- `toe_extension_h`: search distance left of toe, in units of slope height `H`.
- `crest_extension_h`: search distance right of crest, in units of slope height `H`.
- `min_span_h`: minimum allowed endpoint span `(x_right - x_left)`, in units of `H`.
- `radius_max_h`: maximum radius cap scale in units of `H`.
- `seed`: RNG seed for deterministic reproducibility.

## Exact Algorithm Steps

1. Build search domain:
- `x_min = x_toe - toe_extension_h * H`
- `x_max = x_toe + L + crest_extension_h * H`

2. Partition `[x_min, x_max]` into `divisions` equal bins.

3. Build initial bin-pairs `(i, j)` for all `i < j`.
- Count is `divisions * (divisions - 1) / 2`.

4. For each iteration:
- For each active pair `(i, j)`, generate `circles_per_pair` candidates.
- Sample endpoints:
  - `x_left ~ U(bin_i)`
  - `x_right ~ U(bin_j)`
  - reject if `x_right <= x_left` or `(x_right - x_left) < min_span_h * H`
- Set endpoint elevations:
  - `y_left = y_ground(x_left)`
  - `y_right = y_ground(x_right)`
- Compute chord length `c`.
- Radius bounds:
  - `r_min = 0.5 * c * (1 + 1e-6)`
  - `r_max = max(radius_max_h * H, 1.05 * r_min)`
  - sample `r ~ U(r_min, r_max)`
- Construct center from chord perpendicular bisector; choose branch with `yc > max(y_left, y_right)`.
- Reject if no valid center branch.
- Reject if any slice-boundary point violates `y_base(x) <= y_ground(x)`.
- Evaluate valid candidate with Bishop solver.
- Reject if geometry/convergence fails.

5. Sort valid candidates by FOS ascending.

6. Retain the best `ceil(retain_ratio * valid_count)` candidates.

7. Build next iteration pair set from unique pairs of retained candidates.

8. Repeat until `iterations` complete or no active pairs/valid candidates remain.

9. Return global best valid candidate plus search diagnostics.

## Outputs

- Analysis result for the best surface (`fos`, moments, slice data, convergence history).
- Search payload:
  - `best_surface` (`xc`, `yc`, `r`, endpoints, `fos`)
  - `iteration_summaries` (`pairs_evaluated`, `valid_surfaces`, `best_fos`, `mean_fos`, `retained_count`)
  - `top_surfaces` (ranked list, capped by `top_n`)
  - reproducibility metadata (`seed`, settings, domain, total generated/valid)

## Determinism Contract

- With fixed input and fixed `seed`, output is deterministic:
  - same best FOS
  - same best geometry
  - same iteration summaries

## Extension Roadmap (Spencer / Non-Circular)

### Spencer

- Keep search generation independent from solver.
- Add `solver_method` selection (`bishop_simplified`, `spencer`).
- Reuse candidate generation and validity filtering.
- Pass candidate surfaces into Spencer solver for evaluation.
- Extend diagnostics with force-equilibrium residuals specific to Spencer.

### Non-Circular Surfaces

- Introduce generalized `SlipSurface` interface for polyline/parametric surfaces.
- Replace circle-specific constructor with surface generators per search mode.
- Keep auto-refine concept but define refinement over non-circular control variables (not radius).
- Update validity checks from circle base function to generic `y_base(x)`/intersection evaluation.

### Multi-Soil / Water / Seismic (future)

- Maintain search core unchanged; inject richer evaluation models:
  - per-slice material mapping
  - pore pressure model `u(x, z)`
  - surcharge and seismic force models
- Keep output structure stable and append new diagnostic terms rather than changing existing fields.
