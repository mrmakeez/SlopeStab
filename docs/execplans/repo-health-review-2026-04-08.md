# ExecPlan: Repo Health Fixes for Runner Robustness, Parallel Fallback Semantics, and Cleanup

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md`; this plan is maintained in accordance with it.

## Purpose / Big Picture

This work tightens reliability around test/verification orchestration and removes code drift that can hide failures or increase maintenance cost. After this plan is implemented, `cli test` and `cli verify` will have deterministic, policy-aligned behavior for startup failures versus runtime worker failures, discovery errors will be reported as structured output instead of tracebacks, and dead or duplicated code paths will be reduced.

## Progress

- [x] (2026-04-08 10:40 +12:00) Completed repository review and reproduced two runner robustness failures with executable repro snippets.
- [x] (2026-04-08 10:47 +12:00) Drafted initial ExecPlan with scoped fixes for robustness bugs, refactoring opportunities, and orphaned-code cleanup decisions.
- [x] (2026-04-08 11:26 +12:00) Recorded owner decisions from design grilling: runtime worker failures must fail hard, startup-only fallback permitted, legacy verification API removal is accepted, load null placeholders will be removed entirely, shared error contract module is required, and README breaking-change notes are required.
- [x] (2026-04-08 12:40 +12:00) Implemented structured discovery-error handling in `run_unittest_suite_with_execution(...)` and `cli test` payload emission.
- [x] (2026-04-08 12:52 +12:00) Aligned verification/unittest startup-versus-runtime boundaries with startup-only fallback and runtime hard-failure semantics.
- [x] (2026-04-08 13:05 +12:00) Replaced brittle private-helper-mock tests with boundary-accurate fake executor/future tests.
- [x] (2026-04-08 13:15 +12:00) Consolidated duplicate worker-resolution helpers into shared execution policy module and removed orphaned load placeholders.
- [x] (2026-04-08 13:22 +12:00) Added shared structured error-contract module with frozen code set and applied schema to `cli test` and `cli verify`.
- [x] (2026-04-08 13:29 +12:00) Removed legacy `run_verification_suite(...)` API and migrated integration/tests to `run_verification_suite_with_execution(...)`.
- [x] (2026-04-08 15:35 +12:00) Completed full required gate with artifacts (`tmp/verify_repo_health_fix.json`, `tmp/test_repo_health_fix.json`) after one timeout-retry on `cli test`.

## Surprises & Discoveries

- Observation: `run_unittest_suite_with_execution` can crash before producing any structured output when discovery fails (for example invalid start directory), even though `UnittestRunResult` already has a `discovery_error` channel.
  Evidence: Running `run_unittest_suite_with_execution(start_directory='tests/does_not_exist', top_level_directory='.')` raised `ImportError: Start directory is not importable ...` from `unittest.loader.discover` without returning a `UnittestRunResult`.

- Observation: The documented fallback path in verification/unittest orchestration is partially unreachable in realistic failure paths because internal parallel evaluators wrap worker exceptions into `RuntimeError`.
  Evidence: In both `src/slope_stab/verification/runner.py` and `src/slope_stab/testing/unittest_runner.py`, `_evaluate_*_parallel` catches `Exception` and raises `RuntimeError`, while outer orchestration only falls back on `(OSError, PermissionError)` raised directly.

- Observation: The repository keeps placeholder load-model classes that are exported but not consumed by runtime code or tests.
  Evidence: `rg` references show `NullLoadModel` and `NullPorePressureModel` only in `src/slope_stab/loads/null_models.py` and `src/slope_stab/loads/__init__.py`.

- Observation: Full `cli test` gate can exceed a 45-minute timeout budget in this environment and required one larger-timeout retry to finish.
  Evidence: Initial run timed out at 2,702s; retry with larger timeout completed and passed (`all_passed: true`).

## Decision Log

- Decision: Treat uncaught unittest discovery exceptions as a bug and route them through explicit discovery-error metadata.
  Rationale: The CLI contract is JSON summary output for `test`; hard crashes during discovery remove observability and make automation brittle.
  Date/Author: 2026-04-08 / Codex

- Decision: Keep strict failure behavior for runtime worker errors (do not silently fall back to serial once work has started), but keep auto-mode startup fallback support where policy allows it.
  Rationale: This preserves deterministic explicit-failure policy while fixing the current ambiguity between intended fallback and wrapped exceptions.
  Date/Author: 2026-04-08 / Codex

- Decision: Prioritize removing duplicated orchestration helpers only after behavior bugs are fixed and covered.
  Rationale: Consolidation should not obscure correctness fixes; staged changes reduce regression risk.
  Date/Author: 2026-04-08 / Codex

- Decision: Runtime worker failures in auto mode must fail hard; only startup failures may fallback to serial.
  Rationale: Matches AGENTS.md deterministic failure policy and avoids silent partial execution.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Startup fallback metadata should report actual execution backend as `serial` while preserving fallback reason codes.
  Rationale: Improves observability accuracy without losing decision provenance.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Remove `run_verification_suite(...)` immediately (no compatibility shim).
  Rationale: Owner explicitly accepted a clean breaking change and prefers no stale pathways.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Remove `NullLoadModel` and `NullPorePressureModel` entirely, not just from exports.
  Rationale: They are orphaned placeholders and owner requested full removal.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Introduce a shared error contract module and freeze a small enumerated code set used by both `cli test` and `cli verify`.
  Rationale: Prevents contract drift and supports automation-friendly machine parsing.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Error payload shape is fixed as `{"code": "...", "message": "...", "stage": "..."}`.
  Rationale: Uniform schema across commands simplifies downstream consumers and test assertions.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: `discovery_error` becomes structured (object) instead of string-only payload and is applied now with test updates.
  Rationale: Immediate contract stabilization is preferred over transitional formats.
  Date/Author: 2026-04-08 / Project Owner + Codex

- Decision: Document breaking API/symbol removals in README in the same patch.
  Rationale: Owner requested explicit migration visibility at repo entry point.
  Date/Author: 2026-04-08 / Project Owner + Codex

## Outcomes & Retrospective

Implemented outcomes:

- Startup-versus-runtime behavior is now explicit and tested: auto-mode startup failures can degrade to serial, runtime worker failures fail hard.
- Unittest discovery failures now return structured error payloads instead of uncaught tracebacks.
- Shared error contract module (`src/slope_stab/errors/contracts.py`) now enforces frozen code/stage schema across `cli test` and `cli verify`.
- Legacy verification API (`run_verification_suite(...)`) and orphaned load placeholders were removed.
- Duplicate worker-resolution helpers were consolidated into `src/slope_stab/execution/worker_policy.py`.
- README now includes explicit breaking-change migration notes.

Validation outcome:

- `python -m slope_stab.cli verify --output tmp/verify_repo_health_fix.json` passed (`all_passed: true`).
- `python -m slope_stab.cli test --output tmp/test_repo_health_fix.json` passed (`all_passed: true`) after one timeout-retry with larger budget, consistent with gate timeout policy.

Lessons learned:

- Modeling startup and runtime failure boundaries as separate exception paths makes fallback policy deterministic and testable.
- Structured command errors reduce CLI ambiguity and improve automation reliability.

## Context and Orientation

This plan touches four areas.

First, unittest orchestration in `src/slope_stab/testing/unittest_runner.py` discovers targets, decides serial versus process execution, and returns `UnittestRunResult`. Discovery currently happens without a guard around `loader.discover(...)`, so invalid discovery inputs raise exceptions directly before result construction.

Second, verification orchestration in `src/slope_stab/verification/runner.py` follows a parallel/serial decision pattern similar to unittest orchestration. Its `_evaluate_cases_parallel(...)` helper wraps all worker exceptions in `RuntimeError`, but outer fallback logic catches only `OSError`/`PermissionError`, creating inconsistent effective behavior and unclear startup-versus-runtime boundaries.

Third, unit tests in `tests/unit/test_unittest_runner_workers.py` and `tests/unit/test_verification_runner_workers.py` currently mock private `_evaluate_*_parallel` helpers to throw `PermissionError`, which bypasses the real exception-wrapping behavior and overstates fallback coverage.

Fourth, lightweight cleanup opportunities exist in duplicate CPU/worker utility logic across `search.auto_parallel_policy`, `verification.runner`, and `testing.unittest_runner`.

Fifth, this plan now introduces a shared error contract module (target path: `src/slope_stab/errors/contracts.py`) so command outputs use one stable machine-readable error schema with a frozen code enum and stage classification.

## Plan of Work

Milestone 1 resolves discovery robustness in unittest orchestration. Add a guarded discovery phase around `_discover_target_modules(...)` in `run_unittest_suite_with_execution(...)`. When discovery fails, return a populated `UnittestRunResult` with empty `targets`, explicit structured `discovery_error`, deterministic serial execution metadata, and no traceback leakage through CLI command paths. Add contract tests that exercise invalid `start_directory` and invalid `top_level_directory` inputs.

Milestone 2 clarifies startup-versus-runtime failure boundaries for verification/unittest parallel execution. Refactor orchestration so startup failures are detected at executor construction/context-entry boundaries and may fallback in auto mode, while worker runtime failures remain hard failures with explicit errors. Remove dead fallback branches or move boundary handling to where startup exceptions are actually observable. Keep behavior aligned with AGENTS.md non-negotiable deterministic failure policy.

Milestone 3 repairs test realism. Replace unit tests that patch private `_evaluate_*_parallel` helpers with tests using lightweight fake executors/futures so startup and runtime boundaries are exercised end-to-end through public orchestration functions. Add explicit assertions for:

- startup failure in auto mode -> deterministic serial fallback metadata;
- runtime worker failure -> deterministic hard failure with explicit error message;
- no silent partial success.

Milestone 4 performs low-risk maintainability cleanup. Consolidate duplicated `effective_*_cpu_count` and `resolve_*_requested_workers` logic into a shared helper used by verification and unittest runners. Remove `loads/null_models.py` and corresponding exports entirely.

Milestone 5 introduces a shared command error contract. Add `src/slope_stab/errors/contracts.py` with a frozen code enum and payload builder for shape:

- `code`: stable machine-readable identifier;
- `message`: human-readable diagnostic string;
- `stage`: one of `discovery`, `startup`, `runtime`, `validation`.

Apply this schema to both unittest and verification command pathways (`cli test` and `cli verify`) and update tests to assert code/stage stability.

Milestone 6 removes legacy verification API surface. Remove `run_verification_suite(...)` from runner module and exports, migrate all internal/tests to `run_verification_suite_with_execution(...)`, and update docs to call out this breaking change with migration guidance.

Milestone 7 runs the full verification gate and closes the plan. Run `python -m slope_stab.cli verify` first, then `python -m slope_stab.cli test`, and capture output artifacts proving no baseline regressions in Bishop/Spencer prescribed and search benchmarks.

## Concrete Steps

Execute from repository root with `PYTHONPATH=src`.

1. Implement discovery guard and new discovery-error contract in:
   - `src/slope_stab/testing/unittest_runner.py`
   - `src/slope_stab/cli.py` (only if command-path adaptation is required)
   - `src/slope_stab/errors/contracts.py`
2. Add/update tests:
   - `tests/unit/test_unittest_runner_workers.py`
   - `tests/unit/test_cli_test_contract.py`
   - `tests/unit/test_cli_verify_contract.py`
3. Refactor verification/unittest startup/runtime boundaries in:
   - `src/slope_stab/verification/runner.py`
   - `src/slope_stab/testing/unittest_runner.py`
4. Update boundary tests:
   - `tests/unit/test_verification_runner_workers.py`
   - `tests/unit/test_unittest_runner_workers.py`
5. Apply shared helper refactor and orphaned-code cleanup:
   - `src/slope_stab/search/auto_parallel_policy.py` (or new shared helper module)
   - `src/slope_stab/verification/runner.py`
   - `src/slope_stab/testing/unittest_runner.py`
   - `src/slope_stab/loads/null_models.py`
   - `src/slope_stab/loads/__init__.py`
6. Remove legacy verification API and update consumers:
   - `src/slope_stab/verification/runner.py`
   - `src/slope_stab/verification/__init__.py`
   - `tests/integration/test_verification_cases.py`
7. Update breaking-change docs:
   - `README.md`
8. Run validation commands:
   - `python -m slope_stab.cli verify --output tmp/verify_repo_health_fix.json`
   - `python -m slope_stab.cli test --output tmp/test_repo_health_fix.json`

Expected artifacts:

- `tmp/verify_repo_health_fix.json`
- `tmp/test_repo_health_fix.json`

## Validation and Acceptance

Acceptance requires all of the following:

1. Discovery failures in `run_unittest_suite_with_execution(...)` no longer raise uncaught exceptions; they return structured error metadata and `all_passed == False`.
2. Verification/unittest orchestration has explicit, tested behavior:
   - startup failures in auto mode may fall back to serial (policy-aligned),
   - runtime worker failures do not silently fall back.
3. Updated unit tests validate real control flow rather than private-function mocks that bypass exception translation.
4. `cli test` and `cli verify` error payloads use the shared schema (`code`, `message`, `stage`) with frozen enumerated codes validated by tests.
5. Legacy `run_verification_suite(...)` API is removed and no remaining internal/tests import it.
6. Placeholder load-model symbols are removed entirely and no runtime/tests reference them.
7. Full gate passes:
   - `python -m slope_stab.cli verify` returns `all_passed: true`
   - `python -m slope_stab.cli test` returns `all_passed: true`
8. No changes to benchmark targets, tolerances, or prescribed solver numerical baselines.

## Idempotence and Recovery

All planned edits are code-only and can be reapplied safely. If a refactor introduces regressions, revert milestone-by-milestone while retaining test additions that document intended behavior. Keep recovery granular by committing each milestone separately after local validation.

## Artifacts and Notes

Repro snippets captured during review:

- Discovery crash:
  - `run_unittest_suite_with_execution(start_directory='tests/does_not_exist', top_level_directory='.')`
  - observed `ImportError: Start directory is not importable`.

- Wrapped-exception fallback mismatch:
  - Fake process executor futures raising `PermissionError` inside `_evaluate_cases_parallel(...)` and `_evaluate_targets_parallel(...)` produced wrapped `RuntimeError` and bypassed outer `(OSError, PermissionError)` fallback blocks.

Plan revision note (2026-04-08): Added initial plan after repository review and reproducible runner robustness findings; implementation not started.

Plan revision note (2026-04-08, post grilling decisions): Updated scope to include immediate breaking API removals (`run_verification_suite`, load null placeholders), shared frozen error-contract module with schema `{code,message,stage}` applied across `cli test` and `cli verify`, structured discovery errors, and required README breaking-change documentation.

Plan revision note (2026-04-08, implementation complete): Shipped runner/CLI/error-contract/worker-policy changes, removed legacy/orphaned API surfaces, updated docs and bug ledger, and passed required verify+test gates with recorded artifacts.
