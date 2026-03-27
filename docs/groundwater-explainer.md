# Groundwater v1 Explainer

This repository supports two groundwater models under `loads.groundwater`:

- `model = "water_surfaces"`
- `model = "ru_coefficient"`

Both are deterministic and compatible with prescribed-surface and circular-search workflows.

## 1) Water Surfaces

Required fields:

- `surface`: polyline `[[x, y], ...]`, at least two points, strictly increasing `x`
- `hu.mode`: `"custom"` or `"auto"`
- `hu.value`: required only for `"custom"` and constrained to `[0, 1]`
- `gamma_w`: optional pore fluid unit weight (`9.81` default)

Per-slice algorithm:

1. Build integration nodes from slice endpoints plus interior water-surface vertices that fall inside the slice.
2. For each node, compute:
   - base ordinate `y_base`
   - water ordinate `y_water`
   - `h_eff = max(y_water - y_base, 0)`
3. Compute pore pressure at each node:
   - custom: `u = gamma_w * h_eff * Hu`
   - auto: `Hu = cos^2(arctan(local_water_surface_slope))`, then `u = gamma_w * h_eff * Hu`
4. Integrate pore resultant along slice base:
   - `U = sum(0.5 * (u_i + u_{i+1}) * ds_i)`
   - `ds_i = (x_{i+1} - x_i) / cos(alpha_slice_base)`

Strict v1 rule:

- No extrapolation outside provided water-surface `x` range.
- If required slice integration nodes are outside the supplied range, the surface is invalid.

## 2) Ru Coefficient

Required fields:

- `ru` in `[0, 1]`

Per-slice equations:

- `W_soil = slice.weight` (soil self-weight only)
- `sigma_v = W_soil / slice.width`
- `u = ru * sigma_v`
- `U = u * slice.base_length`

External loads (`external_force_y`) are excluded from Ru pore-pressure construction by design.

## 3) Solver Coupling

Groundwater acts through effective-normal resistance terms:

- Bishop: resistance equations use pore vertical projection (`U * cos(alpha)`).
- Spencer: resistance equations use effective-base coupling (`T = cL + (N - U) tan(phi)`).

Driving moment terms remain based on total vertical loads.

## 4) Verification Coverage

Built-in `cli verify` includes groundwater prescribed checks:

- Case 5 (Water Surfaces, Hu=1): Bishop + Spencer
- Case 5 (Water Surfaces, Hu=Auto): Bishop + Spencer
- Case 6 (Ru Coefficient): Bishop + Spencer
