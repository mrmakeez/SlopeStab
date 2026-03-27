# Codex Execution Plans (ExecPlans):

This document describes the requirements for an execution plan ("ExecPlan"), a design document that a coding agent can follow to deliver a working feature or system change. Treat the reader as a complete beginner to this repository: they have only the current working tree and the single ExecPlan file you provide. There is no memory of prior plans and no external context.

## How to use ExecPlans and PLANS.md

When authoring an executable specification (ExecPlan), follow PLANS.md _to the letter_. If it is not in your context, refresh your memory by reading the entire PLANS.md file. Be thorough in reading (and re-reading) source material to produce an accurate specification. When creating a spec, start from the skeleton and flesh it out as you do your research.

When implementing an executable specification (ExecPlan), do not prompt the user for "next steps"; simply proceed to the next milestone. Keep all sections up to date, add or split entries in the list at every stopping point to affirmatively state the progress made and next steps. Resolve ambiguities autonomously, and commit frequently.

When discussing an executable specification (ExecPlan), record decisions in a log in the spec for posterity; it should be unambiguously clear why any change to the specification was made. ExecPlans are living documents, and it should always be possible to restart from _only_ the ExecPlan and no other work.

When researching a design with challenging requirements or significant unknowns, use milestones to implement proof of concepts, "toy implementations", etc., that allow validating whether the user's proposal is feasible. Read the source code of libraries by finding or acquiring them, research deeply, and include prototypes to guide a fuller implementation.

## Requirements

NON-NEGOTIABLE REQUIREMENTS:

* Every ExecPlan must be fully self-contained. Self-contained means that in its current form it contains all knowledge and instructions needed for a novice to succeed.
* Every ExecPlan is a living document. Contributors are required to revise it as progress is made, as discoveries occur, and as design decisions are finalized. Each revision must remain fully self-contained.
* Every ExecPlan must enable a complete novice to implement the feature end-to-end without prior knowledge of this repo.
* Every ExecPlan must produce a demonstrably working behavior, not merely code changes to "meet a definition".
* Every ExecPlan must define every term of art in plain language or do not use it.

Purpose and intent come first. Begin by explaining, in a few sentences, why the work matters from a user's perspective: what someone can do after this change that they could not do before, and how to see it working. Then guide the reader through the exact steps to achieve that outcome, including what to edit, what to run, and what they should observe.

The agent executing your plan can list files, read files, search, run the project, and run tests. It does not know any prior context and cannot infer what you meant from earlier milestones. Repeat any assumption you rely on. Do not point to external blogs or docs; if knowledge is required, embed it in the plan itself in your own words. If an ExecPlan builds upon a prior ExecPlan and that file is checked in, incorporate it by reference. If it is not, you must include all relevant context from that plan.

## Formatting

Format and envelope are simple and strict. Each ExecPlan must be one single fenced code block labeled as `md` that begins and ends with triple backticks. Do not nest additional triple-backtick code fences inside; when you need to show commands, transcripts, diffs, or code, present them as indented blocks within that single fence. Use indentation for clarity rather than code fences inside an ExecPlan to avoid prematurely closing the ExecPlan's code fence. Use two newlines after every heading, use # and ## and so on, and correct syntax for ordered and unordered lists.

When writing an ExecPlan to a Markdown (.md) file where the content of the file *is only* the single ExecPlan, you should omit the triple backticks.

Write in plain prose. Prefer sentences over lists. Avoid checklists, tables, and long enumerations unless brevity would obscure meaning. Checklists are permitted only in the `Progress` section, where they are mandatory. Narrative sections must remain prose-first.

## Guidelines

Self-containment and plain language are paramount. If you introduce a phrase that is not ordinary English ("daemon", "middleware", "RPC gateway", "filter graph"), define it immediately and remind the reader how it manifests in this repository (for example, by naming the files or commands where it appears). Do not say "as defined previously" or "according to the architecture doc." Include the needed explanation here, even if you repeat yourself.

Avoid common failure modes. Do not rely on undefined jargon. Do not describe "the letter of a feature" so narrowly that the resulting code compiles but does nothing meaningful. Do not outsource key decisions to the reader. When ambiguity exists, resolve it in the plan itself and explain why you chose that path. Err on the side of over-explaining user-visible effects and under-specifying incidental implementation details.

Anchor the plan with observable outcomes. State what the user can do after implementation, the commands to run, and the outputs they should see. Acceptance should be phrased as behavior a human can verify ("after starting the server, navigating to [http://localhost:8080/health](http://localhost:8080/health) returns HTTP 200 with body OK") rather than internal attributes ("added a HealthCheck struct"). If a change is internal, explain how its impact can still be demonstrated (for example, by running tests that fail before and pass after, and by showing a scenario that uses the new behavior).

Specify repository context explicitly. Name files with full repository-relative paths, name functions and modules precisely, and describe where new files should be created. If touching multiple areas, include a short orientation paragraph that explains how those parts fit together so a novice can navigate confidently. When running commands, show the working directory and exact command line. When outcomes depend on environment, state the assumptions and provide alternatives when reasonable.

Be idempotent and safe. Write the steps so they can be run multiple times without causing damage or drift. If a step can fail halfway, include how to retry or adapt. If a migration or destructive operation is necessary, spell out backups or safe fallbacks. Prefer additive, testable changes that can be validated as you go.

Validation is not optional. Include instructions to run tests, to start the system if applicable, and to observe it doing something useful. Describe comprehensive testing for any new features or capabilities. Include expected outputs and error messages so a novice can tell success from failure. Where possible, show how to prove that the change is effective beyond compilation (for example, through a small end-to-end scenario, a CLI invocation, or an HTTP request/response transcript). State the exact test commands appropriate to the project's toolchain and how to interpret their results.

Capture evidence. When your steps produce terminal output, short diffs, or logs, include them inside the single fenced block as indented examples. Keep them concise and focused on what proves success. If you need to include a patch, prefer file-scoped diffs or small excerpts that a reader can recreate by following your instructions rather than pasting large blobs.

## Milestones

Milestones are narrative, not bureaucracy. If you break the work into milestones, introduce each with a brief paragraph that describes the scope, what will exist at the end of the milestone that did not exist before, the commands to run, and the acceptance you expect to observe. Keep it readable as a story: goal, work, result, proof. Progress and milestones are distinct: milestones tell the story, progress tracks granular work. Both must exist. Never abbreviate a milestone merely for the sake of brevity, do not leave out details that could be crucial to a future implementation.

Each milestone must be independently verifiable and incrementally implement the overall goal of the execution plan.

## Living plans and design decisions

* ExecPlans are living documents. As you make key design decisions, update the plan to record both the decision and the thinking behind it. Record all decisions in the `Decision Log` section.
* ExecPlans must contain and maintain a `Progress` section, a `Surprises & Discoveries` section, a `Decision Log`, and an `Outcomes & Retrospective` section. These are not optional.
* When you discover optimizer behavior, performance tradeoffs, unexpected bugs, or inverse/unapply semantics that shaped your approach, capture those observations in the `Surprises & Discoveries` section with short evidence snippets (test output is ideal).
* If you change course mid-implementation, document why in the `Decision Log` and reflect the implications in `Progress`. Plans are guides for the next contributor as much as checklists for you.
* At completion of a major task or the full plan, write an `Outcomes & Retrospective` entry summarizing what was achieved, what remains, and lessons learned.

# Prototyping milestones and parallel implementations

It is acceptable---and often encouraged---to include explicit prototyping milestones when they de-risk a larger change. Examples: adding a low-level operator to a dependency to validate feasibility, or exploring two composition orders while measuring optimizer effects. Keep prototypes additive and testable. Clearly label the scope as "prototyping"; describe how to run and observe results; and state the criteria for promoting or discarding the prototype.

Prefer additive code changes followed by subtractions that keep tests passing. Parallel implementations (e.g., keeping an adapter alongside an older path during migration) are fine when they reduce risk or enable tests to continue passing during a large migration. Describe how to validate both paths and how to retire one safely with tests. When working with multiple new libraries or feature areas, consider creating spikes that evaluate the feasibility of these features _independently_ of one another, proving that the external library performs as expected and implements the features we need in isolation.

## Skeleton of a Good ExecPlan

    # <Short, action-oriented description>

    This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

    If PLANS.md file is checked into the repo, reference the path to that file here from the repository root and note that this document must be maintained in accordance with PLANS.md.

    ## Purpose / Big Picture

    Explain in a few sentences what someone gains after this change and how they can see it working. State the user-visible behavior you will enable.

    ## Progress

    Use a list with checkboxes to summarize granular steps. Every stopping point must be documented here, even if it requires splitting a partially completed task into two ("done" vs. "remaining"). This section must always reflect the actual current state of the work.

    - [x] (2025-10-01 13:00Z) Example completed step.
    - [ ] Example incomplete step.
    - [ ] Example partially completed step (completed: X; remaining: Y).

    Use timestamps to measure rates of progress.

    ## Surprises & Discoveries

    Document unexpected behaviors, bugs, optimizations, or insights discovered during implementation. Provide concise evidence.

    - Observation: ...
      Evidence: ...

    ## Decision Log

    Record every decision made while working on the plan in the format:

    - Decision: ...
      Rationale: ...
      Date/Author: ...

    ## Outcomes & Retrospective

    Summarize outcomes, gaps, and lessons learned at major milestones or at completion. Compare the result against the original purpose.

    ## Context and Orientation

    Describe the current state relevant to this task as if the reader knows nothing. Name the key files and modules by full path. Define any non-obvious term you will use. Do not refer to prior plans.

    ## Plan of Work

    Describe, in prose, the sequence of edits and additions. For each edit, name the file and location (function, module) and what to insert or change. Keep it concrete and minimal.

    ## Concrete Steps

    State the exact commands to run and where to run them (working directory). When a command generates output, show a short expected transcript so the reader can compare. This section must be updated as work proceeds.

    ## Validation and Acceptance

    Describe how to start or exercise the system and what to observe. Phrase acceptance as behavior, with specific inputs and outputs. If tests are involved, say "run <project's test command> and expect <N> passed; the new test <name> fails before the change and passes after>".

    ## Idempotence and Recovery

    If steps can be repeated safely, say so. If a step is risky, provide a safe retry or rollback path. Keep the environment clean after completion.

    ## Artifacts and Notes

    Include the most important transcripts, diffs, or snippets as indented examples. Keep them concise and focused on what proves success.

    ## Interfaces and Dependencies

    Be prescriptive. Name the libraries, modules, and services to use and why. Specify the types, traits/interfaces, and function signatures that must exist at the end of the milestone. Prefer stable names and paths such as `crate::module::function` or `package.submodule.Interface`. E.g.:

    In crates/foo/planner.rs, define:

        pub trait Planner {
            fn plan(&self, observed: &Observed) -> Vec<Action>;
        }

If you follow the guidance above, a single, stateless agent -- or a human novice -- can read your ExecPlan from top to bottom and produce a working, observable result. That is the bar: SELF-CONTAINED, SELF-SUFFICIENT, NOVICE-GUIDING, OUTCOME-FOCUSED.

When you revise a plan, you must ensure your changes are comprehensively reflected across all sections, including the living document sections, and you must write a note at the bottom of the plan describing the change and the reason why. ExecPlans must describe not just the what but the why for almost everything.

## Active ExecPlans

```md
# Implement Slide2-Style Auto-Refine Circular Search with Case 3 and Case 4 Parity Gates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and must be maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Users can run either prescribed-surface Bishop analysis or deterministic auto-refine circular search from the same `analyze` input flow. The search path reports the governing surface and per-iteration diagnostics, while preserving existing Case 1 and Case 2 prescribed verification behavior.

## Progress

- [x] (2026-03-13 23:27 +13:00) Reviewed current architecture and confirmed the existing analysis path is prescribed-surface only (`src/slope_stab/analysis.py`) and search namespace is a placeholder (`src/slope_stab/search/__init__.py`).
- [x] (2026-03-13 23:27 +13:00) Extracted Case 3 reference values from `Verification/Bishop/Case 3/Case3/Case3-i.rfcreport` and `.s01`, including search settings, global minimum surface, and valid-surface counts.
- [x] (2026-03-13 23:27 +13:00) Reviewed Slide2 auto-refine documentation page and captured algorithm statements plus known ambiguities.
- [x] (2026-03-14 00:17 +13:00) Confirmed owner decisions for input contract, limits defaults, deterministic behavior, diagnostic-only metrics, and verification placement.
- [x] (2026-03-14 00:17 +13:00) Implemented model and IO interfaces for an auto-refine search input path without regressing prescribed analysis.
- [x] (2026-03-14 00:17 +13:00) Implemented deterministic auto-refine circular search and integrated with Bishop solver dispatch.
- [x] (2026-03-14 00:17 +13:00) Added Case 3 fixture and separate unit/regression tests, including parser and deterministic repeatability coverage.
- [x] (2026-03-14 00:17 +13:00) Ran required verification gate and full test discovery; all passed.
- [x] (2026-03-14 01:13 +13:00) Added Case 4 fixture (`tests/fixtures/case4_auto_refine.json`) and Case 4 parity regression (`tests/regression/test_case4_auto_refine.py`) with the same hard/diagnostic gate policy as Case 3.
- [x] (2026-03-14 01:13 +13:00) Extended deterministic search refinement to better cover low-angle circular families and toe-anchored entry behavior needed for Case 4 parity while keeping baseline verification unchanged.
- [x] (2026-03-14 01:13 +13:00) Re-ran required gate and full test discovery after Case 4 integration; all passed.
- [x] (2026-03-14 15:05 +13:00) Promoted Case 3 and Case 4 parity into built-in `python -m slope_stab.cli verify` with typed verification case handling.
- [x] (2026-03-14 15:05 +13:00) Redesigned `cli verify` output to use per-case typed payloads (`case_type`, `solver`, `hard_checks`, `diagnostics`) while preserving top-level `all_passed`.
- [x] (2026-03-14 15:05 +13:00) Updated docs (`AGENTS.md`, `README.md`, `docs/auto-refine-explainer.md`) and verification tests to match built-in Case 1-4 scope.
- [x] (2026-03-14 15:05 +13:00) Closed this ExecPlan after full verify + unittest gate success.

## Surprises & Discoveries

- Observation: Case 3 includes finite Slide2 model boundaries, even though current code uses infinite toe/crest profile conventions.
  Evidence: `External Boundary` table in `Verification/Bishop/Case 3/Case3/Case3-i.rfcreport` lists points `(70,20)`, `(70,35)`, `(50,35)`, `(30,25)`, `(20,25)`, `(20,20)`.

- Observation: Case 3 `.s01` confirms exactly `19000` generated three-point surfaces and `9696` valid surfaces, with global minimum matching the report.
  Evidence: `* #three point surfaces 19000`, and parsing all `surface 0 data` rows gives min FS `0.986442` at center `(30.259066..., 51.791949...)`.

- Observation: Slide2 doc text explains the iterative refine workflow but leaves several implementation details implicit (exact random-point generation and refinement polyline construction details).
  Evidence: Doc states circles are generated from random points and later divisions are generated on an interpolated polyline through low-FOS divisions, but equation images and averaging details are not fully textual on the page.

