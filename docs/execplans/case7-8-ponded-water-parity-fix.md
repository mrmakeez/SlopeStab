# ExecPlan: Case 7/8 Ponded-Water Parity Fix (Spencer-Centric, Consensus-Gated)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date during implementation.

This repository includes `PLANS.md` at repo root. This ExecPlan is maintained in accordance with that file.

Consensus status: **Codex + Boyle aligned** on scope below.  
Review agent: [@Boyle](agent://019d3206-d7e3-7d32-8e2e-5b33e8996054).  
Implementation is permitted only under this agreed scope.

## Purpose / Big Picture

After this change, ponded-water Cases 7 and 8 match Slide2 much more closely for Spencer without horizontal-force scaling heuristics. Users now see improved FOS parity and improved per-slice `Base Normal Force` parity for Spencer, while preserving baseline correctness for Cases 1-6 and deterministic behavior.

## Progress

- [x] (2026-03-28 +13:00) Reproduced Case 7/8 prescribed runs and compared per-slice `W`, `u`, `N` against `.s01`.
- [x] (2026-03-28 +13:00) Confirmed current production slice boundaries differ from `.s01` minimum-slice boundaries in Cases 7/8.
- [x] (2026-03-28 +13:00) Ran exact-boundary experiments from `.s01` and isolated remaining Spencer mismatch to solver coupling (Case 7).
- [x] (2026-03-28 +13:00) Completed independent Boyle review and adversarial pushback cycle.
- [x] (2026-03-28 +13:00) Reached Codex+Boyle consensus on implementation scope.
- [x] (2026-03-28 +13:00) Implemented Spencer coupling fix (removed horizontal scaling heuristics; added deterministic `lambda=0` fallback rule).
- [x] (2026-03-28 +13:00) Added full-slice Case 7/8 parity regressions (including Spencer per-slice parity and boundary parity tooling path).
- [x] (2026-03-28 +13:00) Ran full verification/test gate and recorded evidence.
- [x] (2026-03-28 +13:00) Updated ExecPlan living sections and closed implementation.

## Surprises & Discoveries

- Observation: With exact `.s01` slice boundaries, Bishop parity becomes nearly exact for Cases 7/8, and Case 8 Spencer also becomes near-exact.  
  Evidence: exact-boundary parity tooling in `tests/regression/test_groundwater_case7_case8.py` yields tight `W/u/N` tolerances.
- Observation: Case 7 Spencer still diverged strongly before solver fix even with exact boundaries, proving a solver issue remained after geometry parity.  
  Evidence: pre-fix exact-boundary runs showed large `|dN|` under heuristic path selection.
- Observation: Case 7 `.s01` Spencer lambda data aligns with a `lambda=0` branch.  
  Evidence: fallback path now selected deterministically for Case 7 and passes tightened verify tolerance.
- Observation: One non-ponded regression appeared during rewrite due to over-broad candidate filtering.  
  Evidence: `tests.regression.test_surcharge_case3` failed until low-`m_alpha` pre-filtering was restricted to horizontal-external-force cases.

## Decision Log

- Decision: Proceed with Spencer coupling fix + regression hardening; defer production slice-edge algorithm redesign.  
  Rationale: Cases 7/8 alone are insufficient to safely define a general edge-generation parity algorithm.  
  Date/Author: 2026-03-28 / Codex + Boyle
- Decision: Remove horizontal coupling scale heuristics from Spencer solver.  
  Rationale: Heuristic branch selection was non-physical and dominated Case 7 mismatch behavior.  
  Date/Author: 2026-03-28 / Codex + Boyle
- Decision: Add deterministic `lambda=0` scalar fallback only when full 2D solve has no valid root.  
  Rationale: Matches Case 7 behavior evidence while retaining strict residual and `m_alpha` acceptance gates.  
  Date/Author: 2026-03-28 / Codex + Boyle
- Decision: Keep production slice generator unchanged in this fix and add test-only exact-boundary tooling for forensic parity.  
  Rationale: Improves observability without broad geometry-path regression risk.  
  Date/Author: 2026-03-28 / Codex + Boyle
- Decision: Tighten Spencer verify tolerance for Cases 7/8 from `0.02` to `0.005`.  
  Rationale: Post-fix errors are ~`0.0022`, so tighter tolerance is stable and increases regression sensitivity.  
  Date/Author: 2026-03-28 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- Spencer now solves via one physical 2D coupling path and deterministic fallback instead of heuristic scaling.
- Case 7/8 parity diagnostics were expanded to full-slice production checks and full-slice exact-boundary checks.
- Spencer result metadata now reports the solve path (`two_dimensional` vs `lambda_zero_fallback`) and fallback diagnostics.
- Required gates are passing after implementation.

Remaining gaps:

- Production slice-edge generation is still not a guaranteed Slide2-exact boundary replica for all ponded geometries; this was intentionally deferred.

Lessons learned:

- Case 7/8 parity improvements require both force-model correctness and explicit diagnostic separation between geometry effects and solver effects.
- For Spencer under ponded horizontal load, deterministic fallback behavior is safer than non-physical branch scaling.

## Context and Orientation

Primary implementation files:

- `src/slope_stab/lem_core/spencer.py`
- `tests/regression/test_groundwater_case7_case8.py`
- `tests/unit/test_spencer_solver.py`
- `src/slope_stab/verification/cases.py`

Case artifacts:

- `Verification/Bishop/Case 7/Case7/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01`
- `Verification/Bishop/Case 8/Case8/{933762C3-91E4-45ec-91BF-11DC0C90376F}.s01`

## Plan of Work

The implemented work followed three milestones:

1. Spencer solver coupling rewrite with no horizontal scaling heuristics and deterministic `lambda=0` fallback.
2. Regression hardening for Case 7/8 full-slice parity and exact-boundary forensic tooling.
3. Verification policy tightening for Case 7/8 Spencer tolerances with full-gate reruns.

## Concrete Steps

Run from repository root with:

    $env:PYTHONPATH='src'

Baseline snapshots:

    python -m slope_stab.cli verify --workers 4 --output baseline_verify_before_fix.json
    python -m slope_stab.cli test --workers 4 --output baseline_test_before_fix.json

Targeted checks during implementation:

    python -m unittest tests.unit.test_spencer_solver
    python -m unittest tests.regression.test_groundwater_case7_case8
    python -m unittest tests.regression.test_surcharge_case3
    python -m unittest tests.regression.test_groundwater_case5_case6
    python -m unittest tests.unit.test_groundwater_slice_forces
    python -m unittest tests.integration.test_verification_cases
    python -m unittest tests.regression.test_cli_verify

Final gates:

    python -m slope_stab.cli verify --workers 4 --output verify_after_fix.json
    python -m slope_stab.cli test --workers 4 --output test_after_fix.json

## Validation and Acceptance

Acceptance outcomes achieved:

- Cases 1-6 remained passing without tolerance loosening.
- Case 7 Spencer moved close to Slide2 target with improved parity (`|delta FOS| ~= 0.00217`).
- Case 8 Spencer remained close to Slide2 target (`|delta FOS| ~= 0.00215`).
- Case 7/8 Spencer per-slice parity diagnostics were materially improved and hardened.
- If 2D solve has no acceptable root, deterministic fallback is used; if fallback fails acceptance checks, deterministic `ConvergenceError` is raised.

## Idempotence and Recovery

The changes are additive and rerunnable. If regressions appear:

1. Re-run targeted Spencer and groundwater regressions first.
2. Disable/revert Spencer fallback path only, preserving diagnostics tests to keep the defect visible.
3. Re-run full verify/test gate before additional changes.

## Interfaces and Dependencies

Public schema changes: none.

Internal behavior changes:

- Spencer no longer uses horizontal scaling heuristics.
- Spencer metadata now exposes solve-path diagnostics.
- Regression helpers include exact-boundary parity tooling using `.s01` minimum-slice boundaries.

Runtime dependencies remain unchanged (`numpy`, `scipy`, `cma`).

Plan revision note (2026-03-28): Added this ExecPlan to repository docs and marked implementation complete with recorded parity/gate evidence.
