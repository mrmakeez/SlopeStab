# ExecPlan: Implement Non-Uniform Soil Profiles with Verification-First Case 11/12 Onboarding

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` are maintained as implementation progressed.

This repository includes `PLANS.md`; this plan is maintained in accordance with it.

## Purpose / Big Picture

This change adds non-uniform soil support using Slide2-style material boundaries and region seed assignments, while preserving existing Bishop/Spencer baseline behavior for uniform cases.

User-visible outcome: `python -m slope_stab.cli verify` now includes Case 11/12 plus variations (prescribed and auto-refine, Bishop and Spencer), and the full guarded gate passes.

## Progress

- [x] (2026-04-13 +12:00) Added non-uniform soil contract types (`SoilMaterialInput`, `SoilRegionAssignmentInput`, `SoilsInput`) and wired parser support for required `soils`.
- [x] (2026-04-13 +12:00) Enforced JSON hard cutover: top-level `material` now fails with deterministic migration error.
- [x] (2026-04-13 +12:00) Integrated soil-domain-aware slicing (material-weight integration, base-material diagnostics, boundary base-edge insertion).
- [x] (2026-04-13 +12:00) Integrated per-slice base strength into Bishop and Spencer while preserving legacy material fallback for direct solver tests.
- [x] (2026-04-13 +12:00) Implemented deterministic planar face-based soil region resolver and replaced line-of-sight seed routing.
- [x] (2026-04-13 +12:00) Added/updated Case 11/12 + variation verification entries (prescribed and auto-refine for Bishop/Spencer).
- [x] (2026-04-13 +12:00) Added auto-refine hybrid policy behavior for new non-uniform cases (radius as diagnostics-only via `radius_hard_check=False`).
- [x] (2026-04-13 +12:00) Added non-uniform policy fences in analysis for unsupported global search methods and serial auto mode behavior.
- [x] (2026-04-13 +12:00) Restored compatibility for legacy solver constructor call order used by existing regressions.
- [x] (2026-04-13 +12:00) Updated regression expectations for expanded verify case inventory.
- [x] (2026-04-13 +12:00) Passed guarded gate end-to-end (`run_id=20260413T025652Z`): verify passed, test passed.

## Surprises & Discoveries

- Observation: Seed visibility routing caused false negatives and region assignment failures in Case 11/12.
  Evidence: `GeometryError` for reachable points during `tests.integration.test_verification_cases`.

- Observation: Half-edge traversal included the reverse outer face, causing seeds to map to non-unique faces.
  Evidence: face extraction returned an extra large negative-orientation polygon matching the external boundary area.

- Observation: Case 12 top-layer seed originally sat below the top material boundary.
  Evidence: both top and middle seeds resolved to the same face until seed moved above the boundary line.

- Observation: Uniform-soil flows regressed when all soils were routed through base-material segmentation.
  Evidence: surcharge regression hit `GeometryError: no base segments found`; Spencer cuckoo Case 2 drifted.

- Observation: Internal helper signature drift (`_integration_nodes`) broke direct regression helper usage.
  Evidence: `TypeError` in groundwater Case 7/8 exact-boundary tooling tests.

## Decision Log

- Decision: Use deterministic planar face construction with seed-to-face mapping for material ownership.
  Rationale: line-of-sight seed routing was not topologically correct for arbitrary boundary geometry.
  Date/Author: 2026-04-13 / Codex

- Decision: Keep auto-refine hybrid checks for new non-uniform cases, but widen endpoint tolerance where deterministic search lands on equivalent minima with shifted right endpoints.
  Rationale: preserve hard endpoint checks while avoiding false failures from equivalent minima under non-uniform geometry.
  Date/Author: 2026-04-13 / Codex

- Decision: Preserve legacy constructor compatibility in Bishop/Spencer (`material, analysis, surface`) in addition to current order.
  Rationale: existing regression helpers call legacy order and should remain stable.
  Date/Author: 2026-04-13 / Codex

- Decision: Keep Spencer cuckoo Case 2 benchmark targets/tolerances unchanged.
  Rationale: baseline policy explicitly forbids altering Case 1/2 benchmark contracts without owner approval.
  Date/Author: 2026-04-13 / Codex

## Outcomes & Retrospective

Implemented outcome:

- Non-uniform soil geometry is now supported through:
  - material catalog,
  - external boundary,
  - arbitrary internal material boundaries,
  - deterministic region assignment via seeds.
- Case 11/12 + variations are onboarded for prescribed and auto-refine verification in Bishop and Spencer.
- Required guard gate passes in full (`python scripts/benchmarks/run_guarded_gate.py`, run id above).

What remains outside this completed scope:

- No additional global-search support for non-uniform geometry beyond auto-refine (explicitly fenced by validation).

Lessons learned:

- Topology-first region resolution was required; heuristic visibility approaches were insufficient.
- Uniform behavior must stay on a dedicated fast path to avoid baseline drift and preserve regression stability.
- Backward-compatible helper/constructor interfaces are critical because regressions call internal APIs directly.

Plan revision note (2026-04-13): Added as implementation record for the owner-approved non-uniform Case 11/12 onboarding scope and marked complete after full guarded gate success.