- Observation: Straight iterative narrowing could drift away from toe/crest-adjacent minima for Case 3-like geometry.
  Evidence: Deterministic refinement improved parity when a bounded toe/crest local refinement pass was added after core iterations.

- Observation: The previous tangent-angle lower-bound logic could exclude Case 4's Slide2 critical surface family.
  Evidence: Case 4 expected geometry (`r = 43.234`, endpoints near `(30,25)` and `(58.068,45)`) implies a lower half-angle than the chord slope angle; enforcing `theta_min = chord slope` prevented those circles from being sampled.

- Observation: Case 4 parity is highly sensitive to endpoint handling near the toe.
  Evidence: Anchoring left endpoint at the toe and re-sweeping beta against the selected right endpoint reduced Case 4 FOS error from about `0.0555` to within the `0.001` gate.

## Decision Log

- Decision: Preserve the current prescribed-surface path as an unchanged baseline and add auto-refine behind an isolated search path.
  Rationale: AGENTS.md mandates verification-first behavior and no baseline regressions.
  Date/Author: 2026-03-13 / Codex

- Decision: Case 3 parity gates should prioritize global minimum FOS and entry/exit coordinates first, then radius/center and surface-count diagnostics second.
  Rationale: This aligns with user intent and directly validates practical design outcomes (critical surface location and safety factor).
  Date/Author: 2026-03-13 / Codex

- Decision: Treat Slide2 total-surface formula as inferred behavior pending confirmation (`surfaces_per_iteration = y * x * (x - 1) / 2`; total multiplied by iteration count `z`).
  Rationale: This inference matches Case 3 counts exactly: `20 * 19 / 2 * 10 * 10 = 19000`.
  Date/Author: 2026-03-13 / Codex

- Decision: Extend existing `analyze` input schema instead of adding a separate CLI command.
  Rationale: Maintains one analysis entrypoint with explicit mode selection and preserves backward compatibility.
  Date/Author: 2026-03-14 / Codex

- Decision: Search limits are optional in input with defaults `x_toe - H` and `x_crest + 2H`.
  Rationale: Matches approved behavior and keeps inputs concise for common cases.
  Date/Author: 2026-03-14 / Codex

- Decision: Keep auto-refine deterministic without random seed fields.
  Rationale: Owner requested deterministic behavior and no random-seeding input for this feature.
  Date/Author: 2026-03-14 / Codex

- Decision: Keep `valid_surfaces` and center-distance parity as diagnostic-only.
  Rationale: Owner selected them as monitoring diagnostics, not hard gates.
  Date/Author: 2026-03-14 / Codex

- Decision: Promote Case 3 and Case 4 parity into built-in `cli verify` while keeping separate parity regressions.
  Rationale: Enforces auto-refine parity in the default verification gate and retains dedicated diagnostics for debugging drift.
  Date/Author: 2026-03-14 / Codex + Project Owner

- Decision: Redesign `cli verify` case payloads to be type-specific.
  Rationale: Prescribed benchmark and auto-refine parity checks need different hard-check structures; typed payloads make the contract explicit.
  Date/Author: 2026-03-14 / Codex + Project Owner

- Decision: Expand tangent-angle generation to always cover `(eps, 90 deg - eps)` and add a toe-locked beta refinement pass after toe/crest refinement.
  Rationale: This deterministic extension admits the Case 4 Slide2 circle family and reaches Case 3 and Case 4 parity gates without introducing randomness.
  Date/Author: 2026-03-14 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- Added search-capable input schema (`search.method = auto_refine_circular`) while preserving prescribed mode compatibility.
- Implemented deterministic auto-refine circular search with per-iteration diagnostics.
- Integrated search dispatch into analysis workflow and metadata output.
- Added unit tests for parser behavior, default limits, per-iteration surface counts, and deterministic repeatability.
- Added separate Case 3 parity regression test.
- Added separate Case 4 parity regression test using the same hard/diagnostic gate structure as Case 3.
- Added deterministic low-angle and toe-locked refinement coverage in search to satisfy both Case 3 and Case 4 parity gates.
- Promoted Case 3 and Case 4 into built-in `cli verify` with type-aware verification checks.
- Updated `cli verify` JSON output contract to type-specific case payloads.
- Updated verification documentation to state built-in Case 1-4 coverage.
- Ran required gate and full test discovery with passing results.

Gaps intentionally left:

- Additional/alternative search methods remain deferred.

Plan status: Closed.

## Context and Orientation

Current baseline flow:

`src/slope_stab/io/json_io.py` now parses mutually exclusive modes: prescribed-surface or search.
`src/slope_stab/analysis.py` dispatches to prescribed solving or auto-refine search and returns one governing result.
`src/slope_stab/search/auto_refine.py` contains deterministic search logic and diagnostics.
`src/slope_stab/verification/cases.py` now contains typed verification definitions for Case 1-4 (prescribed benchmarks and auto-refine parity cases).

Case 3 reference artifacts:

- `Verification/Bishop/Case 3/Case3/Case3-i.rfcreport`
- `Verification/Bishop/Case 3/Case3/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`
- `Verification/Bishop/Case 3/Case3.slmd`
- `Verification/Bishop/Case 3/Case 3.pdf`

Case 3 target values captured from report/output:

- Search method: Auto Refine Search
- Divisions along slope: `20`
- Circles per division: `10`
- Iterations: `10`
- Divisions to use next iteration: `50%`
- Global minimum FS: `0.986442`
- Center: `(30.259, 51.792)`
- Radius: `26.793`
- Endpoints: left `(30.000, 25.000)`, right `(51.137, 35.000)`
- Valid surfaces: `9696`, invalid surfaces: `0`
- Total generated three-point surfaces: `19000`

Case 4 reference artifacts:

- `Verification/Bishop/Case 4/Case4/Case4-i.rfcreport`
- `Verification/Bishop/Case 4/Case4.slmd`
- `Verification/Bishop/Case 4/Case 4.pdf`

Case 4 target values captured from report/output:

- Search method: Auto Refine Search
- Divisions along slope: `30`
- Circles per division: `15`
- Iterations: `15`
- Divisions to use next iteration: `50%`
- Global minimum FS: `1.234670`
- Center: `(21.024, 67.292)`
- Radius: `43.234`
- Endpoints: left `(30.000, 25.000)`, right `(58.068, 45.000)`
- Valid surfaces: `38360`, invalid surfaces: `0`

## Plan of Work

Implemented sequence:

1. Added additive interfaces and parser validation for search mode.
2. Implemented deterministic auto-refine search path and diagnostics.
3. Integrated dispatch and output metadata without altering prescribed verification behavior.
4. Added separate Case 3 fixture and tests.
5. Added separate Case 4 fixture and parity regression test with matching gates.
6. Refined deterministic search angle/refinement handling to satisfy Case 4 parity while preserving Case 3 parity and baseline verification.
7. Promoted Case 3/4 parity checks into built-in verification and updated typed verify output payloads.
8. Updated docs and validation tests for Case 1-4 built-in verification scope.
9. Validated against required gate and full test suite.

## Concrete Steps

Run all commands from repository root:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Baseline safety check before code edits:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Run targeted search coverage:

    python -m unittest discover -s tests -p "test_*.py" -k auto_refine
    python -m slope_stab.cli analyze --input tests/fixtures/case3_auto_refine.json
    python -m slope_stab.cli analyze --input tests/fixtures/case4_auto_refine.json

Run full verification gate:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Expected high-level transcript markers after completion:

    verify output reports all_passed=true for Case 1, Case 2, Case 3, and Case 4.
    case3 and case4 regression tests pass in unittest discovery and enforce parity gates.

## Validation and Acceptance

Non-regression gates (hard):

- Existing Case 1 and Case 2 verification values and tolerances remain exactly unchanged.
- Built-in `python -m slope_stab.cli verify` passes all four cases.
- Existing verification and unit/regression commands complete successfully.

Case 3 parity gates (hard):

- `abs(FOS - 0.986442) <= 0.001`
- endpoint coordinate absolute error <= `0.20 m` for each of `x_left, y_left, x_right, y_right`
- radius relative error <= `10%`

Case 3 diagnostic-only parity metrics:

- center distance
- valid/invalid surface counts

Case 4 parity gates (hard):

- `abs(FOS - 1.234670) <= 0.001`
- endpoint coordinate absolute error <= `0.20 m` for each of `x_left, y_left, x_right, y_right`
- radius relative error <= `10%`

Case 4 diagnostic-only parity metrics:

- center distance
- valid/invalid surface counts

## Idempotence and Recovery

Documentation and tests are rerunnable. Preserve Case 1/Case 2 benchmark values and keep search changes isolated from prescribed solver behavior.

## Artifacts and Notes

Case 3 extracted reference snippet:

    Search Method: Auto Refine Search
    Divisions along slope: 20
    Circles per division: 10
    Number of iterations: 10
    Divisions to use in next iteration: 50%
    FS: 0.986442
    Center: 30.259, 51.792
    Radius: 26.793
    Left Endpoint: 30.000, 25.000
    Right Endpoint: 51.137, 35.000
    Number of Valid Surfaces: 9696

Case 3 external boundary snippet:

    70,20
    70,35
    50,35
    30,25
    20,25
    20,20

Case 4 extracted reference snippet:

    Search Method: Auto Refine Search
    Divisions along slope: 30
    Circles per division: 15
    Number of iterations: 15
    Divisions to use in next iteration: 50%
    FS: 1.234670
    Center: 21.024, 67.292
    Radius: 43.234
    Left Endpoint: 30.000, 25.000
    Right Endpoint: 58.068, 45.000
    Number of Valid Surfaces: 38360

## Interfaces and Dependencies

Implemented interfaces in `src/slope_stab/models.py`:

    @dataclass(frozen=True)
    class SearchLimitsInput:
        x_min: float
        x_max: float

    @dataclass(frozen=True)
    class AutoRefineSearchInput:
        divisions_along_slope: int
        circles_per_division: int
        iterations: int
        divisions_to_use_next_iteration_pct: float
        search_limits: SearchLimitsInput

    @dataclass(frozen=True)
    class SearchInput:
        method: str
        auto_refine_circular: AutoRefineSearchInput

Implemented search entrypoint in `src/slope_stab/search/auto_refine.py`:

    def run_auto_refine_search(
        profile: UniformSlopeProfile,
        config: AutoRefineSearchInput,
        evaluate_surface: SurfaceEvaluator,
    ) -> AutoRefineSearchResult:
        ...

Output includes winning prescribed circle, FOS result, generated/valid/invalid counts, and per-iteration diagnostics.

Dependency policy: use only Python standard library and existing repository modules; no new external packages are required for this feature.

Plan revision note: Updated on 2026-03-14 to promote Case 3/4 parity into built-in `cli verify`, redesign typed verify payloads, and close the active plan after passing full validation.
```

```md
# Implement Deterministic DIRECT Global Circular Search with Cases 2-4 Benchmark Gates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were maintained through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and maintained in accordance with `PLANS.md`.

## Purpose / Big Picture

Users can now run a deterministic global circular search (`search.method = direct_global_circular`) in the same analysis flow as prescribed and auto-refine modes. The direct-global path exposes DIRECT-style search diagnostics and is verified against benchmark margin checks for Cases 2-4 while preserving baseline Case 1-4 behavior.

## Progress

- [x] (2026-03-14 20:05 +13:00) Added additive direct-global method path and initial benchmark-gate verification scaffolding.
- [x] (2026-03-14 21:02 +13:00) Replaced wrapper behavior with true deterministic DIRECT rectangle search over normalized 3-parameter circular space.
- [x] (2026-03-14 21:02 +13:00) Migrated `direct_global_circular` input schema to DIRECT-specific fields (`max_iterations`, `max_evaluations`, `min_improvement`, `stall_iterations`, `min_rectangle_half_size`, `search_limits`).
- [x] (2026-03-14 21:02 +13:00) Emitted DIRECT-specific metadata (`total_evaluations`, `valid_evaluations`, `infeasible_evaluations`, `termination_reason`, per-iteration diagnostics).
- [x] (2026-03-14 21:02 +13:00) Added deterministic toe/crest polishing after global DIRECT exploration to satisfy benchmark quality gates.
- [x] (2026-03-14 21:02 +13:00) Updated fixtures/tests/verification cases for direct-global schema and margin gate policy.
- [x] (2026-03-14 21:20 +13:00) Updated docs/governance artifacts (`docs/direct-global-explainer.md`, `AGENTS.md`, `README.md`, and this plan) and re-ran required gate.

## Surprises & Discoveries

- Observation: A naive potentially-optimal selector collapsed to one rectangle per iteration and behaved like local search.
  Evidence: Early runs terminated with good Case 2 but poor Case 3/4 FOS values despite increased evaluation budgets.

- Observation: Initialization from only one center (`u = 0.5, 0.5, 0.5`) under-covered the domain.
  Evidence: Global benchmark tests improved after deterministic 3x3x3 seeding.

- Observation: DIRECT global phase alone still missed benchmark-quality minima in toe/crest-sensitive families.
  Evidence: Cases 3/4 remained above target margin until deterministic toe/crest and toe-locked post-polish was applied.

## Decision Log

- Decision: Keep direct-global additive and do not modify prescribed or auto-refine baseline logic.
  Rationale: Verification-first policy and Case 1/2 benchmark immutability.
  Date/Author: 2026-03-14 / Codex

- Decision: Use DIRECT-specific JSON fields for `direct_global_circular` instead of reusing auto-refine controls.
  Rationale: Makes global optimizer intent explicit and avoids semantic overload.
  Date/Author: 2026-03-14 / Codex + Project Owner

- Decision: Preserve benchmark acceptance gate as `FOS(method) <= FOS(benchmark) + 0.01` for Cases 2-4.
  Rationale: Approved rollout gate balancing stability and quality.
  Date/Author: 2026-03-14 / Project Owner

- Decision: Apply deterministic post-polish after DIRECT global loop.
  Rationale: Restores benchmark quality for known toe/crest-sensitive basins while keeping deterministic behavior.
  Date/Author: 2026-03-14 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- True deterministic DIRECT search implemented for `direct_global_circular`.
- DIRECT-specific schema and metadata contract implemented.
- Built-in verification now includes Cases 2-4 global benchmark entries with hard margin checks.
- Regression tests enforce validity guards and repeatability for direct-global cases.
- Required full verification gate passed after implementation.

Residual gaps:

- Additional search methods beyond auto-refine and direct-global remain deferred.
- Performance tuning can continue in future work without altering current acceptance gates.

Plan status: Closed.

## Context and Orientation

Core implementation files:

- `src/slope_stab/search/direct_global.py` (DIRECT engine and diagnostics)
- `src/slope_stab/io/json_io.py` (direct-global schema parsing/validation)
- `src/slope_stab/analysis.py` (method dispatch and metadata emission)
- `src/slope_stab/verification/cases.py` and `src/slope_stab/verification/runner.py` (benchmark gate definitions and evaluation)

