# Spencer Solver Explained (Current Implementation)

This document explains the Spencer implementation in `src/slope_stab/lem_core/spencer.py`.

Goal in one sentence: solve for `FOS` and interslice coupling `lambda` so force and moment equilibrium are both satisfied for circular-slice geometry.

## Inputs and Conventions

- Uses the same `SliceGeometry` produced by the existing slicing pipeline.
- Uses the same coordinate/sign conventions as the Bishop path.
- Uses the same validity rules as Bishop for search compatibility:
  - final-iteration `m_alpha < 0.2` invalidates the surface
  - negative base shear strength contribution is clamped to zero

## Unknowns Solved

- `FOS` (factor of safety)
- `lambda` (constant interslice force coupling parameter)

The solver uses a deterministic nonlinear root solve over two residuals:

- force residual: normalized closure of interslice force transfer across all slices
- moment residual: `FOS - (sum(resisting_shear) / sum(driving_component))`

## Per-Slice Terms

For each slice, with base angle `alpha`, soil friction `tan(phi)`, and trial `FOS`:

- `A = sin(alpha) - tan(phi) * cos(alpha) / FOS`
- `B = cos(alpha) + tan(phi) * sin(alpha) / FOS`
- `m_alpha = B + lambda * A`
- `delta_E = (W * A - c*b/FOS) / m_alpha`
- `N = (W - lambda*delta_E - c*b*sin(alpha)/FOS) / B`
- `shear_raw = c*b + N*tan(phi)`
- `shear = max(shear_raw, 0)`

The solver enforces finite-term checks around `B`, `m_alpha`, `FOS`, and `lambda`.

## Convergence Strategy

- Deterministic start set for `(FOS, lambda)` with SciPy `root(..., method="hybr")`.
- Accepts the best successful candidate by minimum combined residual norm.
- Requires both residuals to satisfy analysis tolerance.

## Output Diagnostics

On success, result metadata includes:

- `metadata.spencer.lambda`
- `metadata.spencer.force_residual_norm`
- `metadata.spencer.moment_residual`
- `metadata.spencer.nfev`

The public `AnalysisResult` shape remains unchanged for downstream search and reporting compatibility.
