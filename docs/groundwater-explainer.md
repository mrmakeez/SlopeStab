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

1. Evaluate at the center of the slice base:
   - `x_mid = 0.5 * (x_left + x_right)`
   - `y_base_mid` from linear interpolation of base endpoints
   - `y_water_mid` and local water-surface slope at `x_mid`
2. Compute effective head:
   - `h_eff = max(y_water_mid - y_base_mid, 0)`
3. Compute pore pressure at base center:
   - custom: `u = gamma_w * h_eff * Hu`
   - auto: `Hu = cos^2(arctan(local_water_surface_slope))`, then `u = gamma_w * h_eff * Hu`
4. Convert pressure to base-normal resultant:
   - `U = u * slice.base_length`
5. Store pore application point at slice-base center:
   - `pore_x_app = x_mid`
   - `pore_y_app = y_base_mid`

Strict v1 rule:

- No extrapolation outside provided water-surface `x` range.
- If the required midpoint query is outside the supplied range, the surface is invalid.

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