## Plan of Work

Implemented in sequence:

1. Introduced direct-global schema and parser validation.
2. Implemented DIRECT rectangle search core with deterministic selection, subdivision, and caching.
3. Added direct-global runtime metadata and iteration diagnostics output.
4. Added deterministic post-polish passes to improve benchmark convergence behavior.
5. Updated benchmark fixtures/cases/tests and validated with targeted and full gates.
6. Updated repository docs/governance files to reflect shipped behavior.

## Concrete Steps

Run from repository root:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Targeted:

    $env:PYTHONPATH='src'; python -m unittest tests.unit.test_search_auto_refine
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_global_search_benchmark
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_cli_verify

Required gate:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

## Validation and Acceptance

Hard acceptance checks met:

- Case 1-4 baseline verification remained passing.
- Cases 2-4 direct-global benchmark cases passed `FOS(method) <= FOS(benchmark) + 0.01`.
- Direct-global regressions confirmed deterministic repeatability and validity guards.
- Full `cli verify` and full `unittest discover` passed.

## Idempotence and Recovery

All docs/tests/verification commands are rerunnable. If future tuning regresses Case 1/2 benchmarks or Case 2-4 direct-global margin checks, treat as regression and fix search path behavior rather than loosening gates.

## Artifacts and Notes

Representative verify evidence after closure:

    all_passed: true
    case_type: prescribed_benchmark (Case 1, Case 2)
    case_type: auto_refine_parity (Case 3, Case 4)
    case_type: global_search_benchmark (Case 2, Case 3, Case 4)

    Case 2 (Global Search Benchmark): fos 2.1068669 <= 2.12283
    Case 3 (Global Search Benchmark): fos 0.9855736 <= 0.996442
    Case 4 (Global Search Benchmark): fos 1.2350334 <= 1.24467

## Interfaces and Dependencies

Implemented direct-global interface:

    @dataclass(frozen=True)
    class DirectGlobalSearchInput:
        max_iterations: int
        max_evaluations: int
        min_improvement: float
        stall_iterations: int
        min_rectangle_half_size: float
        search_limits: SearchLimitsInput

Implemented direct-global runtime result:

    @dataclass(frozen=True)
    class DirectGlobalSearchResult:
        winning_surface: PrescribedCircleInput
        winning_result: AnalysisResult
        iteration_diagnostics: list[DirectIterationDiagnostics]
        total_evaluations: int
        valid_evaluations: int
        infeasible_evaluations: int
        termination_reason: str

No external dependencies were added.

Plan revision note: Added on 2026-03-14 to document completed DIRECT implementation, benchmark-gate verification, and release-alignment documentation updates.
```

```md
# Implement Seeded Cuckoo Global Circular Search with Oracle Global-Minimum Gates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were maintained through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and maintained in accordance with `PLANS.md`.

## Purpose / Big Picture

Users can now run seeded stochastic cuckoo global circular search (`search.method = cuckoo_global_circular`) in the same analysis flow as prescribed, auto-refine, and direct-global modes. The path is additive and exposes search diagnostics while preserving baseline verification behavior.

## Progress

- [x] (2026-03-14 23:xx +13:00) Added additive schema/model support for `cuckoo_global_circular`.
- [x] (2026-03-14 23:xx +13:00) Implemented seeded cuckoo search core with bounded repair, Levy variation, replacement, abandonment/regeneration, caching, and deterministic tie-breaks.
- [x] (2026-03-14 23:xx +13:00) Wired analysis dispatch and metadata output for cuckoo mode.
- [x] (2026-03-14 23:xx +13:00) Added Cases 2-4 cuckoo benchmark checks to built-in `cli verify`.
- [x] (2026-03-14 23:xx +13:00) Added dedicated cuckoo regression tests for benchmark and oracle parity (`test_cuckoo_global_search_benchmark.py`, `test_cuckoo_global_oracle.py`).
- [x] (2026-03-14 23:xx +13:00) Added cuckoo explainer diagrams and corrected SVG slip-surface exits to ground-level endpoints.
- [x] (2026-03-14 23:xx +13:00) Ran required gate successfully (`python -m slope_stab.cli verify`, `python -m unittest discover -s tests -p "test_*.py"`).

## Surprises & Discoveries

- Observation: Dense-grid oracle baselines are useful as bounded empirical references, but coarse grids can remain conservative in narrow low-FOS basins.
  Evidence: Case 4 dense-grid baseline stayed above cuckoo+post-polish minima while benchmark gates remained satisfied.

- Observation: SVG educational diagrams needed explicit endpoint-ground checks to avoid visually incorrect elevated exits.
  Evidence: Initial drafts showed elevated right exits; diagrams were corrected so entry/exit lie on the ground profile.

## Decision Log

- Decision: Keep cuckoo additive as a new method key (`cuckoo_global_circular`) rather than replacing direct-global.
  Rationale: Preserves existing deterministic search baselines and non-regression expectations.
  Date/Author: 2026-03-14 / Codex + Project Owner

- Decision: Use fixed-seed repeatability as the determinism contract for cuckoo.
  Rationale: Cuckoo is stochastic by design; fixed seed gives reproducible verification behavior.
  Date/Author: 2026-03-14 / Codex + Project Owner

- Decision: Verify cuckoo with benchmark margin gates and dedicated oracle regressions.
  Rationale: Provides practical global-search quality checks without over-claiming finite-iteration global-optimality.
  Date/Author: 2026-03-14 / Codex + Project Owner

## Outcomes & Retrospective

Delivered outcomes:

- End-to-end seeded cuckoo global circular search path implemented and documented.
- Built-in verification extended with Cases 2-4 cuckoo benchmark checks.
- Dedicated cuckoo regression tests added for benchmark and oracle diagnostics.
- Required full verification gate passed.

Residual caveat:

- Cuckoo remains a finite-budget stochastic method; verification claims are empirical (benchmark/oracle-gated), not theorem-level finite-iteration guarantees.

Plan status: Closed.

Plan revision note: Added on 2026-03-15 to close the cuckoo implementation in repo-root planning records and align governance docs with shipped behavior.
```

```md
# Implement NumPy/SciPy/pycma Modernization and Redundancy Cleanup

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were maintained through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and maintained in accordance with `PLANS.md`.

## Purpose / Big Picture

Users can run the same analysis and verification workflows with reduced internal duplication, vectorized high-cost solver/slicing internals, and dependency-explicit CMA-ES execution. Existing verification gates remain passing while the optimization/search implementation is cleaner and easier to extend.

## Progress

- [x] (2026-03-18 22:00 +13:00) Captured baseline evidence (`cli verify`, full `unittest discover`, and cProfile top cumulative functions).
- [x] (2026-03-18 22:30 +13:00) Added shared circular-search core (`src/slope_stab/search/common.py`) and migrated direct/cuckoo/cmaes to shared mapping/tie-break/validation helpers.
- [x] (2026-03-18 22:55 +13:00) Vectorized slicing and solver internals using NumPy in `src/slope_stab/slicing/slice_generator.py` and `src/slope_stab/lem_core/bishop.py`.
- [x] (2026-03-18 23:20 +13:00) Removed CMA-ES fallback search/polish branches and replaced them with explicit required-dependency errors in `src/slope_stab/search/cmaes_global.py`.
- [x] (2026-03-18 23:40 +13:00) Refactored repeated search dispatch payload assembly via method registry in `src/slope_stab/analysis.py`.
- [x] (2026-03-18 23:50 +13:00) Unified repeated global benchmark verification case dataclasses into one method-tagged class in `src/slope_stab/verification/cases.py` and simplified runner dispatch.
- [x] (2026-03-18 23:55 +13:00) Added `.gitignore` and removed tracked bytecode/cache artifacts from git index.
- [x] (2026-03-19 00:05 +13:00) Updated governance/docs (`AGENTS.md`, `README.md`, and search explainers).
- [x] (2026-03-19 00:20 +13:00) Re-ran full verification gate and full unittest discovery; all passed.

## Surprises & Discoveries

- Observation: Centralizing candidate validation in one helper increased call concentration but reduced total call volume significantly.
  Evidence: total function calls in cProfile dropped from ~190M baseline to ~73.5M after shared helper + vectorization.

- Observation: Slicing became materially cheaper after vectorization, while bishop became the dominant hotspot.
  Evidence: `generate_vertical_slices` cumulative time reduced from ~42.1s baseline profile to ~31.7s post-change profile.

- Observation: Removing fallback branches required tightening documentation language that previously implied fallback behavior.
  Evidence: `docs/cmaes-global-explainer.md` Stage 3 wording updated to remove fallback references and call out required deps.

## Decision Log

- Decision: Keep quality-improve policy while retaining all current benchmark gates.
  Rationale: Approved by project owner; allows better minima without relaxing acceptance criteria.
  Date/Author: 2026-03-18 / User + Codex

- Decision: Require runtime `cma` and `scipy` for CMA-ES path, no runtime fallback algorithms.
  Rationale: Dependencies are present in project config and required by policy choice.
  Date/Author: 2026-03-18 / User + Codex

- Decision: Use qualitative performance evidence instead of fixed percentage SLA.
  Rationale: Approved by project owner for this modernization pass.
  Date/Author: 2026-03-18 / User + Codex

## Outcomes & Retrospective

Delivered outcomes:

- Added a shared search core (`search/common.py`) and removed duplicated mapping/tie-break/validation logic from direct/cuckoo/cmaes modules.
- Vectorized high-cost slicing and bishop internals with NumPy while preserving gate behavior.
- Removed CMA fallback algorithm branches and made missing deps explicit errors.
- Replaced repetitive search dispatch branches in `analysis.py` with method registry handlers while preserving metadata contract.
- Collapsed repeated verification benchmark dataclasses into one method-tagged benchmark type.
- Added `.gitignore` and de-tracked committed bytecode cache artifacts.
- Updated AGENTS/README/explainer docs to match shipped behavior.
- Re-ran required verification gate and full test discovery with passing results.

Residual caveat:

- CMA-ES repeatability remains seed-stable at test tolerances, but as documented, exact bitwise identity across all environments is not guaranteed.

Plan status: Closed.

## Context and Orientation

Primary implementation files:

- `src/slope_stab/search/common.py`
- `src/slope_stab/search/direct_global.py`
- `src/slope_stab/search/cuckoo_global.py`
- `src/slope_stab/search/cmaes_global.py`
- `src/slope_stab/slicing/slice_generator.py`
- `src/slope_stab/lem_core/bishop.py`
- `src/slope_stab/analysis.py`
- `src/slope_stab/verification/cases.py`
- `src/slope_stab/verification/runner.py`
- `AGENTS.md`, `README.md`, and `docs/*-explainer.md`

## Plan of Work

Implemented sequence:

1. Gathered baseline runtime and regression evidence.
2. Centralized shared circular search primitives.
3. Migrated global search methods to shared primitives.
4. Vectorized slice generation and bishop iteration arithmetic.
5. Removed CMA fallback logic and enforced dependency-required behavior.
6. Refactored non-library redundancies (analysis dispatch, verification case duplication, repo hygiene).
7. Updated governance and explainer documentation.
8. Re-ran full verification and test gates.

## Concrete Steps

Run from repository root:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Profiling command used for before/after evidence:

    $env:PYTHONPATH='src'; @'
    import cProfile, pstats, io
    from slope_stab.verification.runner import run_verification_suite
    pr = cProfile.Profile(); pr.enable(); run_verification_suite(); pr.disable()
    s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('cumtime').print_stats(20)
    print(s.getvalue())
    '@ | python -

Structural duplication check command:

    rg "def _map_to_surface|def _circle_from_endpoints_and_tangent|def _surface_key|def _clip01" src/slope_stab/search

Bytecode tracking check command:

    git ls-files | rg "(__pycache__/|\.pyc$)"

## Validation and Acceptance

Hard acceptance checks met:

- `python -m slope_stab.cli verify` passed all 13 built-in cases.
- `python -m unittest discover -s tests -p "test_*.py"` passed (28 tests).
- Case 1/2 benchmark targets/tolerances were not modified.
- Cases 2-4 benchmark gates for direct/cuckoo/cmaes remained passing.
- Deterministic and fixed-seed repeatability regressions remained passing.
- No CMA fallback stage remains; dependency absence now fails explicitly.

Qualitative performance evidence met:

- cProfile total function calls reduced from ~190M to ~73.5M.
- `generate_vertical_slices` cumulative profile time reduced from ~42.1s to ~31.7s.

## Idempotence and Recovery

All commands above are rerunnable. If future tuning regresses verification gates, treat as regression and adjust implementation details rather than loosening benchmark tolerances.

## Artifacts and Notes

Baseline summary:

- `cli verify`: passed
- `unittest discover`: passed
- profile top hotspots included `generate_vertical_slices`, `_slice_area_piecewise`, and `BishopSimplifiedSolver.solve`

Post-change summary:

- `cli verify`: passed
- `unittest discover`: passed
- profile top hotspots shifted to shared candidate evaluation plus bishop and vectorized slicing

## Interfaces and Dependencies

Added shared search interfaces in `src/slope_stab/search/common.py`:

- `map_vector_to_surface(...)`
- `circle_from_endpoints_and_tangent(...)`
- `evaluate_surface_candidate(...)`
- tie-break/repair/round helpers and shared constants

Dependency contract:

- `numpy`, `scipy`, and `cma` are required for optimization path behavior; fallback algorithm branches are removed.

Plan revision note: Added and closed on 2026-03-19 after full implementation, documentation updates, and gate validation.
```

```md
# Implement Final-Iteration M_alpha Validity Gate and Tension-Shear Clamp for Slide2 Parity

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and must be maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

After this change, Bishop calculations will follow the same two solver rules used in the provided Slide2 verification models: (1) any converged surface with final-iteration `M_alpha < 0.2` is treated as invalid, and (2) slice shear strength that would become negative due to base tension is clamped to zero. This should improve FOS parity against Slide2 reference files for prescribed and searched circular surfaces, and it will make oracle baselines internally consistent with the updated solver behavior.

The user-visible outcome is that `python -m slope_stab.cli analyze ...` and all supported search modes continue to run, but candidates that violate the final `M_alpha` stability criterion are rejected and negative per-slice shear strengths are no longer allowed to reduce total resistance below zero. Verification output and regression fixtures remain deterministic for deterministic paths and fixed-seed repeatable for seeded paths.

## Progress

