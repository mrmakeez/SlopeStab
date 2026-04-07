# Groundwater v1 Explainer

This repository supports two groundwater models under `loads.groundwater`:

- `model = "water_surfaces"`
- `model = "ru_coefficient"`

Both are deterministic and compatible with prescribed-surface and circular-search workflows.

Seismic is supported separately under `loads.seismic` (horizontal pseudo-static in v1); see `docs/seismic-explainer.md`.

## 1) Water Surfaces

Required fields:

- `surface`: polyline `[[x, y], ...]`, at least two points, strictly increasing `x`
- `hu.mode`: `"custom"` or `"auto"`
- `hu.value`: required only for `"custom"` and constrained to `[0, 1]`
- `gamma_w`: optional pore fluid unit weight (`9.81` default)

Per-slice algorithm:

1. Evaluate pore pressure at the center of the slice base:
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

6. Evaluate ponded-water top loading over the slice top boundary where water is above ground:
   - `h_pond(x) = max(y_water(x) - y_ground(x), 0)`
   - vertical ponded resultant (downward): `F_y_pond = gamma_w * integral(h_pond(x) dx)`
   - horizontal ponded resultant on sloping submerged top: `F_x_pond = -gamma_w * integral(h_pond(x) * slope_ground(x) dx)`
   - ponded resultants are added into slice external load channels (`external_force_x`, `external_force_y`) with deterministic application points.

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

Groundwater acts through two channels:

- Bishop: resistance equations use pore vertical projection (`U * cos(alpha)`).
- Spencer: resistance equations use effective-base coupling (`T = cL + (N - U) tan(phi)`).

Ponded-water and surcharge resultants are treated as external slice loads:

- vertical components contribute through total vertical force terms.
- horizontal and vertical external components both contribute through external moment terms about slip-center.

Seismic coupling in v1:

- pseudo-static horizontal seismic force is assembled at slice level into `external_force_x`.
- groundwater pore-pressure resultants (`pore_force`) are not part of seismic inertial mass basis in v1.

## 4) Verification Coverage

Built-in `cli verify` includes groundwater prescribed checks:

- Case 5 (Water Surfaces, Hu=1): Bishop + Spencer
- Case 5 (Water Surfaces, Hu=Auto): Bishop + Spencer
- Case 6 (Ru Coefficient): Bishop + Spencer
- Case 7 (Ponded Water, Hu=Auto): Bishop + Spencer
- Case 8 (Ponded Water, Hu=Auto): Bishop + Spencer
