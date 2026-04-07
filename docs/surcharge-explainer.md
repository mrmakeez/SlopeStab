# Uniform Surcharge (v1)

This document defines shipped v1 surcharge behavior.

## Scope

v1 adds optional crest surcharge loading for both Bishop and Spencer analyses.

- Plane strain, unit thickness.
- Uniform pressure units: `kPa` (`kN/m^2`).
- Surcharge is mapped to per-slice external vertical force.

Not implemented in v1:

- Additional seismic models beyond v1 horizontal pseudo-static (`docs/seismic-explainer.md`).
- Distributed horizontal surcharge components.

## JSON Interface

`loads` is optional in project input.

```json
{
  "loads": {
    "uniform_surcharge": {
      "magnitude_kpa": 10.0,
      "placement": "crest_infinite"
    },
    "seismic": { "model": "none" },
    "groundwater": { "model": "none" }
  }
}
```

`uniform_surcharge` fields:

- `magnitude_kpa`: non-negative float.
- `placement`:
  - `crest_infinite`
  - `crest_range`
- `x_start`/`x_end`:
  - not allowed for `crest_infinite`
  - required for `crest_range`
  - must satisfy `x_start < x_end` and both at/above crest start (`x >= geometry.x_toe + geometry.l`)

Seismic is supported separately under `loads.seismic` (see `docs/seismic-explainer.md`). Groundwater models are documented in `docs/groundwater-explainer.md`.

## Solver Semantics

Per-slice fields are additive and explicit:

- `weight`: soil self-weight only.
- `external_force_y`: surcharge contribution.
- `total_vertical_force = weight + external_force_y`.

v1 keeps surcharge handling independent from groundwater channels by carrying dedicated external/pore fields on slice geometry/results.

## Determinism and Compatibility

- If `loads` is omitted (or surcharge magnitude is zero), solver results match baseline no-load behavior.
- Existing no-load inputs remain valid without modification.
- Result metadata includes a `loads` object so CLI outputs expose resolved load inputs used in a run.

## Verification Benchmark Policy

- Case 3 surcharge 50 kPa is the primary surcharge benchmark and is included in `python -m slope_stab.cli verify` for both Bishop and Spencer.
- Case 3 surcharge 100 kPa is retained as a non-verify stress regression (unittest-only) to cover shallow local failure behavior and Spencer invalid-surface handling.