- [x] (2026-03-18 22:52 +13:00) Captured scope and acceptance requirements, including user clarification that the `M_alpha < 0.2` rule applies only to the final converged Bishop iteration.
- [x] (2026-03-18 23:05 +13:00) Implemented solver updates in `src/slope_stab/lem_core/bishop.py`: final-iteration `m_alpha < 0.2` invalidation and non-negative shear clamp in iteration/final resistance aggregation.
- [x] (2026-03-18 23:07 +13:00) Expanded `tests/unit/test_bishop_solver.py` with targeted coverage for final-iteration-only threshold behavior, final-threshold rejection, and shear clamp behavior.
- [x] (2026-03-18 23:13 +13:00) Re-ran parity checks via `python -m slope_stab.cli verify`; Cases 1-4 parity gates remained passing without changing benchmark targets/tolerances.
- [x] (2026-03-18 23:16 +13:00) Evaluated oracle impact via regression gates (`tests.regression.test_cuckoo_global_oracle`, `tests.regression.test_cmaes_global_oracle`) as part of full discovery run; existing oracle fixtures remained valid so no fixture recomputation/update was required.
- [x] (2026-03-18 23:20 +13:00) Updated documentation in `AGENTS.md`, `README.md`, and solver/search explainer markdown files to document the new validity rules.
- [x] (2026-03-18 23:22 +13:00) Ran required verification gate successfully: `python -m slope_stab.cli verify` and `python -m unittest discover -s tests -p "test_*.py"`.

## Surprises & Discoveries

- Observation: The user clarified that `M_alpha < 0.2` must be enforced only after convergence on the final iteration, not during intermediate fixed-point iterations.
  Evidence: User note on 2026-03-18 in this thread: "M_alpha < 0.2 check is only required on the final iteration of the limit equilibrium calculation".

- Observation: Global search methods already centralize invalid-candidate handling through shared evaluation wrappers, so solver-thrown invalidation will propagate naturally to `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`.
  Evidence: `src/slope_stab/search/common.py::evaluate_surface_candidate` maps solver exceptions to invalid candidate outcomes.

- Observation: Existing Case 1-4 verification and benchmark gates were unchanged after the solver update, indicating those current fixtures do not traverse surfaces that violate final `m_alpha >= 0.2` and do not rely on negative slice shear.
  Evidence: `python -m slope_stab.cli verify` remained `all_passed=true` with Case 1-4 hard checks still passing under the same expected values/tolerances.

## Decision Log

- Decision: Keep near-zero `m_alpha` guards during iteration for numerical safety, and add the new `m_alpha < 0.2` rule only on the final converged iteration state.
  Rationale: This follows user instruction while preserving existing convergence stability protections.
  Date/Author: 2026-03-18 / Codex

- Decision: Clamp total per-slice shear strength to `max(0.0, c*l + N*tan(phi))` before numerator aggregation and in emitted `slice_results`.
  Rationale: The requirement is explicitly about negative shear strength under base tension; clamping at the final shear term is the most direct and auditable implementation.
  Date/Author: 2026-03-18 / Codex

- Decision: Treat surfaces failing the final `M_alpha` threshold as invalid by raising `ConvergenceError` from the solver, reusing existing invalid-surface plumbing.
  Rationale: This avoids introducing search-method-specific branching and preserves current invalid-candidate handling contracts.
  Date/Author: 2026-03-18 / Codex

- Decision: Recompute oracle fixtures only after parity checks confirm expected Slide2 alignment with the new solver rules.
  Rationale: Oracle values are objective-dependent and should be regenerated from the final accepted solver behavior, not from an intermediate state.
  Date/Author: 2026-03-18 / Codex

- Decision: Do not rewrite oracle fixture JSON in this change set because post-change oracle regression tests already pass with existing thresholds and endpoint tolerances.
  Rationale: Rewriting fixture baselines without observed threshold/tolerance drift adds churn without increasing verification signal.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

Implemented and validated the requested solver semantics in the Bishop path. The final-iteration `m_alpha` threshold (`< 0.2` invalid) is now enforced after convergence, and base tension induced negative shear strength is clamped to zero in both iterative numerator updates and final reported slice resistance.

The required verification gate stayed green after the change. Case 1/Case 2 benchmark expectations and tolerances were not modified, Case 3/Case 4 parity checks remained passing, and global benchmark/oracle regressions remained passing.

No oracle fixture rewrite was required in this pass because oracle regression contracts remained satisfied. If future datasets trigger more `m_alpha`-invalid candidates and materially shift best-found surfaces, recomputing oracle baselines should be revisited.

## Context and Orientation

The Bishop solver is implemented in `src/slope_stab/lem_core/bishop.py`. It currently computes iterative factor of safety using per-slice terms and already rejects numerically unstable states such as near-zero `m_alpha` and non-finite results. Search modes (`auto_refine_circular`, `direct_global_circular`, `cuckoo_global_circular`, and `cmaes_global_circular`) all evaluate surfaces through `src/slope_stab/analysis.py` and `src/slope_stab/search/common.py`, so solver-level invalidation affects all modes consistently.

In this plan, `M_alpha` means the Bishop denominator term per slice:

    M_alpha = cos(alpha) + sin(alpha) * tan(phi) / F

where `alpha` is slice base angle, `phi` is friction angle, and `F` is current factor of safety iterate. "Final iteration" means the converged `F` that is returned as solver output candidate, not earlier trial iterates. "Base tension induced negative shear strength" means the computed slice shear resistance term (`c*l + N*tan(phi)`) is negative due to negative effective normal force; this value must be clamped to zero.

Verification references and parity artifacts are in `Verification/Bishop/Case 1` through `Verification/Bishop/Case 4` (Slide2 reports and model outputs). Built-in verification expectations are defined in `src/slope_stab/verification/cases.py` and evaluated by `src/slope_stab/verification/runner.py`. Regression coverage for benchmarks and oracles is in `tests/regression/`, with oracle payloads in `tests/fixtures/*_oracle.json`.

## Plan of Work

First, take a baseline measurement by running the required verification gate and recording current Case 1-4 FOS and benchmark/oracle outcomes. This provides a pre-change anchor and ensures any later deltas are attributable to the new solver rules rather than unrelated drift.

Second, implement the solver behavior changes in `src/slope_stab/lem_core/bishop.py`. Keep the existing iterative loop and finite checks intact, but after convergence recompute final `m_alpha` and reject the surface if any slice has `m_alpha < 0.2`. In the same final-term computation path, clamp per-slice shear strength to zero when negative and use the clamped value for the numerator, returned FOS, and slice diagnostics. Ensure warning/error messages include slice id and threshold context to support debugging.

Third, expand tests. Add focused unit coverage in `tests/unit/test_bishop_solver.py` for (a) final-iteration-only `M_alpha` invalidation and (b) negative shear clamp behavior. Update or add regression assertions where needed so invalid surfaces from the new rule are handled as infeasible in search outputs rather than causing crashes. Keep deterministic/fixed-seed repeatability checks intact.

Fourth, run parity checks against Slide2 artifacts for Cases 1-4. If FOS/reference-surface parity changes, update expected values in verification data and parity regressions with documented evidence from the Slide2 files. Respect the repository rule that Case 1/Case 2 targets/tolerances are not changed without explicit approval; if those values need adjustment, record evidence and obtain approval before finalizing edits.

Fifth, regenerate objective-dependent oracle baselines (currently cuckoo and CMAES oracle fixtures) using the accepted updated solver behavior, then update fixture JSON and oracle regression expectations. Use deterministic generation settings and record generation parameters in fixture metadata.

Finally, update documentation so future contributors can apply the same rules consistently. Update `AGENTS.md` solver conventions, update `README.md` behavior notes, update each method explainer (`docs/auto-refine-explainer.md`, `docs/direct-global-explainer.md`, `docs/cuckoo-global-explainer.md`, `docs/cmaes-global-explainer.md`) to describe invalidation/clamping semantics, and update this `PLANS.md` plan sections through completion.

## Concrete Steps

Run all commands from repository root `C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab`.

Baseline and post-change verification commands:

    python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"
    python -m unittest tests.unit.test_bishop_solver
    python -m unittest tests.regression.test_case3_auto_refine
    python -m unittest tests.regression.test_case4_auto_refine
    python -m unittest tests.regression.test_global_search_benchmark
    python -m unittest tests.regression.test_cuckoo_global_search_benchmark
    python -m unittest tests.regression.test_cmaes_global_search_benchmark
    python -m unittest tests.regression.test_cuckoo_global_oracle
    python -m unittest tests.regression.test_cmaes_global_oracle

If oracle recomputation tooling is added in this work, run it after solver changes are accepted and before updating oracle fixtures:

    python tests/tools/recompute_oracles.py --fixture tests/fixtures/case2_cuckoo_oracle.json --write
    python tests/tools/recompute_oracles.py --fixture tests/fixtures/case3_cuckoo_oracle.json --write
    python tests/tools/recompute_oracles.py --fixture tests/fixtures/case2_cmaes_oracle.json --write
    python tests/tools/recompute_oracles.py --fixture tests/fixtures/case3_cmaes_oracle.json --write

Expected transcript characteristics:

    - `cli verify` returns JSON with `"all_passed": true`.
    - `unittest discover` reports all tests passing.
    - Bishop unit tests include explicit pass/fail checks for final-iteration `M_alpha` thresholding and non-negative shear strength.
    - Oracle regression tests pass using refreshed fixture values when refreshed values are required.

## Validation and Acceptance

Acceptance is met only when all of the following are true:

The solver behavior is correct and observable. A surface that converges with any final-iteration slice `m_alpha < 0.2` is rejected as invalid, while intermediate iterations are not rejected solely for `m_alpha < 0.2`. Per-slice shear strength in final calculations and `slice_results` is never negative.

Slide2 parity is improved or maintained for Cases 1-4 using the provided verification files in `Verification/Bishop/`. Any changed expected values are accompanied by explicit evidence and rationale. Case 1/Case 2 expected targets or tolerances are not changed without explicit approval.

Required verification gates pass:

    python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Benchmark/oracle regressions remain valid with the updated solver semantics. If oracle fixtures were recomputed, fixture metadata and regression thresholds are internally consistent and reproducible.

Documentation is complete and synchronized across `AGENTS.md`, `PLANS.md`, `README.md`, and relevant explainer markdown files.

## Idempotence and Recovery

All analysis and test commands above are rerunnable. If a partial edit breaks tests, restore local consistency by finishing solver/test/doc updates before re-running the full gate; avoid changing tolerances to force pass. If oracle regeneration produces unstable values, fix determinism inputs (grid resolution, seed, mapping rules) and regenerate rather than hand-editing oracle numbers.

If parity updates require Case 1/Case 2 target modifications, stop and request explicit user approval before committing those target changes. Until approval is given, keep existing Case 1/Case 2 expected values unchanged and track parity deltas as diagnostics.

## Artifacts and Notes

Implementation evidence:

    - Baseline: `python -m slope_stab.cli verify` (with `PYTHONPATH=src`) returned `all_passed=true` for all 13 built-in cases.
    - Post-change: `python -m slope_stab.cli verify` (with `PYTHONPATH=src`) returned `all_passed=true` for all 13 built-in cases.
    - Unit proof: `python -m unittest tests.unit.test_bishop_solver` ran 5 tests and passed, including:
      - final-iteration-only `m_alpha` gate behavior
      - rejection when final `m_alpha < 0.2`
      - non-negative shear clamp behavior
    - Full gate: `python -m unittest discover -s tests -p "test_*.py"` ran 31 tests and passed.
    - Oracle impact check: oracle regression tests remained passing in full discovery run; no fixture JSON updates required.

No runtime cache artifacts (`__pycache__/`, `*.pyc`) may be committed.

## Interfaces and Dependencies

Primary implementation interface:

- `src/slope_stab/lem_core/bishop.py::BishopSimplifiedSolver.solve`

Required end-state behavior contract:

- Final converged `m_alpha` array is validated against threshold `0.2`.
- Any slice with final `m_alpha < 0.2` causes solver invalidation via `ConvergenceError`.
- Final per-slice shear strength used in numerator and reported diagnostics is `max(0.0, shear_strength_raw)`.
- Existing numerical safety checks (finite values, near-zero denominator/`m_alpha`, convergence limits) remain in place.

Likely touched verification and regression interfaces:

- `src/slope_stab/verification/cases.py` for expected values when parity evidence requires updates.
- `tests/unit/test_bishop_solver.py` for rule-focused unit coverage.
- `tests/regression/test_*` and `tests/fixtures/*_oracle.json` for benchmark/oracle alignment.

Dependencies remain unchanged and required: `numpy`, `scipy`, and `cma`.

Plan revision note: Added on 2026-03-18 and closed on 2026-03-18 after implementing the solver-rule updates, adding focused unit coverage, updating documentation, and passing the required verification gate.
```

```md
# Consolidate Global Search Core and Remove Optimization Redundancies (NumPy/SciPy/pycma)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were kept up to date through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and was maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Global search paths now share core objective/caching and DIRECT partition primitives, reducing duplicated logic while preserving benchmark and verification behavior. Runtime dependencies remain required (`numpy`, `scipy`, `cma`) with no fallback branches added. The user-visible behavior remains unchanged: same methods, same CLI surface, same verification policy.

## Progress

- [x] (2026-03-19 +13:00) Completed repository + subagent exploration and confirmed redundancy/performance hotspots.
- [x] (2026-03-19 +13:00) Captured baseline gate status using `python -m slope_stab.cli verify` and `python -m unittest discover -s tests -p "test_*.py"`.
- [x] (2026-03-19 +13:00) Added shared global objective evaluator module (`src/slope_stab/search/objective_evaluator.py`).
- [x] (2026-03-19 +13:00) Added shared DIRECT partition primitive (`src/slope_stab/search/direct_partition.py`).
- [x] (2026-03-19 +13:00) Added shared post-polish config helper (`src/slope_stab/search/post_polish.py`).
- [x] (2026-03-19 +13:00) Refactored `direct_global.py` to use shared evaluator and shared DIRECT partition primitive.
- [x] (2026-03-19 +13:00) Refactored `cuckoo_global.py` to use shared evaluator and precompute Levy `sigma_u` once per run.
- [x] (2026-03-19 +13:00) Refactored `cmaes_global.py` to use shared evaluator + shared DIRECT prescan primitive and removed dead restart branch.
- [x] (2026-03-19 +13:00) Applied bounded CMAES toe-locked tuning from fixed `81x81` sweep to deterministic two-phase (`61x61` coarse + `21x21` local) sweep.
- [x] (2026-03-19 +13:00) Removed repeated per-iteration small-cos warning emission in `bishop.py` (now emitted once).
- [x] (2026-03-19 +13:00) Removed unused `_slice_area_piecewise` in `slice_generator.py`.
- [x] (2026-03-19 +13:00) De-duplicated regression benchmark scaffolding via shared helper (`tests/regression/global_search_benchmark_helpers.py`).
- [x] (2026-03-19 +13:00) Updated documentation in `AGENTS.md`, `README.md`, and search explainers.
- [x] (2026-03-19 +13:00) Re-ran full required gate; all tests and verification checks passed.

## Surprises & Discoveries

- Observation: Shared evaluator and DIRECT primitives can be extracted without changing benchmark outcomes when tie-break and ordering semantics are preserved exactly.
  Evidence: Cases 2-4 benchmark gates stayed passing for direct/cuckoo/CMAES after refactor.

- Observation: Removing duplicated repair/round paths via centralized vector normalization did not reduce repeatability for fixed-seed cuckoo/CMAES checks.
  Evidence: `tests.regression.test_cuckoo_global_oracle` and `tests.regression.test_cmaes_global_oracle` passed.

