# ExecPlan Revision: Pseudo-Static Seismic (Horizontal-Only) Recovery

## Summary
- Replace prior plan text with a clean, ASCII-safe copy to remove ambiguity.
- Keep v1 scope horizontal-only (`kh` active, `kv = 0` enforced).
- Add a strict prototype gate that selects seismic mass basis and sign before production seismic edits.
- Implement seismic at slice-load assembly so Bishop/Spencer equations remain unchanged.

## Public Interface (v1)
- `loads.seismic.model`: `none | pseudo_static`
- `loads.seismic.kh`: required for `pseudo_static`, bounded `[0, 1]`
- `loads.seismic.kv`: optional, default `0.0`, must equal `0.0` in v1
- Backward compatibility is preserved when `loads` or `loads.seismic` is omitted

## Prototype Gate (Required)
Evaluate Case 9/10 prescribed-surface evidence against candidate rules:

- Mass basis A: `Fh = kh * W_soil`
- Mass basis B: `Fh = kh * (W_soil + external_force_y)`
- Sign candidates: `+Fh` and `-Fh` applied to `external_force_x`

Acceptance metrics:

- Case 9 slice-force MAPE `<= 0.5%`
- Case 10 slice-force MAPE `<= 2.0%`
- Case 10 toe-region max absolute percent error `<= 5.0%`
- Case 9/10 Bishop and Spencer FOS absolute error `<= 0.01`

Stop condition:

- If no candidate passes, stop implementation and revise this ExecPlan before any production seismic-force edits.

Decision recorded from current prototype evidence:

- Selected mass basis/sign: `Fh = +kh * W_soil`
- Rejected candidates: `-kh * W_soil`, `+kh * (W_soil + external_force_y)`, `-kh * (W_soil + external_force_y)`

## Implementation Changes
- Extend seismic schema/parser/metadata round-trip for `pseudo_static`.
- Add slice-level seismic horizontal inertial force from selected basis/sign.
- Keep surcharge and ponded-water channels unchanged.
- Exclude pore-pressure resultant from seismic inertial mass in v1.
- Keep Bishop/Spencer equations unchanged; they consume updated slice external forces.
- Add minimal per-slice diagnostics for seismic contribution.

## Verification and Tests
- Unit tests:
  - Seismic schema validation (`pseudo_static` accepted, nonzero `kv` rejected).
  - Slice-force assembly tests for seismic-only and seismic with surcharge/ponded-water interactions.
- Regression tests:
  - Prototype mass-basis/sign gate using Case 9/10 `.s01` slice-force evidence.
  - Case 9/10 per-slice horizontal seismic force parity checks.
  - Case 9/10 Bishop/Spencer FOS parity checks.
- Verification suite:
  - Add Case 9 and Case 10 for Bishop and Spencer (total verification cases: `39 -> 43`).
- Gate commands:
  - `PYTHONPATH='src' python -m slope_stab.cli verify`
  - `PYTHONPATH='src' python -m slope_stab.cli test`

## Documentation Updates
- Update `README.md` load contract to include pseudo-static seismic support.
- Update `docs/surcharge-explainer.md` and `docs/groundwater-explainer.md` to remove "seismic unsupported" wording and link seismic docs.
- Add `docs/seismic-explainer.md` documenting:
  - JSON contract (`model`, `kh`, `kv`)
  - sign convention and mass basis
  - slice-level assembly behavior
  - v1 limits (horizontal-only, `kv=0`)

## Assumptions
- v1 remains horizontal-only; nonzero vertical seismic is deferred.
- Slide2 Case 9/10 artifacts are the parity source for this scope.
- Existing search methods and non-seismic baselines remain unchanged.
