# ExecPlan: Cuckoo Verification Wall-Time Optimization with Shared Parameters

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md`; this plan is maintained in accordance with it.

## Purpose / Big Picture

This work attempts to reduce cuckoo verification wall time while keeping one shared cuckoo profile everywhere and preserving all current benchmark/oracle gates. If no candidate delivers meaningful speedup under unchanged gates, the correct implementation outcome is no parameter change.

## Progress

- [x] (2026-03-29 +13:00) Added deterministic tuning harness `scripts/diagnostics/cuckoo_tuning_matrix.py` to evaluate candidate profiles against frozen cuckoo benchmark/oracle gates.
- [x] (2026-03-29 +13:00) Captured all-10-fixture baseline evidence to `docs/benchmarks/cuckoo_tuning_baseline.json`.
- [x] (2026-03-29 +13:00) Ran coarse and targeted sweeps (proxy + all-10 validation) and filtered to gate-safe candidates only.
- [x] (2026-03-29 +13:00) Ran warm-up + two measured comparison between baseline and best gate-safe candidate and saved evidence to `docs/benchmarks/cuckoo_tuning_comparison.json`.
- [x] (2026-03-29 +13:00) Applied plan go/no-go rule: no candidate met the required 15% median aggregate wall-time reduction; keep shared cuckoo parameters unchanged.
- [x] (2026-03-29 +13:00) Ran full `python -m slope_stab.cli verify` and `python -m slope_stab.cli test`; both passed (`all_passed: true`).

## Surprises & Discoveries

- Observation: Spencer/Bishop Case 2 oracle gates are the dominant constraint for aggressive runtime reduction.
  Evidence: Many faster candidates failed `case2_cuckoo_oracle.json` and/or `case2_cuckoo_oracle_spencer.json` while still passing benchmark gates.

- Observation: Gate-safe candidates clustered around the existing profile and delivered only modest speedup.
  Evidence: Best gate-safe candidate (`min_improvement=2e-4` with other settings unchanged) improved median aggregate all-10-fixture time by about 2.9%, well below the 15% acceptance threshold.

## Decision Log

- Decision: Freeze benchmark constants, oracle metadata, oracle tolerances, and margins during tuning.
  Rationale: Prevents passing by changing targets instead of improving performance.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Keep `seed=0`, `post_polish=True`, `levy_beta=1.5`, `alpha_max=0.5`, `alpha_min=0.05` fixed during tuning.
  Rationale: Preserve deterministic behavior and algorithm shape while tuning runtime levers.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Accept a parameter update only if median aggregate all-10 cuckoo fixture wall time improves by at least 15% while all cuckoo gates remain green.
  Rationale: Avoid churn for marginal gains under strict verification constraints.
  Date/Author: 2026-03-29 / Project Owner + Codex

- Decision: Final outcome is no shared-cuckoo-parameter change.
  Rationale: Best gate-safe candidate improvement (~2.9%) did not meet the 15% threshold.
  Date/Author: 2026-03-29 / Codex

## Outcomes & Retrospective

Implemented:

- Added reusable tuning harness at `scripts/diagnostics/cuckoo_tuning_matrix.py`.
- Captured baseline and comparison evidence files in `docs/benchmarks`.
- Completed sweep and comparison workflow with frozen-gate policy.

Result:

- Shared cuckoo parameters remain unchanged (`40/300/7000`, `discovery_rate=0.25`, `min_improvement=1e-4`, `stall_iterations=25`).
- Final closure gate status: `cli verify` green and `cli test` green.

Lesson:

- Current oracle strictness around Case 2 leaves limited room for parameter-only runtime reduction without changing verification gates.

## Context and Orientation

Shared cuckoo defaults are parsed in `src/slope_stab/io/json_io.py`. Explicit verification cuckoo configs are in `src/slope_stab/verification/cases.py`. Cuckoo benchmark/oracle regressions are in `tests/regression/test_cuckoo_global_search_benchmark.py`, `tests/regression/test_spencer_cuckoo_global_search_benchmark.py`, `tests/regression/test_cuckoo_global_oracle.py`, and `tests/regression/test_spencer_cuckoo_global_oracle.py`.

This plan did not change benchmark/oracle values; it only tested whether parameter changes could speed up runs while preserving all current thresholds.

## Plan of Work

1. Add diagnostics harness for fixture-level timing and gate checks.
2. Capture baseline.
3. Run coarse and targeted sweeps to find gate-safe candidates.
4. Compare baseline vs best candidate with warm-up and repeated measured runs.
5. Apply go/no-go rule.
6. If threshold met, propagate new profile everywhere; otherwise keep profile unchanged.
7. Run full verify/test gate and close out.

## Concrete Steps

Executed commands (repo root, `PYTHONPATH=src`):

- `python scripts/diagnostics/cuckoo_tuning_matrix.py --fixtures "@all" --measured-runs 1 --output docs/benchmarks/cuckoo_tuning_baseline.json`
- `python scripts/diagnostics/cuckoo_tuning_matrix.py --fixtures "@all" --profiles-file tmp/cuckoo_profiles_finalists.json --measured-runs 1 --output tmp/cuckoo_all10_finalists_r1.json`
- `python scripts/diagnostics/cuckoo_tuning_matrix.py --fixtures "@all" --profiles-file tmp/cuckoo_profiles_compare.json --warmup-runs 1 --measured-runs 2 --output docs/benchmarks/cuckoo_tuning_comparison.json`

Observed comparison summary:

- Baseline median aggregate (all 10 fixtures): `92.217365s`
- Best gate-safe candidate median aggregate: `89.568623s`
- Improvement: `~2.87%` (below required `15%`)

## Validation and Acceptance

Acceptance rule for parameter update:

- All cuckoo benchmark/oracle checks must pass unchanged.
- Full `cli verify` and `cli test` must pass.
- Median aggregate all-10-fixture improvement must be at least `15%`.

Outcome against acceptance:

- Correctness conditions were satisfied for the best candidate.
- Performance improvement did not meet threshold.
- Therefore no parameter update is accepted.

## Idempotence and Recovery

The harness and evidence workflow is repeatable and non-destructive. Future reruns can reuse the same script with updated candidate lists. If future requirements lower the speedup threshold or relax gates, the same harness can be reused to re-evaluate.

Plan revision note (2026-03-29): Marked this plan complete with a no-change parameter decision because measured gate-safe speedup did not meet the agreed 15% threshold.