- Observation: Two-phase toe-locked CMAES polish changed some CMAES objective trajectories slightly but stayed within required benchmark margins.
  Evidence: built-in `cli verify` still passed Case 2/3/4 CMAES benchmark checks (`<= benchmark + 0.01`).

- Observation: The previous benchmark perf capture command emitted very large metadata payloads due full iteration diagnostics.
  Evidence: baseline command output was extremely large; a compact fixture timing summary was added for post-change reporting.

## Decision Log

- Decision: Keep refactor behavior-preserving for direct and cuckoo paths while allowing bounded CMAES polish tuning.
  Rationale: matches approved scope and minimizes risk to deterministic/repeatability contracts.
  Date/Author: 2026-03-19 / Codex + User

- Decision: Centralize evaluator and partition logic into shared modules rather than partial helper extraction.
  Rationale: this removes multiple duplicate implementations and reduces future drift risk.
  Date/Author: 2026-03-19 / Codex

- Decision: Keep performance checks non-gating and evidence-oriented.
  Rationale: avoids environment-dependent flakiness while still recording regressions.
  Date/Author: 2026-03-19 / Codex + User

- Decision: De-dup verification scaffolding in regression helpers in this cycle; leave `verification/cases.py` data layout unchanged.
  Rationale: preserve fixture readability and reduce churn risk while still removing repeated assertion logic.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

Completed goals:

- Reduced search-core duplication by introducing shared objective and DIRECT partition primitives.
- Preserved required verification behavior and benchmark gate outcomes.
- Applied bounded CMAES toe-locked tuning with deterministic sampling.
- Removed low-risk local inefficiencies (`bishop` warning duplication, dead slicing helper, repeated Levy constant math).
- Updated governance and explainer docs to match current implementation architecture.

Remaining technical debt:

- `src/slope_stab/verification/cases.py` still has repeated case payload blocks and can be further deduplicated in a follow-up without touching expected values.

## Context and Orientation

Primary touched runtime modules:

- `src/slope_stab/search/objective_evaluator.py`
- `src/slope_stab/search/direct_partition.py`
- `src/slope_stab/search/post_polish.py`
- `src/slope_stab/search/direct_global.py`
- `src/slope_stab/search/cuckoo_global.py`
- `src/slope_stab/search/cmaes_global.py`
- `src/slope_stab/lem_core/bishop.py`
- `src/slope_stab/slicing/slice_generator.py`

Primary touched regression/docs modules:

- `tests/regression/global_search_benchmark_helpers.py`
- `tests/regression/test_global_search_benchmark.py`
- `tests/regression/test_cuckoo_global_search_benchmark.py`
- `tests/regression/test_cmaes_global_search_benchmark.py`
- `AGENTS.md`
- `README.md`
- `docs/direct-global-explainer.md`
- `docs/cuckoo-global-explainer.md`
- `docs/cmaes-global-explainer.md`
- `docs/auto-refine-explainer.md`

## Plan of Work

Implementation followed the planned sequence:

1. Baseline gate check.
2. Shared core extraction (objective evaluator + DIRECT partition + polish config).
3. Refactor direct/cuckoo/CMAES onto shared core.
4. Apply bounded CMAES tuning.
5. Remove low-risk local inefficiencies.
6. De-duplicate benchmark regression assertions.
7. Update docs.
8. Re-run full verification and test gates.

## Concrete Steps

Run from repository root:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    $env:PYTHONPATH='src'; python -m unittest discover -s tests -p "test_*.py"
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_global_search_benchmark
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_cuckoo_global_search_benchmark
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_cmaes_global_search_benchmark
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_cuckoo_global_oracle
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_cmaes_global_oracle

Compact post-change perf snapshot command:

    $env:PYTHONPATH='src'; @'
    import json, time
    from slope_stab.io.json_io import load_project_input
    from slope_stab.analysis import run_analysis
    fixtures = [
      "tests/fixtures/case2_direct_global.json",
      "tests/fixtures/case3_direct_global.json",
      "tests/fixtures/case4_direct_global.json",
      "tests/fixtures/case2_cuckoo_global.json",
      "tests/fixtures/case3_cuckoo_global.json",
      "tests/fixtures/case4_cuckoo_global.json",
      "tests/fixtures/case2_cmaes_global.json",
      "tests/fixtures/case3_cmaes_global.json",
      "tests/fixtures/case4_cmaes_global.json",
    ]
    rows = []
    for fixture in fixtures:
        project = load_project_input(fixture)
        t0 = time.perf_counter()
        result = run_analysis(project)
        dt = time.perf_counter() - t0
        search = result.metadata.get("search", {})
        rows.append({
            "fixture": fixture,
            "seconds": round(dt, 4),
            "fos": result.fos,
            "total_evaluations": search.get("total_evaluations"),
            "valid_evaluations": search.get("valid_evaluations"),
            "infeasible_evaluations": search.get("infeasible_evaluations"),
            "termination_reason": search.get("termination_reason"),
        })
    print(json.dumps(rows, indent=2))
    '@ | python -

## Validation and Acceptance

All required acceptance checks passed:

- `python -m slope_stab.cli verify` passed all built-in cases.
- `python -m unittest discover -s tests -p "test_*.py"` passed (31 tests).
- Case 1 and Case 2 targets/tolerances were unchanged.
- Cases 2-4 benchmark checks for direct/cuckoo/CMAES remained passing.
- Cuckoo/CMAES oracle regressions remained passing for fixed seeds.
- Documentation updates were applied to AGENTS/README/explainers.

## Idempotence and Recovery

Commands above are rerunnable. If a future change causes benchmark drift, first disable new tuning paths (for example CMAES toe-locked sampling changes) and keep shared-core structural refactor intact, then re-run the full verification gate.

Do not adjust Case 1/Case 2 benchmark tolerances as a recovery action.

## Artifacts and Notes

Functional gate evidence:

- Baseline verify: passed all built-in cases.
- Baseline unittest discover: passed.
- Post-change verify: passed all built-in cases.
- Post-change unittest discover: passed (31 tests).

Performance evidence (non-gating):

- Baseline sample timings captured before refactor included:
  - `case2_direct_global`: `1.1571s`
  - `case3_direct_global`: `1.6624s`
  - `case4_direct_global`: `1.4333s`
  - `case2_cuckoo_global`: `1.2992s`
- Post-change compact timings:
  - `case2_direct_global`: `0.9886s`
  - `case3_direct_global`: `1.6160s`
  - `case4_direct_global`: `1.6701s`
  - `case2_cuckoo_global`: `1.4800s`
  - `case3_cuckoo_global`: `3.1493s`
  - `case4_cuckoo_global`: `2.5165s`
  - `case2_cmaes_global`: `3.4924s`
  - `case3_cmaes_global`: `3.9215s`
  - `case4_cmaes_global`: `4.3879s`
- No benchmark-gate regressions were introduced while applying bounded CMAES tuning and shared-core refactors.

No runtime cache artifacts (`__pycache__/`, `*.pyc`) were added.

## Interfaces and Dependencies

Public interfaces unchanged:

- CLI contract unchanged.
- Input schema unchanged.
- Supported methods unchanged.

New internal interfaces:

- `CachedObjectiveEvaluator` and scoring policy in `src/slope_stab/search/objective_evaluator.py`.
- `DirectRectangle`, `select_potentially_optimal`, `split_rectangle`, and seeded center helper in `src/slope_stab/search/direct_partition.py`.
- `default_post_polish_refine_config` in `src/slope_stab/search/post_polish.py`.

Dependencies unchanged and required:

- `numpy`, `scipy`, `cma`.

Plan status: Closed.

Plan revision note: Added and closed on 2026-03-19 after implementing shared search-core refactors, bounded CMAES polish tuning, documentation alignment, and full gate validation.
```

```md
# Implement Spencer Method End-to-End (Verification First, Then Search)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and must be maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Users can now run `analysis.method = "spencer"` for prescribed circular surfaces and all existing circular search methods (`auto_refine_circular`, `direct_global_circular`, `cuckoo_global_circular`, `cmaes_global_circular`) while preserving Bishop paths and benchmarks.

## Progress

- [x] (2026-03-19 +13:00) Implemented `SpencerSolver` and analysis dispatch support with additive parser validation (`analysis.method` accepts `bishop_simplified` and `spencer`).
- [x] (2026-03-19 +13:00) Added Spencer verification coverage in built-in suite: prescribed benchmarks for Cases 2-4, auto-refine parity for Cases 3-4, and global benchmark checks for Cases 2-4 across DIRECT/Cuckoo/CMAES.
- [x] (2026-03-19 +13:00) Added dedicated Spencer regression coverage (`tests/regression/test_spencer_*`) including prescribed, benchmark, and oracle checks.
- [x] (2026-03-19 +13:00) Added Spencer fixture variants (`tests/fixtures/*_spencer.json`) for search/oracle regression runs.
- [x] (2026-03-19 +13:00) Updated docs (`AGENTS.md`, `README.md`, and explainers) to reflect Spencer support and solver-agnostic search validity rules.
- [x] (2026-03-19 +13:00) Ran required verification gate and full test discovery successfully.

## Surprises & Discoveries

- Observation: Existing Slide2 artifacts already contained Spencer global-minimum references for Cases 2-4, including lambda trend data for Case 3/4.
  Evidence: `Case2-i.rfcreport`, `Case3-i.rfcreport`, `Case4-i.rfcreport`, and corresponding `.s01` files.

- Observation: A deterministic two-residual Spencer solve (`force residual` + `moment residual`) with vectorized slice terms is fast enough for large search budgets.
  Evidence: Built-in verify and full test suite pass under expanded Spencer benchmark/oracle coverage.

- Observation: Auto-generated JSON fixtures written with BOM cause loader failures under `json.loads(..., encoding='utf-8')` expectations.
  Evidence: Spencer fixture regressions initially failed with `JSONDecodeError: Unexpected UTF-8 BOM`; fixed by rewriting fixtures without BOM.

## Decision Log

- Decision: Expose Spencer through `analysis.method = "spencer"` (additive, no fallback paths).
  Rationale: Clear explicit contract and compatibility with existing mode dispatch architecture.
  Date/Author: 2026-03-19 / Codex + Owner

- Decision: Keep search engines method-agnostic and route Spencer through the shared `evaluate_surface` callback path.
  Rationale: Avoid duplicated search logic and preserve centralized objective/caching behavior.
  Date/Author: 2026-03-19 / Codex + Owner

- Decision: Preserve hard benchmark rule shape (`FOS(method) <= FOS(benchmark) + 0.01`) for Spencer global checks.
  Rationale: Keeps benchmark semantics consistent across Bishop and Spencer suites.
  Date/Author: 2026-03-19 / Codex + Owner

## Outcomes & Retrospective

Delivered outcomes:

- Spencer solver path implemented and integrated.
- Verification suite expanded to 27 built-in cases (13 Bishop + 14 Spencer).
- Spencer regression/oracle test coverage added and passing.
- Documentation updated to reflect current repository capabilities.

Gate evidence:

- `python -m slope_stab.cli verify` passed all 27 cases.
- `python -m unittest discover -s tests -p "test_*.py"` passed (39 tests).

Plan status: Closed.

Plan revision note: Added and closed on 2026-03-19 after Spencer solver integration, expanded verification/regression coverage, and full gate validation.
```

```md
# Implement Staged Parallel Processing with Determinism Guarantees

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were kept up to date through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and was maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

The repository now supports opt-in parallel candidate scoring for circular search workflows while preserving verification-first behavior and benchmark contracts. Parallel failures are explicit, deterministic errors; there is no silent partial-state continuation.

## Progress

- [x] (2026-03-19 +13:00) Added additive parallel config model and parser support (`search.parallel`).
- [x] (2026-03-19 +13:00) Added top-level worker-boundary module with immutable context and candidate-only task payloads.
- [x] (2026-03-19 +13:00) Added deterministic batch semantics in shared objective evaluator (`evaluate_vectors_batch`).
- [x] (2026-03-19 +13:00) Parallelized auto-refine and CMAES batchable scoring paths; preserved deterministic ordered merge behavior.
- [x] (2026-03-19 +13:00) Added DIRECT/Cuckoo batch integrations where safe without violating update-order contracts.
- [x] (2026-03-19 +13:00) Added `cli verify --workers` with stable output ordering and inner-search serial override.
- [x] (2026-03-19 +13:00) Added unit/regression coverage for parser defaults, batch semantics, parallel behavior, and timeout failure policy.
- [x] (2026-03-19 +13:00) Updated documentation (`AGENTS.md`, `README.md`, and explainers).
- [x] (2026-03-19 +13:00) Ran required verification gate and full unittest discovery successfully.

## Surprises & Discoveries

- Observation: Process worker creation can fail in restricted Windows environments (`WinError 5` on pipe creation).
  Evidence: Parallel regression tests failed in-process-pool initialization with access-denied pipe creation.

- Observation: A controlled thread-worker fallback is required to keep opt-in parallel paths usable in restricted environments while retaining deterministic merge semantics.
  Evidence: Parallel regression tests passed after controlled fallback and explicit backend reporting.

- Observation: CMAES worker-invariance can show very small numerical drift under batched scoring while still meeting benchmark gates.
  Evidence: Parallel-vs-serial CMAES regression required tolerance-based surface/FOS comparison instead of strict field equality.

## Decision Log

- Decision: Keep `search.parallel` opt-in with serial defaults.
  Rationale: verification-first risk posture and non-breaking behavior.
  Date/Author: 2026-03-19 / Codex + Owner

- Decision: Implement worker-boundary contract using immutable context plus candidate-only tasks.
  Rationale: supports process workers without lambda/closure coupling and minimizes per-task payload overhead.
  Date/Author: 2026-03-19 / Codex

- Decision: Raise deterministic explicit errors on worker timeout/invalid payload/worker failure.
  Rationale: no silent partial continuation.
  Date/Author: 2026-03-19 / Codex

- Decision: Use controlled thread-worker fallback when process workers cannot be created in restricted environments.
  Rationale: preserves behavior and keeps opt-in parallel paths operable under host constraints while reporting backend in metadata.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- Parallel configuration and runtime wiring landed end-to-end.
- Shared evaluator now supports deterministic ordered batch evaluation with cache/budget/incumbent consistency.
- Search methods and verification runner support parallel workflows per scope.
- Documentation updated for parallel invariants and failure policy.

Validation evidence:

- `python -m slope_stab.cli verify` returned `all_passed=true` for all 27 built-in cases.
- `python -m unittest discover -s tests -p "test_*.py"` passed (48 tests).
- Added targeted tests: `tests/unit/test_objective_evaluator_batch.py` and `tests/regression/test_parallel_search_behavior.py`.

Performance evidence (non-gating, sampled):

- `case3_auto_refine_spencer`: serial `28.9667s`, parallel `29.7247s`.
- `case4_auto_refine_spencer`: serial `141.5342s`, parallel `144.2342s`.
- `case4_cmaes_global`: serial `2.9664s`, parallel `2.9324s`.
- Sampled environment used thread fallback backend due process-worker restrictions.

Plan status: Closed.

