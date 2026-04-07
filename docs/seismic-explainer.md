# Pseudo-Static Seismic (v1)

This document defines shipped v1 seismic behavior.

## Scope

v1 supports horizontal pseudo-static seismic loading for both Bishop and Spencer:

- `loads.seismic.model = "pseudo_static"`
- horizontal coefficient `kh` in `[0, 1]`
- vertical coefficient `kv` is fixed to `0.0` in v1

Not implemented in v1:

- nonzero `kv`
- alternative seismic models

## JSON Contract

```json
{
  "loads": {
    "seismic": {
      "model": "pseudo_static",
      "kh": 0.132,
      "kv": 0.0
    }
  }
}
```

Rules:

- `loads` is optional.
- `loads.seismic` is optional.
- if omitted, behavior is unchanged from no-seismic baseline.
- `kh` is required when `model = "pseudo_static"`.
- `kv` defaults to `0.0` and any nonzero value is rejected.

## Slice Assembly

Seismic is assembled in `slice_generator` as an external horizontal resultant:

- `Fh = kh * W_soil`
- `W_soil` is slice soil self-weight only (`slice.weight`)
- surcharge and ponded-water vertical resultants are excluded from seismic mass basis
- pore-pressure resultants are excluded from seismic mass basis

Sign convention:

- positive `Fh` acts in +x (to the right)

Application point (for external moment coupling):

- x: slice midpoint
- y: slice mass-centroid approximation from top/base edge ordinates

Diagnostics:

- per-slice `seismic_force_x` and `seismic_force_y` are emitted in slice results

## Verification Notes

Case 9 and Case 10 Slide2 artifacts are used for v1 parity checks:

- Case 9: `kh = 0.132`, `kv = 0`
- Case 10: `kh = 0.25`, `kv = 0`
- per-slice horizontal seismic force parity is checked from `.s01` evidence
- Bishop/Spencer FOS parity is checked in verification/regression tests

## Auto-Refine Parity Snapshot

Snapshot date: `2026-04-07`.

Auto-refine run settings used for this snapshot:

- `divisions_along_slope = 20`
- `circles_per_division = 10`
- `iterations = 10`
- `divisions_to_use_next_iteration_pct = 50.0`
- Case 9 search limits: `x_min = -50`, `x_max = 150`
- Case 10 search limits: `x_min = 0`, `x_max = 35`

| Case | Method | Slide2 FOS | Before-Polish FOS | Before Delta (abs) | After-Polish FOS | After Delta (abs) |
|---|---|---:|---:|---:|---:|---:|
| Case 9 | Bishop | 0.987678 | 0.997426 | 0.009748 | 0.986979 | 0.000699 |
| Case 9 | Spencer | 1.001120 | 1.010174 | 0.009054 | 1.001366 | 0.000246 |
| Case 10 | Bishop | 0.907907 | 0.909056 | 0.001149 | 0.907613 | 0.000294 |
| Case 10 | Spencer | 0.918623 | 0.918893 | 0.000270 | 0.916492 | 0.002131 |

This section is an analysis snapshot only and is not a locked verification benchmark.
