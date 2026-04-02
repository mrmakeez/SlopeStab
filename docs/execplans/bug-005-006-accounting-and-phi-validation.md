# ExecPlan: BUG-005 Evaluation Accounting + BUG-006 Friction Angle Validation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md`; this plan is maintained in accordance with it.

## Purpose / Big Picture

This plan closes two verified defects without changing solver benchmark targets:

- `BUG-005`: search reporting under-counts work because post-search refinement/polish evaluations are not published separately.
- `BUG-006`: `material.phi_deg` is parsed without a physical-range guard; invalid values fail late or produce unstable behavior.

After implementation, users will see explicit stage-separated evaluation accounting in analysis output and will receive early, deterministic JSON `InputValidationError` failures for `phi_deg` outside `0 <= phi_deg < 90`.

## Scope

In scope:

- Enforce strict JSON validation rule: `0 <= material.phi_deg < 90`.
- Introduce explicit post-search refinement counters and publish them in analysis output.
- Preserve deterministic ordering and existing benchmark behavior.
- Add tests proving both bugs are fixed and regression-safe.

Out of scope:

- Any change to benchmark targets/tolerances.
- Any change to solver mechanics for valid inputs.
- Any new search algorithm or non-circular feature work.

## Progress

- [x] (2026-03-31 +13:00) Drafted implementation-ready ExecPlan for BUG-005 and BUG-006.
- [x] (2026-03-31 +13:00) Obtained explicit consensus review from `@Ptolemy` with `CONSENSUS: AGREE`.
- [x] (2026-03-31 +13:00) Implemented BUG-006 parser guard in `json_io.py` and added `phi_deg` boundary tests.
- [x] (2026-03-31 +13:00) Implemented BUG-005 stage-separated accounting publication for auto-refine and all global search methods with additive metadata fields.
- [x] (2026-03-31 +13:00) Added regression coverage for post-refinement field presence, partition equations, and zero-valued publication when post-polish is disabled.
- [x] (2026-03-31 +13:00) Ran process-pool preflight and full gates: `python -m slope_stab.cli verify` and `python -m slope_stab.cli test` (both green).

## Surprises & Discoveries

- Observation: current global-search result counters represent only the global evaluation phase, while refinement/polish runs occur afterward via raw evaluation paths.
  Evidence: `direct_global.py`, `cuckoo_global.py`, and `cmaes_global.py` compute core counters from evaluator statistics, then execute deterministic refinement/polish stages.

- Observation: parser-level numeric hygiene already rejects bools and non-finite floats, but no physical range is enforced for `phi_deg`.
  Evidence: `src/slope_stab/io/json_io.py` validates `gamma > 0` while leaving `phi_deg` unbounded.

## Decision Log

- Decision: keep existing global-stage counters intact for backward compatibility and add explicit post-refinement counters rather than silently changing semantics of existing fields.
  Rationale: existing downstream tooling already reads current fields; additive fields minimize compatibility risk while fixing observability gaps.
  Date/Author: 2026-03-31 / Codex (draft, pending reviewer consensus)

- Decision: enforce `0 <= phi_deg < 90` at JSON parsing boundary.
  Rationale: invalid friction angles are input contract violations and should fail early with explicit validation errors.
  Date/Author: 2026-03-31 / Codex (draft, pending reviewer consensus)

- Decision: this fix is parser-boundary enforcement only; no separate dataclass-constructor hardening is added in this scope.
  Rationale: `BUG-006` is an input-contract defect and parser validation is the canonical enforcement boundary in this codebase.
  Date/Author: 2026-03-31 / Codex (draft, pending reviewer consensus)

- Decision: additive metadata only; existing fields keep their current meaning and remain in-place.
  Rationale: preserves backward compatibility for existing payload consumers.
  Date/Author: 2026-03-31 / Codex (draft, pending reviewer consensus)

- Decision: explicit reviewer consensus is achieved for this revised ExecPlan (`CONSENSUS: AGREE` from `@Ptolemy`).
  Rationale: owner-required consensus gate is satisfied and implementation may proceed under this contract.
  Date/Author: 2026-03-31 / Ptolemy + Codex

## Outcomes & Retrospective

Implemented:

- Added parser validation: `material.phi_deg` must satisfy `0 <= phi_deg < 90` and fails early with `InputValidationError`.
- Added deterministic refinement-stage counters:
  - auto-refine: `post_refinement_generated_surfaces`, `post_refinement_valid_surfaces`, `post_refinement_invalid_surfaces`
  - global methods: `post_refinement_total_evaluations`, `post_refinement_valid_evaluations`, `post_refinement_infeasible_evaluations`
- Published additive counters in analysis metadata while preserving existing core-stage fields unchanged.
- Added/updated tests to enforce parser contract, metadata presence, partition equations, and zero-valued publication paths.

Validation:

- `python -m slope_stab.cli verify` passed (`all_passed: true`).
- `python -m slope_stab.cli test` passed (`all_passed: true`).

Retrospective:

- Additive metadata was the lowest-risk way to close BUG-005 without breaking existing consumers.
- Parser-boundary validation fully resolves BUG-006 while keeping solver behavior unchanged for valid inputs.

## Context and Orientation

Primary code areas:

- JSON parsing and validation:
  - `src/slope_stab/io/json_io.py`
- Material model downstream use:
  - `src/slope_stab/materials/mohr_coulomb.py`
- Search implementations and result metadata:
  - `src/slope_stab/search/auto_refine.py`
  - `src/slope_stab/search/direct_global.py`
  - `src/slope_stab/search/cuckoo_global.py`
  - `src/slope_stab/search/cmaes_global.py`
- Analysis output assembly:
  - `src/slope_stab/analysis.py`
- Tests:
  - `tests/unit` and `tests/regression` modules covering JSON IO and search metadata behavior.

BUG references:

- `BUG-005` and `BUG-006` entries in `BUGS.md` define verified behavior and expected fix direction.

Counter contract definitions used by this plan:

- "Core-stage counters" are the currently published search counters that describe the primary search phase before deterministic post-search refinement/polish.
- "Post-refinement counters" are new additive counters that describe deterministic refinement/polish phases after core search.
- "Total/generated counters" count candidate evaluation records processed in that phase (including invalid candidates); "valid" and "infeasible/invalid" partition those phase totals.

## Milestones

### Milestone 1: Lock Input Contract for `phi_deg`

Add parser validation for `material.phi_deg` so invalid angles fail before analysis execution. This milestone ensures invalid values are rejected deterministically with clear error messages and no downstream numeric instability.

Expected result:

- `phi_deg` accepts values in `[0, 90)` only.
- Inputs with `phi_deg < 0` or `phi_deg >= 90` raise `InputValidationError` with a clear field-specific message.

Proof:

- Unit tests for boundary/invalid values pass.
- Existing valid-input verification cases remain green.

### Milestone 2: Add Stage-Separated Search Accounting

Introduce explicit counters for post-search refinement/polish activity and publish them alongside existing stage counters in CLI analysis output.

Expected result:

- Existing counters continue to represent core search-stage activity.
- New refinement counters publish deterministic counts for post-search refinement/polish evaluations.
- Output makes both phases visible without ambiguity.
- Output contracts are explicit by method family:
  - `direct_global_circular`, `cuckoo_global_circular`, `cmaes_global_circular` add:
    - `post_refinement_total_evaluations`
    - `post_refinement_valid_evaluations`
    - `post_refinement_infeasible_evaluations`
  - `auto_refine_circular` adds:
    - `post_refinement_generated_surfaces`
    - `post_refinement_valid_surfaces`
    - `post_refinement_invalid_surfaces`
  - Existing fields remain unchanged:
    - global methods: `total_evaluations`, `valid_evaluations`, `infeasible_evaluations`
    - auto-refine: `generated_surfaces`, `valid_surfaces`, `invalid_surfaces`
  - No new combined aggregate counter is required in this change; consumers can sum stage fields if needed.

Proof:

- Regression tests demonstrate non-zero refinement counters when refinement runs.
- Existing outputs remain backward compatible with additive fields only.

### Milestone 3: Validate End-to-End and Close

Run full verification and test gates, confirm no benchmark regressions, and finalize plan status.

Expected result:

- `cli verify` passes unchanged benchmark expectations.
- `cli test` passes with new coverage.

Proof:

- Command outputs saved/observed from gate runs.

## Detailed Implementation Plan

1. `phi_deg` validation (`BUG-006`)

- Update `src/slope_stab/io/json_io.py` material parsing to enforce:
  - `phi_deg >= 0`
  - `phi_deg < 90`