Plan revision note: Added and closed on 2026-03-19 after implementing staged parallel processing features, deterministic batch semantics, failure-policy safeguards, documentation updates, and full gate validation.
```

```md
# Implement Default `auto` Search Parallel-Mode Resolution

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` were kept up to date through implementation and closure.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and was maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Search configuration now defaults to `search.parallel.mode = auto`. Runtime deterministically resolves serial vs parallel using a static, versioned policy and emits explicit decision metadata so behavior is observable and testable. Legacy `search.parallel.enabled` remains backward-compatible.

## Progress

- [x] (2026-03-23 +13:00) Migrated parallel config contract to `mode` (`auto|serial|parallel`) with default `auto` and default `workers=0`.
- [x] (2026-03-23 +13:00) Added deterministic auto-policy module (`src/slope_stab/search/auto_parallel_policy.py`) with effective CPU helper, worker clamping rules, centralized batching classification, workload classification, and policy tables.
- [x] (2026-03-23 +13:00) Updated parser migration logic to map legacy `enabled` values and reject conflicting `enabled`+`mode`.
- [x] (2026-03-23 +13:00) Updated analysis resolution/metadata path to emit requested/resolved mode, reason enum, evidence version, backend, worker counts, workload class, and batching class.
- [x] (2026-03-23 +13:00) Added CLI analyze overrides (`--parallel-mode`, `--parallel-workers`) with precedence `CLI > JSON > defaults`.
- [x] (2026-03-23 +13:00) Added/updated tests for parser migration, resolver semantics, metadata contract, CLI override behavior, and thread-backend default-serial policy in auto mode.
- [x] (2026-03-23 +13:00) Added benchmark harness `scripts/benchmarks/auto_mode_matrix.py` and recorded evidence artifact in `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json`.
- [x] (2026-03-23 +13:00) Updated docs (`AGENTS.md`, `README.md`, and explainers) to reflect default auto behavior and deterministic resolver contract.
- [x] (2026-03-23 +13:00) Ran full required gate: `python -m slope_stab.cli verify` and `python -m unittest discover -s tests -p "test_*.py"`.

## Surprises & Discoveries

- Observation: In this host environment, forced parallel requests used thread backend during benchmark runs.
  Evidence: `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json` reports `backend="thread"` for forced parallel runs.

- Observation: Benchmark workload proxies for sampled fixtures classified as `small`/`medium`, so conservative auto policy resolved serial.
  Evidence: all sampled auto runs report `decision_reason="policy_threshold_serial"` with `workload_class` in `{small, medium}`.

- Observation: Full unittest discovery runtime is substantial after expanded regression coverage.
  Evidence: `python -m unittest discover -s tests -p "test_*.py"` completed 64 tests in ~1758 seconds in this environment.

## Decision Log

- Decision: Keep thread-backend whitelist structurally present but empty in v1.
  Rationale: avoid auto-promoting thread parallelism until dedicated evidence supports it.
  Date/Author: 2026-03-23 / Codex + external review consensus

- Decision: Keep runtime resolver dependent on static policy table and deterministic classifiers only.
  Rationale: avoids runtime probing/calibration nondeterminism and keeps behavior reproducible.
  Date/Author: 2026-03-23 / Codex + external review consensus

- Decision: Preserve legacy `enabled` compatibility with strict conflict rejection.
  Rationale: protects existing inputs while forcing unambiguous intent when both old and new fields appear.
  Date/Author: 2026-03-23 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- Default search processing mode is now `auto`.
- Resolver behavior is deterministic, metadata-rich, and test-covered.
- CLI overrides and parser migration behavior are implemented and validated.
- Documentation now reflects mode semantics, worker rules, thread fallback posture, and metadata contract.
- Benchmark evidence workflow is codified in-repo and can be rerun for future policy revisions.

Validation evidence:

- `python -m slope_stab.cli verify` passed all 27 built-in cases.
- `python -m unittest discover -s tests -p "test_*.py"` passed (64 tests).

Performance evidence artifacts:

- `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.json`
- `docs/benchmarks/auto-mode-policy-evidence-2026-03-23.md`

Plan status: Closed.

Plan revision note: Added and closed on 2026-03-23 after implementing default auto-mode resolution, deterministic policy metadata, CLI overrides, benchmark evidence capture, documentation updates, and full gate validation.
```

