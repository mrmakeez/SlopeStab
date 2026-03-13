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
# Implement Slide2-Style Auto-Refine Circular Search with Case 3 Parity Gates

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

## Surprises & Discoveries

- Observation: Case 3 includes finite Slide2 model boundaries, even though current code uses infinite toe/crest profile conventions.
  Evidence: `External Boundary` table in `Verification/Bishop/Case 3/Case3/Case3-i.rfcreport` lists points `(70,20)`, `(70,35)`, `(50,35)`, `(30,25)`, `(20,25)`, `(20,20)`.

- Observation: Case 3 `.s01` confirms exactly `19000` generated three-point surfaces and `9696` valid surfaces, with global minimum matching the report.
  Evidence: `* #three point surfaces 19000`, and parsing all `surface 0 data` rows gives min FS `0.986442` at center `(30.259066..., 51.791949...)`.

- Observation: Slide2 doc text explains the iterative refine workflow but leaves several implementation details implicit (exact random-point generation and refinement polyline construction details).
  Evidence: Doc states circles are generated from random points and later divisions are generated on an interpolated polyline through low-FOS divisions, but equation images and averaging details are not fully textual on the page.

- Observation: Straight iterative narrowing could drift away from toe/crest-adjacent minima for Case 3-like geometry.
  Evidence: Deterministic refinement improved parity when a bounded toe/crest local refinement pass was added after core iterations.

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

- Decision: Keep Case 3 parity outside `cli verify` initially.
  Rationale: Owner selected separate regression coverage first while preserving built-in verification scope.
  Date/Author: 2026-03-14 / Codex

## Outcomes & Retrospective

Delivered outcomes:

- Added search-capable input schema (`search.method = auto_refine_circular`) while preserving prescribed mode compatibility.
- Implemented deterministic auto-refine circular search with per-iteration diagnostics.
- Integrated search dispatch into analysis workflow and metadata output.
- Added unit tests for parser behavior, default limits, per-iteration surface counts, and deterministic repeatability.
- Added separate Case 3 parity regression test.
- Ran required gate and full test discovery with passing results.

Gaps intentionally left:

- Case 3 parity is intentionally outside built-in `cli verify`.
- Additional/alternative search methods remain deferred.

## Context and Orientation

Current baseline flow:

`src/slope_stab/io/json_io.py` now parses mutually exclusive modes: prescribed-surface or search.
`src/slope_stab/analysis.py` dispatches to prescribed solving or auto-refine search and returns one governing result.
`src/slope_stab/search/auto_refine.py` contains deterministic search logic and diagnostics.
`src/slope_stab/verification/cases.py` still contains Case 1 and Case 2 prescribed benchmarks only.

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

## Plan of Work

Implemented sequence:

1. Added additive interfaces and parser validation for search mode.
2. Implemented deterministic auto-refine search path and diagnostics.
3. Integrated dispatch and output metadata without altering prescribed verification behavior.
4. Added separate Case 3 fixture and tests.
5. Validated against required gate and full test suite.

## Concrete Steps

Run all commands from repository root:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Baseline safety check before code edits:

    python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Run targeted search coverage:

    python -m unittest discover -s tests -p "test_*.py" -k auto_refine
    python -m slope_stab.cli analyze --input tests/fixtures/case3_auto_refine.json

Run full verification gate:

    python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Expected high-level transcript markers after completion:

    verify output reports all_passed=true for existing baseline cases.
    case3 regression test passes in unittest discovery and enforces parity gates.

## Validation and Acceptance

Non-regression gates (hard):

- Existing Case 1 and Case 2 verification values and tolerances remain exactly unchanged.
- Existing verification and unit/regression commands complete successfully.

Case 3 parity gates (hard):

- `abs(FOS - 0.986442) <= 0.001`
- endpoint coordinate absolute error <= `0.20 m` for each of `x_left, y_left, x_right, y_right`
- radius relative error <= `10%`

Case 3 diagnostic-only parity metrics:

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

Plan revision note: Updated on 2026-03-14 to reflect implemented behavior, resolved decisions, final parity gates, and verification outcomes.
```