- Raise `InputValidationError` with a deterministic message referencing `material.phi_deg` and accepted range.
- Keep current finite/bool guards intact; this change is additive physical validation.

2. Refinement accounting model (`BUG-005`)

- Define explicit post-refinement counter fields in search result metadata for methods that perform refinement/polish after core search.
- Preserve existing fields and semantics (core/global stage counters remain unchanged).
- Lock additive counter names now (no deferred naming):
  - global methods: `post_refinement_total_evaluations`, `post_refinement_valid_evaluations`, `post_refinement_infeasible_evaluations`
  - auto-refine: `post_refinement_generated_surfaces`, `post_refinement_valid_surfaces`, `post_refinement_invalid_surfaces`
- Counting basis (locked):
  - global core-stage (`total_evaluations`, `valid_evaluations`, `infeasible_evaluations`) remains unchanged.
  - global post-refinement counters count candidate evaluation records processed during deterministic post-search refinement/polish, partitioned by valid vs infeasible.
  - auto-refine core-stage (`generated_surfaces`, `valid_surfaces`, `invalid_surfaces`) remains the iterative division stage only.
  - auto-refine post-refinement counters count candidate evaluation records processed during the deterministic refinement/polish calls that occur after iterations.
- For all methods, publish post-refinement counters even when zero.
- Ensure deterministic counting order and no behavior change in candidate selection/merging.

3. Publish both phases in analysis output

- Update `src/slope_stab/analysis.py` output assembly so search payload includes:
  - existing stage counters
  - new post-refinement counters
- Ensure each search method emits consistent field presence where applicable.

4. Tests

- Add/update unit tests for JSON validation:
  - Accept: `phi_deg=0`, representative valid interior value, and near-upper-bound valid (`89.999...`).
  - Reject: negative and `>=90` values with specific `InputValidationError`.
- Add/update search accounting tests:
  - Deterministic fixture where post-refinement runs and counters are asserted.
  - Validate method-specific payload fields are present for:
    - auto-refine family (`generated_*` plus `post_refinement_*_surfaces`)
    - global family (`*_evaluations` plus `post_refinement_*_evaluations`)
  - Assert post-refinement fields are present even when their values are zero.
  - Validate per-phase partition relationships:
    - global: `post_refinement_total_evaluations == post_refinement_valid_evaluations + post_refinement_infeasible_evaluations`
    - auto-refine: `post_refinement_generated_surfaces == post_refinement_valid_surfaces + post_refinement_invalid_surfaces`
  - Validate core-stage fields still behave as before (backward compatibility).
- Keep existing deterministic/stochastic seed stability assertions intact.

5. Documentation and bug tracking updates

- Update `BUGS.md` statuses for `BUG-005` and `BUG-006` once fixes and tests are complete.
- Record exact repro and verification evidence linked to changed tests and command runs.

## Validation and Acceptance

Acceptance is met only when all of the following are true:

1. Parser contract:
   - `material.phi_deg` outside `[0, 90)` is rejected at parse time with explicit `InputValidationError`.
   - Valid boundary values (including `0`) remain accepted.

2. Search accounting:
   - Analysis output publishes both core-stage counters and post-search refinement counters.
   - Output field names match this plan exactly for both method families.
   - Counter partition equations in this plan hold for representative deterministic runs.
   - Reported counters are deterministic and reproducible for fixed seeds.

3. Regression safety:
   - `python -m slope_stab.cli verify` passes.
   - `python -m slope_stab.cli test` passes.
   - No benchmark target/tolerance modifications were needed.

## Execution Notes

- Set environment each run: `$env:PYTHONPATH='src'`.
- Follow repository timeout policy for long commands:
  - `cli verify`: `timeout_ms=1200000`
  - `cli test`: `timeout_ms=2700000`
- Run process-pool preflight before long parallel commands per repository policy.
- Run verify and test sequentially, not in parallel.

## Idempotence and Recovery

- Changes are additive and localized to parsing, search metadata, and tests.
- If counter-shape compatibility concerns arise, preserve old fields and add new fields rather than renaming/removing existing ones.
- If any gate fails, revert only the failing incremental change and re-run targeted tests before full gate rerun.

Plan revision note (2026-03-31): Executed and closed. Implemented parser guard + additive refinement counters, added regression coverage, and passed full verify/test gates after process-pool preflight.