```md
# Implement Default Parallel `cli verify` with Explicit Serial Debug Mode

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and must be maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Users currently need to opt into parallel verification with `python -m slope_stab.cli verify --workers N`. After this change, `python -m slope_stab.cli verify` will run case-level parallel processing by default on multi-core machines, while still allowing an explicit serial mode for debugging and step-by-step reproduction.

The user-visible outcome is faster default verification behavior without changing verification case definitions, benchmark thresholds, or output ordering. Debugging remains deterministic through an explicit serial path.

## Progress

- [x] (2026-03-23 20:31 +13:00) Reviewed current CLI and verification runner behavior in `src/slope_stab/cli.py` and `src/slope_stab/verification/runner.py`.
- [x] (2026-03-23 20:31 +13:00) Reviewed existing verification regression/integration tests and current docs references in `README.md`, `AGENTS.md`, and explainer files.
- [x] (2026-03-23 20:31 +13:00) Captured baseline runtime evidence on this machine: `verify --workers 1` ~= `361.54s`, `--workers 2` ~= `352.85s`, `--workers 4` ~= `354.13s`, `--workers 8` ~= `356.20s`.
- [x] (2026-03-23 21:03 +13:00) Completed external AI review pass (`GPT5.4 Plan Review.txt`) and recorded consensus amendments plus explicit accept/reject decisions.
- [x] (2026-03-23 21:18 +13:00) Completed external AI v2 review pass (`GPT5.4 Plan Review v2.txt`) and folded required amendments for strict CLI conflict rules, conservative thread fallback, and narrower documentation scope.
- [x] (2026-03-23 21:36 +13:00) Completed external AI v3 review pass (`GPT5.4 Plan Review v3.txt`) and folded final consistency edits for acceptance wording and documentation-scope phrasing.
- [x] (2026-03-23 22:08 +13:00) Implemented `cli verify` contract update: default auto-parallel scheduling, `--serial` canonical debug path, explicit `--workers`, and strict `--serial`/`--workers` mutual exclusion.
- [x] (2026-03-23 22:08 +13:00) Added deterministic verify execution metadata in CLI JSON output under top-level `execution`.
- [x] (2026-03-23 22:08 +13:00) Added/updated coverage: `tests/unit/test_verification_runner_workers.py`, `tests/unit/test_cli_verify_contract.py`, and updated `tests/regression/test_cli_verify.py`.
- [x] (2026-03-23 22:08 +13:00) Updated documentation: `AGENTS.md`, `README.md`, `docs/auto-refine-explainer.md`, `docs/direct-global-explainer.md`, and finalized this ExecPlan in `PLANS.md`.
- [x] (2026-03-23 22:31 +13:00) Ran required full gate: `python -m slope_stab.cli verify` and `python -m unittest discover -s tests -p "test_*.py"`; all passed.

## Surprises & Discoveries

- Observation: Parallel workers improve wall-clock time on this host, but only modestly for current case mix and runtime profile.
  Evidence: Measured `verify --workers 1` at `361.54s` and `verify --workers 2` at `352.85s` with small improvement.

- Observation: Verification already enforces inner analysis serial mode per case (`forced_parallel_mode="serial", forced_parallel_workers=1`), so current parallelism is only at case scheduling level.
  Evidence: `_evaluate_case` in `src/slope_stab/verification/runner.py`.

- Observation: Process worker startup can fail in restricted environments and current code already falls back to thread workers.
  Evidence: `run_verification_suite` catches `OSError`/`PermissionError` and constructs `ThreadPoolExecutor`.

- Observation: External review correctly identified that "serial debug = --workers 1" alone is ambiguous UX and should be replaced by an explicit canonical serial flag.
  Evidence: Reviewer requested an exact CLI contract with `--serial` and conflict validation.

- Observation: External review correctly challenged the rationale for `workers=0 -> min(4, cpu)`; current evidence supports "deterministic bounded policy reuse" but does not prove 4 is a machine-optimal runtime choice.
  Evidence: Measured timings showed only a small gain at 2 workers and no clear win at 4 or 8.

- Observation: External v2 review identified that allowing any `--serial` + `--workers` combination creates avoidable UX ambiguity.
  Evidence: Reviewer requested strict rejection of all combined uses, including `--serial --workers 1` and `--serial --workers 0`.

- Observation: External v2 review identified that thread-parallel verify fallback would diverge from existing conservative thread posture already used by search auto-mode.
  Evidence: Existing tests codify serial-by-default behavior for auto mode on thread backend unless explicitly whitelisted.

- Observation: External v3 review identified a contract mismatch between one acceptance bullet and the backend-policy section.
  Evidence: Existing hard-acceptance wording implied unconditional parallel-by-default for multi-core hosts, while backend policy explicitly routes thread fallback to serial in auto mode.

- Observation: In this host environment, default verify auto mode resolved serial due process backend unavailability and thread fallback policy.
  Evidence: Gate run `python -m slope_stab.cli verify` emitted `execution` metadata with `requested_mode=auto_parallel`, `backend=thread`, `resolved_mode=serial`, `decision_reason=thread_backend_default_serial`, `requested_workers=4`, `resolved_workers=1`.

## Decision Log

- Decision: Keep inner case evaluation forced to serial during this change and parallelize only across verification cases.
  Rationale: Avoid nested parallel oversubscription and preserve deterministic behavior in search paths already governed by their own policy.
  Date/Author: 2026-03-23 / Codex

- Decision: Make default parallel behavior a CLI contract change (`cli verify` defaults to auto-resolved workers) while preserving explicit serial debugging controls.
  Rationale: Meets owner requirement without changing verification math, case fixtures, or benchmark tolerances.
  Date/Author: 2026-03-23 / Codex

- Decision: External AI review suggestions must be handled with explicit accept/reject reasoning before implementation.
  Rationale: Owner requires consensus prior to coding and expects critical evaluation of weak or unsafe recommendations.
  Date/Author: 2026-03-23 / Codex

- Decision: Lock the CLI contract before coding: default `verify` is auto-parallel; `--serial` is canonical debug path; `--workers N` is explicit override; conflicting combinations fail loudly.
  Rationale: Removes ambiguity and addresses review concern that "or equivalent" was too loose.
  Date/Author: 2026-03-23 / Codex

- Decision: Keep deterministic completion-order collection for worker futures (not fail-fast) and reject fail-fast suggestion for this iteration.
  Rationale: Deterministic failure indexing and reproducibility are higher priority than marginally earlier failure surfacing in a rare error path.
  Date/Author: 2026-03-23 / Codex

- Decision: Reuse existing parallel metadata vocabulary (`requested_mode`, `resolved_mode`, `decision_reason`, `backend`, `requested_workers`, `resolved_workers`, `evidence_version`) under a dedicated top-level `execution` object.
  Rationale: Avoids a second metadata dialect and keeps debug/observability contracts coherent with existing parallel policy naming.
  Date/Author: 2026-03-23 / Codex

- Decision: Narrow documentation and test scope to verification-relevant files and efficient coverage.
  Rationale: Avoid scope creep and long redundant end-to-end runs while still covering changed behavior.
  Date/Author: 2026-03-23 / Codex

- Decision: Treat `--serial` as mutually exclusive with `--workers` for all values.
  Rationale: `--serial` is the canonical debug path; combining it with worker flags introduces ambiguous intent with no useful capability.
  Date/Author: 2026-03-23 / Codex

- Decision: In default verify auto mode, if process workers are unavailable and backend resolves to thread, default to serial unless and until explicit benchmark evidence approves thread-parallel verify policy.
  Rationale: Aligns with existing conservative thread posture and avoids policy divergence without evidence.
  Date/Author: 2026-03-23 / Codex

- Decision: Drop new verification-specific explainer from implementation scope; keep documentation updates in `AGENTS.md`, `README.md`, and existing explainers that already mention `cli verify`.
  Rationale: Meets documentation requirements without adding unnecessary long-lived docs surface for a small CLI mode change.
  Date/Author: 2026-03-23 / Codex

- Decision: Tighten hard-acceptance wording to explicitly include process-backend availability and backend-policy-driven fallback behavior.
  Rationale: Removes ambiguity and keeps acceptance criteria consistent with the documented thread-fallback policy.
  Date/Author: 2026-03-23 / Codex

- Decision: Keep legacy `run_verification_suite(workers=...)` behavior for compatibility while adding `run_verification_suite_with_execution(...)` for CLI execution-contract metadata.
  Rationale: Preserves existing integration usage and minimizes breakage while enabling new verify metadata/contract behavior.
  Date/Author: 2026-03-23 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- `cli verify` now defaults to auto-parallel request mode with deterministic worker resolution (`workers=0 -> min(4, effective_cpu_count)`).
- `cli verify --serial` is the canonical serial debug path.
- `--serial` and `--workers` are mutually exclusive at parse-time.
- Verify output now includes top-level `execution` metadata: `requested_mode`, `resolved_mode`, `decision_reason`, `backend`, `requested_workers`, `resolved_workers`, `evidence_version`.
- Deterministic case ordering and explicit worker-failure behavior were preserved.
- Documentation and focused coverage were updated to match shipped behavior.

Validation evidence:

- `python -m slope_stab.cli verify` passed all 27 built-in cases (`all_passed=true`).
- `python -m unittest discover -s tests -p "test_*.py"` passed (73 tests).

Residual caveat:

- In this host environment, verify auto mode selected serial because process backend was unavailable and thread fallback serial policy is intentionally conservative.

## Context and Orientation

`cli verify` is implemented in `src/slope_stab/cli.py`. It currently exposes `--workers` with default `1`, then calls `run_verification_suite(workers=max(1, int(args.workers)))`. This means default execution is serial.

Case execution logic lives in `src/slope_stab/verification/runner.py`. The runner preserves output order by storing futures in case-index order and materializing results in that same order. Worker failures are already treated as hard failures via explicit `RuntimeError`.

Verification case definitions and benchmark values are fixed in `src/slope_stab/verification/cases.py`. These values are not part of this change and must remain untouched.

Current test coverage includes:

- `tests/regression/test_cli_verify.py`
- `tests/integration/test_verification_cases.py`

Current docs references to `cli verify` are in:

- `AGENTS.md`
- `README.md`
- `docs/auto-refine-explainer.md`
- `docs/direct-global-explainer.md`

Additional explainers that should be aligned for consistent user guidance:

- `docs/cuckoo-global-explainer.md`
- `docs/cmaes-global-explainer.md`
- `docs/spencer-explainer.md`

In this plan, "parallel verification" means running different verification cases concurrently. It does not mean enabling inner-search parallel scoring inside each case.

## External Review Gate

Before implementation, obtain review feedback from another AI model and record each suggestion in this plan's `Decision Log` as accepted or rejected.

External review outcome (GPT-5.4):

- Accepted: lock exact CLI contract before implementation.
- Accepted: tighten worker-policy rationale and describe `workers=0` as deterministic bounded policy reuse.
- Accepted: explicitly define backend-resolution behavior.
- Accepted: reuse existing parallel metadata vocabulary in a dedicated `execution` object.
- Accepted: narrow docs/tests scope for implementation efficiency.
- Rejected: fail-fast worker error collection proposal for this change.

External review v2 outcome (GPT-5.4):

- Accepted: reject all `--serial` + `--workers` combinations.
- Accepted: keep verify auto-mode serial-by-default on thread fallback pending dedicated evidence.
- Accepted: remove new verification explainer from implementation scope.

External review v3 outcome (GPT-5.4):

- Accepted: align hard-acceptance wording with backend fallback policy.
- Accepted: make documentation-scope wording consistent across `Progress`, milestones, and concrete steps.

Critical review rules for external suggestions (still enforced):

- Reject suggestions that change Case 1/Case 2 benchmarks or tolerances.
- Reject suggestions that reorder case output by completion time instead of definition order.
- Reject suggestions that silently continue when any worker fails.
- Reject suggestions that enable nested inner-search parallelism in verification cases by default.
- Reject suggestions that depend on runtime calibration/probing to choose worker counts.

Implementation starts only after a recorded consensus decision that satisfies the above constraints.

## Plan of Work

Milestone 1 updates CLI contract and worker resolution semantics. The contract is fixed before coding:

- `python -m slope_stab.cli verify` means requested mode `auto_parallel` with requested workers `0`.
- `python -m slope_stab.cli verify --serial` means requested mode `serial` and canonical debug behavior.
- `python -m slope_stab.cli verify --workers N` means explicit worker override in auto-parallel mode.
- Any `--serial` + `--workers` combination is a validation error.

Worker resolution remains deterministic: `workers=0 -> min(4, effective_cpu_count)`, explicit workers clamped to available CPU.

Milestone 2 updates verification runner interfaces to expose execution metadata needed for debugging and review. The verify JSON payload will include a dedicated top-level `execution` object with fields `requested_mode`, `resolved_mode`, `decision_reason`, `backend`, `requested_workers`, `resolved_workers`, and `evidence_version`.

Backend policy is explicit in this milestone: prefer process workers for parallel mode; when process workers are unavailable and thread backend is selected, default verify auto mode resolves serial unless an explicit verification thread-policy whitelist entry is introduced in a future evidence-backed change.

Milestone 3 adds tests. Unit tests cover worker resolution rules, backend-resolution policy, and argument validation. Regression tests cover CLI default behavior (no flags), explicit serial behavior, deterministic case ordering, and deterministic failure surfaces for worker exceptions. Coverage expansion is kept efficient: one subprocess-level `cli verify` regression plus targeted unit tests for edge cases.

Milestone 4 updates documentation. `AGENTS.md` will capture the new non-negotiable verify-mode expectations. `README.md` quick-start and parallel sections will describe default parallel verify and serial debugging commands. Explainer scope is narrowed to files that currently discuss `cli verify` behavior (`docs/auto-refine-explainer.md`, `docs/direct-global-explainer.md`).

Milestone 5 runs full validation and closes the plan. The required gate (`cli verify` and full unittest discovery) must pass without changing benchmark references. Progress, decisions, and outcomes are then finalized in this ExecPlan.

## Concrete Steps

Run all commands from:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Pre-change baseline (already measured in this plan; re-run before coding if environment changed):

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify --workers 1
    $env:PYTHONPATH='src'; python -m slope_stab.cli verify --workers 2

Implementation sequence:

    1. Update `src/slope_stab/cli.py` with default-parallel verify argument semantics and serial debug control.
    2. Update `src/slope_stab/verification/runner.py` to support deterministic worker resolution and execution metadata plumbing.
    3. Update/add tests:
       tests/regression/test_cli_verify.py
       tests/integration/test_verification_cases.py
       tests/unit/test_verification_runner_workers.py (new)
    4. Update docs:
       AGENTS.md
       README.md
       docs/auto-refine-explainer.md
       docs/direct-global-explainer.md

Validation commands after implementation:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    $env:PYTHONPATH='src'; python -m slope_stab.cli verify --workers 1
    $env:PYTHONPATH='src'; python -m unittest discover -s tests -p "test_*.py"

Expected acceptance transcript fragments:

    - default `cli verify` completes with `all_passed: true`.
    - explicit serial debug path completes with identical pass/fail outcomes and case order.
    - no benchmark target/tolerance drift in Case 1 or Case 2.

## Validation and Acceptance

Hard acceptance:

- `python -m slope_stab.cli verify` uses parallel case scheduling by default when effective CPU availability is greater than 1 and process backend is available; otherwise it resolves deterministically according to the documented backend policy.
- Explicit serial debugging path is available and documented.
- Case result ordering in JSON remains identical to `VERIFICATION_CASES` definition order.
- Any worker failure still fails deterministically with explicit error; no partial-success summaries.
- Built-in verification case count and benchmark targets remain unchanged.

Regression acceptance:

- `tests/regression/test_cli_verify.py` validates default behavior and serial override behavior.
- `tests/integration/test_verification_cases.py` remains passing with stable outcomes.
- New worker-resolution unit tests cover `workers=0`, clamping, serial override, and invalid argument combinations.

Gate acceptance:

- `python -m slope_stab.cli verify` passes.
- `python -m unittest discover -s tests -p "test_*.py"` passes.

## Idempotence and Recovery

This change is fully rerunnable. If default-parallel behavior causes host-specific instability, debugging must use the explicit serial path first to isolate case-level correctness from scheduling behavior.

If regressions appear, recovery must not modify benchmark fixtures or tolerances. Revert only verification scheduling/CLI argument changes and re-run the full verification gate to restore baseline behavior.

## Artifacts and Notes

Baseline timing evidence captured for planning (non-gating):

- `verify --workers 1`: `361.54s`
- `verify --workers 2`: `352.85s`
- `verify --workers 4`: `354.13s`
- `verify --workers 8`: `356.20s`

These timings do not prove a universal runtime optimum worker count. They support using a deterministic bounded policy (`workers=0 => min(4, available)`) for consistency with existing repository worker-resolution semantics and resource control.

## Interfaces and Dependencies

CLI interface target:

- `python -m slope_stab.cli verify` should default to parallel-capable execution.
- Serial debug must be explicitly available and documented.
- Worker resolution remains deterministic and bounded.

Code interface target:

- `src/slope_stab/verification/runner.py` should expose deterministic worker resolution helpers used by `cli verify`.
- Verification output should include additive execution metadata sufficient to diagnose resolved mode/worker/backend.

Dependencies remain unchanged (`numpy`, `scipy`, `cma` required by existing optimization/search paths). No new runtime dependencies are permitted for this work.

Plan revision note: Added on 2026-03-23 to define a consensus-gated implementation path for default-parallel `cli verify` with explicit serial debugging and mandatory documentation alignment.

Plan revision note (2026-03-23, post GPT-5.4 review): tightened CLI contract, backend policy, metadata schema, and scope boundaries; accepted most review amendments and explicitly rejected fail-fast failure collection for determinism reasons.

Plan revision note (2026-03-23, post GPT-5.4 v2 review): added strict `--serial` conflict policy, adopted conservative thread-fallback serial behavior for default verify auto mode, and removed new verification explainer from scope.

Plan revision note (2026-03-23, post GPT-5.4 v3 review): reconciled acceptance wording with backend fallback policy and normalized documentation-scope wording across plan sections.

Plan revision note (2026-03-23, implementation complete): shipped CLI/runner/docs/tests updates for default verify auto mode + serial override contract, added execution metadata, and closed after full gate success.

Plan status: Closed.

# Implement Groundwater v1 (Water Surfaces with Hu + Ru Coefficient) with Case 5/6 Bishop+Spencer Verification Gates

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan is embedded in that file and must be maintained in accordance with the requirements in that same file.

## Purpose / Big Picture

Users will be able to run groundwater-enabled analyses using two explicit methods under `loads.groundwater`: `water_surfaces` and `ru_coefficient`. `water_surfaces` will support both `Hu` custom values and `Hu` automatic calculation for inclined water surfaces, and `ru_coefficient` will model pore pressure from a per-material Ru value. The change is complete when Case 5 and Case 6 benchmarks pass for both Bishop and Spencer in built-in verification, while all existing baseline verification behavior remains unchanged.

## Progress

- [x] (2026-03-27 16:25 +13:00) Reviewed current groundwater placeholders and confirmed active groundwater models are currently rejected in parser (`loads.groundwater.model != "none"`).
- [x] (2026-03-27 16:35 +13:00) Reviewed user-provided Case 5/6 assets and confirmed benchmark reports include both Bishop and Spencer global minimum outputs.
- [x] (2026-03-27 16:45 +13:00) Extracted Water Parameters semantics from attached Slide2 documentation PDF, including equation forms for custom and auto Hu.
- [x] (2026-03-27 16:55 +13:00) Drafted initial consensus-gated groundwater ExecPlan.
- [x] (2026-03-27 17:40 +13:00) Completed GPT-5.4 review round 1 triage and revised the plan to remove ambiguity in discretization, Ru formula, and test scope.
- [x] (2026-03-27 18:05 +13:00) Added explicit verification sequencing: prescribed-surface Case 5/6 checks are mandatory and must pass before any groundwater search checks are added/executed.
- [x] (2026-03-27 18:22 +13:00) Completed GPT-5.4 review round 2, triaged all suggestions, and revised this plan.
- [x] (2026-03-27 18:25 +13:00) Recorded explicit Codex + GPT-5.4 consensus for the groundwater ExecPlan scope and sequencing.
- [x] (2026-03-27 22:05 +13:00) Implemented parser/model/slice/solver groundwater paths for `water_surfaces` and `ru_coefficient`, including deterministic water-surface node handling and solver pore-pressure coupling.
- [x] (2026-03-27 22:28 +13:00) Added/extended Case 5/6 regression + verification coverage (Bishop + Spencer), then passed full gates (`cli verify`, `cli test`).

## Surprises & Discoveries

- Observation: Local Case 5 and Case 6 references are present under `Verification/Bishop/Case 5` and `Verification/Bishop/Case 6`, and each report includes both Bishop and Spencer result sections.
  Evidence: `Case5_Hu=1.rfcreport`, `Case5_Hu=Auto.rfcreport`, and `Case6.rfcreport` each contain `Method: bishop simplified` and `Method: spencer`.

- Observation: Reported benchmark FoS values for the added groundwater references are:
  Evidence: Case 5 Hu=1 -> Bishop `1.116900`, Spencer `1.117220`; Case 5 Hu=Auto -> Bishop `1.157570`, Spencer `1.157480`; Case 6 Ru -> Bishop `1.001250`, Spencer `1.018880`.

- Observation: Slide2 Water Parameters semantics are explicit enough to pin equations and validation ranges.
  Evidence: Attached PDF states `u = gamma_w * h * Hu`, `Hu_auto = cos^2(alpha)`, and states Ru "between 0 and 1 must be specified"; it also states Ru vertical earth pressure excludes external loads.

- Observation: Existing solver path has pore-force fields on slices/results but solver equations do not currently consume pore pressure in resistance terms.
  Evidence: `SliceGeometry` includes `pore_force`, but Bishop/Spencer currently compute using `weights = total_vertical_force` and do not subtract pore-pressure contributions.

- Observation: Built-in verify coverage count is currently fixed at 29 and does not include Case 5/6 yet.
  Evidence: `tests/integration/test_verification_cases.py` asserts 29 outcomes; `src/slope_stab/verification/cases.py` currently defines Case 1-4 and surcharge/global variants only.

## Decision Log

- Decision: Scope groundwater v1 to two explicit methods only: `water_surfaces` and `ru_coefficient`, with no seismic work in this plan.
  Rationale: Meets owner-requested direction, preserves bounded scope, and aligns with prior consensus ordering (groundwater before seismic).
  Date/Author: 2026-03-27 / Codex

- Decision: Enforce a hard external consensus gate before implementation starts.
  Rationale: Owner requested that implementation is not permitted until Codex and GPT-5.4 agree on direction and plan.
  Date/Author: 2026-03-27 / Codex

- Decision: Treat Hu auto semantics as `Hu = cos^2(alpha)` and pore pressure as `u = gamma_w * h * Hu`.
  Rationale: Directly matches symbols recovered from attached Slide2 Water Parameters documentation.
  Date/Author: 2026-03-27 / Codex

- Decision: Use explicit deterministic Water Surfaces discretization with base-wise integration nodes and deterministic kink tie-break rules.
  Rationale: Addresses review concern that prior wording was under-specified and could produce non-reproducible implementation choices.
  Date/Author: 2026-03-27 / Codex

- Decision: Use explicit Ru operational equations in implementation:
  - `sigma_v = W_soil / slice.width`
  - `u = ru * sigma_v`
  - `U = u * slice.base_length`
  - Ru uses `W_soil = slice.weight` only, not external loads.
  Rationale: Removes ambiguity and directly enforces documented Slide2 exclusion of external loads from Ru vertical pressure.
  Date/Author: 2026-03-27 / Codex

- Decision: Keep `ru` validation range hard-clamped to `[0, 1]`.
  Rationale: GPT-5.4 concern was valid if unsupported; attached Slide2 text explicitly states Ru must be between 0 and 1, so clamping is reference-backed, not invented policy.
  Date/Author: 2026-03-27 / Codex

- Decision: Add explicit surcharge+Ru exclusion regression.
  Rationale: This is a subtle but high-risk interaction now that surcharge is baseline-supported and Ru is being added.
  Date/Author: 2026-03-27 / Codex

- Decision: Avoid duplicate benchmark sources in `tests/fixtures` for Case 5/6.
  Rationale: Use `Verification/Bishop/Case 5-6` as the single source of truth for benchmark targets and keep expected values centralized in verification case definitions to reduce drift.
  Date/Author: 2026-03-27 / Codex

- Decision: External GPT-5.4 review v1 suggestions triaged as: accepted (discretization specificity, explicit Ru formula, surcharge+Ru regression, fixture-duplication reduction); rejected (relax Ru range).
  Rationale: Rejected item conflicts with explicit attached Slide2 admissible-range statement.
  Date/Author: 2026-03-27 / Codex

- Decision: Consensus remains pending after review round 1.
  Rationale: GPT-5.4 explicitly reported "close, but no consensus yet."
  Date/Author: 2026-03-27 / Codex

- Decision: Groundwater verification sequencing is prescribed-first: add and pass Case 5/6 prescribed-surface checks before any groundwater search checks are introduced or run.
  Rationale: Matches owner directive and enforces verification-first progression from deterministic baseline surfaces to search behavior.
  Date/Author: 2026-03-27 / Codex + Owner directive

- Decision: External GPT-5.4 review v2 suggestions triaged as accepted (solver insertion specificity and explicit v1 strict-coverage documentation note); no additional blocking issues raised.
  Rationale: Both suggestions improve implementation safety and user expectation clarity without changing scope or baseline policies.
  Date/Author: 2026-03-27 / Codex

- Decision: Consensus obtained for Groundwater ExecPlan scope and sequencing.
  Rationale: Codex + GPT-5.4 agree plan is bounded, verification-first, and implementation-ready.
  Date/Author: 2026-03-27 / Codex + GPT-5.4

- Decision: Preserve slope-direction consistency by normalizing solver trigonometric sign handling from driving-moment direction while keeping absolute driving-moment magnitudes.
  Rationale: Required to support both Right-to-Left and Left-to-Right benchmark geometries deterministically (Case 6).
  Date/Author: 2026-03-27 / Codex

- Decision: Spencer groundwater coupling uses effective-base-force form (`cL_eff = cL - U*tan(phi)`, `N' = N-U`) rather than direct `W_eff` substitution.
  Rationale: Direct `W_eff` substitution failed prescribed benchmarks and caused invalid `m_alpha`; effective-base coupling matched Case 5/6 benchmarks and preserved dry/surcharge baselines.
  Date/Author: 2026-03-27 / Codex

## Outcomes & Retrospective

Current status:

- Groundwater v1 implementation is complete for `water_surfaces` and `ru_coefficient`.
- Prescribed Case 5/6 Bishop+Spencer checks are implemented and passing.
- Full required gates are passing (`python -m slope_stab.cli verify`, `python -m slope_stab.cli test`).

Remaining to completion:

- None for this plan scope.

## Context and Orientation

Groundwater placeholders exist but are inactive:

- `src/slope_stab/models.py` defines `GroundwaterInput(model="none")` and slice fields (`pore_force`, `pore_x_app`, `pore_y_app`).
- `src/slope_stab/io/json_io.py` currently rejects active groundwater models (`model != "none"`).
- `src/slope_stab/slicing/slice_generator.py` initializes pore terms to zero for all slices.
- `src/slope_stab/lem_core/bishop.py` and `src/slope_stab/lem_core/spencer.py` do not yet apply pore-pressure reductions in effective-normal/shear terms.
- `src/slope_stab/verification/cases.py` and `tests/integration/test_verification_cases.py` do not yet include Case 5/6 groundwater verification coverage.

Reference artifacts to drive verification:

- `Verification/Bishop/Case 5/Hu=1/Case5_Hu=1.rfcreport`
- `Verification/Bishop/Case 5/Hu=Auto/Case5_Hu=Auto.rfcreport`
- `Verification/Bishop/Case 6/Case6.rfcreport`
- Supporting model snapshots in matching `.sli` files for geometry/water-surface metadata.

In this plan:

- "Water Surfaces method" means pore pressure computed from a water-surface polyline and Hu semantics.
- "Ru method" means pore pressure computed as a fraction of vertical earth pressure per slice.
- "Hu custom" means explicit user-specified `0 <= Hu <= 1`.
- "Hu auto" means `Hu = cos^2(alpha)` where `alpha` is local water-surface inclination above the evaluation point.

## External Review Gate

Before any code implementation milestone starts, complete the following review protocol:

1. Share the full current ExecPlan text with GPT-5.4.
2. Record every GPT-5.4 suggestion in `Decision Log` as accepted/rejected with rationale.
3. Revise the plan text to incorporate accepted suggestions.
4. Present the full revised ExecPlan to the owner after each review round.
5. Repeat until explicit consensus entry is recorded:

   - `Decision: Consensus obtained for Groundwater ExecPlan scope and sequencing.`
   - `Rationale: Codex + GPT-5.4 agree plan is bounded, verification-first, and implementation-ready.`

Implementation is blocked until this entry exists in this plan.

## Plan of Work

Milestone 1 defines groundwater JSON/model contract and validation rules. Extend `loads.groundwater` from stub to explicit config:

- `model = "none"` (backward-compatible).
- `model = "water_surfaces"` with:
  - required `surface` polyline points `[[x, y], ...]` (minimum two points, strictly increasing `x`).
  - required `hu.mode` in `{ "custom", "auto" }`.
  - `hu.value` required when mode is `custom` and constrained to `[0, 1]`.
  - optional `gamma_w` (default `9.81 kN/m^3`).
- `model = "ru_coefficient"` with:
  - required `ru` in `[0, 1]` (reference-backed by attached Slide2 doc).

Milestone 2 implements groundwater load models in isolated load modules and wires them into slicing with fully specified deterministic mechanics.

Water Surfaces discretization rule:

- For each slice, build deterministic integration nodes along x:
  - start with `[x_left, x_right]`,
  - add any interior water-surface polyline vertex x-values that lie strictly within `(x_left, x_right)`,
  - sort unique ascending.
- For each node x:
  - evaluate base y at x (using slice base linearization consistent with slice base angle convention),
  - evaluate water-surface y and local slope from the containing polyline segment.
- Segment selection tie-break at polyline vertices:
  - if `x` equals an interior vertex, use the segment to the right,
  - for the final vertex, use the segment to the left.
- Coverage rule:
  - if any required node x is outside water-surface polyline x-range, fail the surface explicitly (prescribed run errors; search candidate invalidates deterministically with explicit reason).
- At each node:
  - `h = y_water - y_base`,
  - `h_eff = max(h, 0)`,
  - `Hu = hu.value` for custom,
  - `Hu = cos^2(alpha)` for auto, where `alpha = arctan(local_slope)`,
  - `u = gamma_w * h_eff * Hu`.
- Integrate pore resultant over slice base by piecewise trapezoid:
  - `U_segment = 0.5 * (u_i + u_{i+1}) * ds_segment`,
  - `ds_segment = (x_{i+1} - x_i) / cos(alpha_slice_base)`,
  - `U = sum(U_segment)`.
- Resultant application:
  - `pore_x_app` uses U-weighted centroid of segment midpoints along base projection,
  - `pore_y_app` is the base ordinate at `pore_x_app`.

Ru operational formula (explicit):

- `W_soil = slice.weight` (soil self-weight only; excludes `external_force_y`).
- `sigma_v = W_soil / slice.width`.
- `u = ru * sigma_v`.
- `U = u * slice.base_length`.
- Ru therefore excludes surcharge/seismic/external loads by construction.

Milestone 3 integrates pore effects in solver equations for both Bishop and Spencer while preserving all existing no-groundwater behavior.

Solver insertion contract (explicit, required):

- Bishop insertion:
  - use pore vertical projection in resistance equations (`W_eff = total_vertical_force - U*cos(alpha)`),
  - keep driving denominator/moment terms based on total vertical force unchanged.
- Spencer insertion:
  - use effective-base coupling (`cL_eff = cL - U*tan(phi)`, `N' = N-U`) in `_compute_state`,
  - keep driving denominator/moment terms based on total vertical force unchanged.
- Preserve existing finite checks, final-iteration `m_alpha` validity rule, and zero-shear clamp behavior exactly as-is.

Milestone 4 adds verification/test coverage with explicit prescribed-first sequencing.

- Milestone 4A (mandatory first): prescribed-surface groundwater checks.
  - Extend built-in verification definitions in `src/slope_stab/verification/cases.py` for prescribed Case 5/6 checks:
    - Case 5 Hu=1 (bishop + spencer),
    - Case 5 Hu=Auto (bishop + spencer),
    - Case 6 Ru (bishop + spencer).
  - Do not add duplicate Case 5/6 benchmark fixtures in `tests/fixtures`; use verification assets and centralized expected values as the single benchmark source.
  - Add regression tests validating:
    - prescribed FoS benchmark parity for the above cases,
    - metadata includes resolved groundwater inputs and per-slice pore outputs,
    - dry behavior (`h <= 0`, or water-surface none where applicable),
    - surcharge+Ru interaction rule: pore terms for Ru remain unchanged when surcharge is toggled (given identical geometry/surface/material/ru).
  - Update integration/regression expectations for increased verify case count.

- Milestone 4B (deferred until 4A is green): groundwater search checks.
  - Any groundwater search benchmark/parity/oracle checks are out of scope for initial Case 5/6 onboarding and must not be started until all 4A prescribed checks pass in the same branch.

Milestone 5 updates docs and closes the plan.

- Update `AGENTS.md` baseline/support sections and verification gate description to include groundwater Case 5/6 coverage.
- Update `README.md` load schema and examples for `water_surfaces` and `ru_coefficient`.
- Add `docs/groundwater-explainer.md` with formulas, tie-break rules, deterministic behavior, and an explicit v1 limitation note:
  - strict water-surface coverage rule (out-of-range required x-values cause failure/invalidation rather than dry extrapolation).
- Re-run full required gate and finalize living sections.

## Concrete Steps

Run all commands from:

    C:/Users/JamesMcKerrow/Stanley Gray Limited/SP - ENG/Technical/JAMES TECHNICAL/Codex/SlopeStab

Always set:

    $env:PYTHONPATH='src'

Consensus rounds (no implementation yet):

    1. Share full ExecPlan text with GPT-5.4.
    2. Capture review notes in a local text artifact.
    3. Update this plan's Decision Log with accept/reject rationale.
    4. Present full updated ExecPlan to owner.

Implementation sequence after consensus:

    1. Update models + parser:
       src/slope_stab/models.py
       src/slope_stab/io/json_io.py
    2. Add groundwater load modules and integrate slice calculations:
       src/slope_stab/loads/
       src/slope_stab/slicing/slice_generator.py
    3. Apply pore-force usage in solvers:
       src/slope_stab/lem_core/bishop.py
       src/slope_stab/lem_core/spencer.py
    4. Add/extend tests (prescribed-first ordering):
       tests/unit/test_loads_schema.py
       tests/unit/test_groundwater_slice_forces.py (new)
       tests/regression/test_groundwater_case5_case6.py (new)
       tests/regression/test_groundwater_ru_surcharge_exclusion.py (new)
       tests/integration/test_verification_cases.py
       tests/regression/test_cli_verify.py
    5. Extend built-in verification cases:
       src/slope_stab/verification/cases.py
    6. Update docs:
       AGENTS.md
       README.md
       docs/groundwater-explainer.md (new)
       docs/surcharge-explainer.md (cross-reference update)

Verification commands after implementation:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    $env:PYTHONPATH='src'; python -m slope_stab.cli test

Targeted groundwater checks:

    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_groundwater_case5_case6
    $env:PYTHONPATH='src'; python -m unittest tests.regression.test_groundwater_ru_surcharge_exclusion
    $env:PYTHONPATH='src'; python -m unittest tests.unit.test_groundwater_slice_forces

## Validation and Acceptance

Hard acceptance:

- `loads.groundwater.model` accepts `none`, `water_surfaces`, and `ru_coefficient` with explicit validation errors for malformed/unsupported payloads.
- Water Surfaces calculations follow the exact discretization contract above (node construction, segment tie-break, out-of-range behavior, `u = gamma_w * h * Hu`, trapezoidal base integration, deterministic resultant location).
- Ru calculations follow exact operational equations:
  - `sigma_v = W_soil / slice.width`,
  - `u = ru * sigma_v`,
  - `U = u * slice.base_length`,
  - `W_soil = slice.weight` only (external loads excluded).
- Solver resistance uses pore-pressure effects deterministically for both Bishop and Spencer.
- Existing no-load and surcharge verification behavior remains unchanged (no regression to Case 1-4 and existing surcharge/global policies).
- Groundwater verification onboarding is prescribed-first: Case 5/6 prescribed checks must pass before any groundwater search checks are introduced or run.

Groundwater benchmark acceptance (new):

- Case 5 (Water Surfaces, Hu=1):
  - Bishop FoS ~= `1.116900` within agreed tolerance.
  - Spencer FoS ~= `1.117220` within agreed tolerance.
- Case 5 (Water Surfaces, Hu=Auto):
  - Bishop FoS ~= `1.157570` within agreed tolerance.
  - Spencer FoS ~= `1.157480` within agreed tolerance.
- Case 6 (Ru Coefficient):
  - Bishop FoS ~= `1.001250` within agreed tolerance.
  - Spencer FoS ~= `1.018880` within agreed tolerance.
- Ru+surcharge regression:
  - for matched surfaces, changing surcharge does not change Ru-derived pore terms.

Gate acceptance:

- `python -m slope_stab.cli verify` passes with updated case count.
- `python -m slope_stab.cli test` passes.
- If groundwater search checks are added in a later step, they are gated behind a prior green run of the prescribed Case 5/6 groundwater checks.

## Idempotence and Recovery

All steps are additive and rerunnable. If groundwater implementation introduces drift:

- First isolate by rerunning only groundwater-targeted tests.
- If baseline cases drift, revert groundwater-specific parser/slice/solver edits only; do not alter established Case 1/2 benchmark targets or tolerances.
- Re-run full verification gate after each rollback/reapply cycle.

## Artifacts and Notes

Groundwater benchmark references extracted during planning:

- Case 5 Hu=1 report: Bishop `FS=1.116900`, Spencer `FS=1.117220`.
- Case 5 Hu=Auto report: Bishop `FS=1.157570`, Spencer `FS=1.157480`.
- Case 6 Ru report: Bishop `FS=1.001250`, Spencer `FS=1.018880`.

Slide2 Water Parameters equations from attached PDF:

- `u = gamma_w * h * Hu`
- `Hu_auto = cos^2(alpha)`
- Ru admissible range: `0 <= ru <= 1`.

These references must remain fixed unless owner-approved re-baselining is documented.

## Interfaces and Dependencies

Proposed interface targets:

- In `src/slope_stab/models.py`, define groundwater config types with explicit fields for:
  - water-surface polyline
  - Hu mode/value
  - gamma_w
  - Ru value
- In `src/slope_stab/io/json_io.py`, parse/validate new groundwater payloads with deterministic errors.
- In `src/slope_stab/slicing/slice_generator.py`, compute slice-level `pore_force` and application points from groundwater model outputs.
- In `src/slope_stab/lem_core/bishop.py` and `src/slope_stab/lem_core/spencer.py`, consume pore terms in effective-normal/shear calculations.
- In `src/slope_stab/analysis.py`, expose groundwater input metadata in outputs (matching existing load metadata pattern).

Dependency policy:

- Keep runtime dependencies unchanged (`numpy`, `scipy`, `cma` required as-is).
- Do not introduce new runtime dependencies for groundwater v1.

Plan revision note: Added on 2026-03-27 to define a consensus-gated groundwater v1 implementation path supporting Water Surfaces (Hu custom + auto) and Ru Coefficient methods with Case 5/6 Bishop+Spencer verification targets.

Plan revision note (2026-03-27, post GPT-5.4 review v1): tightened groundwater discretization and Ru formulas, added surcharge+Ru exclusion regression, removed benchmark-fixture duplication plan, retained Ru [0,1] clamp with explicit source justification, and left plan in consensus-pending state.

Plan revision note (2026-03-27, post GPT-5.4 review v2): recorded explicit consensus, added solver insertion contract for Bishop/Spencer (`W_eff = total_vertical_force - pore_force` in resistance-equation paths), and added explicit documentation requirement that strict water-surface coverage behavior is an intentional v1 limitation.

Plan revision note (2026-03-27, implementation complete): shipped groundwater parser/model/slicing/solver updates, added Case 5/6 prescribed verification and regression coverage (Bishop + Spencer), and closed after full gate success.

Plan status: Closed.
```
