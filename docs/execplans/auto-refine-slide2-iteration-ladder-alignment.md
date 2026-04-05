# ExecPlan: Align Auto-Refine Circular Search with Slide2 Iteration Ladders

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md` at repo root. This ExecPlan must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, users who run `search.method = "auto_refine_circular"` will get iteration behavior that more closely matches the saved Slide2 verification projects for Case 2 and Case 4, not just the final one-shot benchmark result. The core search should keep following the retained low-factor-of-safety divisions instead of collapsing them into one broad `x` window, and the final refinement stage should be explicit, deterministic, and easier to explain.

The user-visible proof is twofold. First, new regression coverage will compare our `before_post_polish` and `after_post_polish` stages against the Slide2 Iter 1, Iter 2, Iter 3, and final verification files for Case 2 and Case 4. Second, the existing final parity gates for Case 3 and Case 4, plus the broader repository verification gate, will remain green.

## Progress

- [x] (2026-04-04 12:46 +13:00) Re-read `PLANS.md`, `src/slope_stab/search/auto_refine.py`, `src/slope_stab/analysis.py`, and current auto-refine regression coverage to confirm the current implementation shape and output contract.
- [x] (2026-04-04 12:46 +13:00) Parsed Slide2 Case 2 and Case 4 Iter 1, Iter 2, Iter 3, and final `.rfcreport` files for both Bishop and Spencer and compared them to our `before_post_polish` and `after_post_polish` outputs.
- [x] (2026-04-04 12:46 +13:00) Confirmed the current core loop already matches the Slide2-style midpoint-pair and linear-beta candidate generation for Case 2 Iter 1, but stalls afterward when retained divisions are non-contiguous.
- [x] (2026-04-04 12:46 +13:00) Confirmed the current post-polish stage materially improves final parity but becomes almost iteration-insensitive by Iter 1 or Iter 2 on the Case 2 and Case 4 ladders.
- [x] (2026-04-04 12:46 +13:00) Inspected the saved `.slmd` bundles and confirmed they store this search as `maxcoverage search` with the same `divisionsalong`, `circlesperdiv`, `iterations`, and `percentkept` values as the reports.
- [x] (2026-04-04 12:46 +13:00) Ran "Opt Off" forensic comparisons for `Case2_Search_Iter_1` and `Case4_Iter1` and confirmed that zeroing the exposed `optimize` and `optimization_option` flags in the `.slsc` file does not change the reported minimum surface or the `.s01` body.
- [x] (2026-04-04 13:18 +13:00) Added `scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py` and captured the pre-change ladder baseline to `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`.
- [x] (2026-04-04 13:23 +13:00) Replaced the core loop's `next_x_min..next_x_max` collapse with a retained-path representation in `src/slope_stab/search/auto_refine.py`, and exposed `active_path_segments` plus `next_active_path_segments` in `iteration_diagnostics`.
- [x] (2026-04-04 13:24 +13:00) Added retained-path unit coverage in `tests/unit/test_search_auto_refine.py` and confirmed the helper-level and live-diagnostic checks pass.
- [x] (2026-04-04 13:31 +13:00) Captured the post-change ladder artifact to `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json` and measured the `before_post_polish` prototype deltas against the current baseline.
- [x] (2026-04-04 13:39 +13:00) Added `tests/regression/test_auto_refine_slide2_iteration_ladders.py` as an executable prototype harness. The Milestone 3 acceptance checks are present but intentionally marked `expectedFailure` because the retained-path-only change did not meet the improvement bar.
- [x] (2026-04-04 15:49 +13:00) Confirmed with `Case4_Iter1_Simple` that Slide2 stores circles which pass through division-point construction locations but are clipped to later ground intercepts before evaluation.
- [x] (2026-04-04 16:09 +13:00) Implemented construction-point intercept clipping in `src/slope_stab/search/auto_refine.py` so auto-refine circles are canonicalized to lower-arc/ground intercepts before evaluation.
- [x] (2026-04-04 16:10 +13:00) Added unit coverage for the `Case4_Iter1_Simple` clipping example and confirmed the new clipped candidate canonicalization passes.
- [x] (2026-04-04 16:28 +13:00) Captured `docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json` and measured the new core-stage deltas against the current baseline.
- [x] (2026-04-04 16:40 +13:00) Removed the speculative Milestone 4 gap-padding and shared-ranking runtime heuristics after they proved unnecessary for the clipping hypothesis and muddied parity behavior.
- [ ] Re-evaluate the remaining unresolved core-search mechanics before changing supplementary optimization. Construction-point clipping is a major missing behavior, but it is still not sufficient on its own.
- [ ] Replace the current auto-refine-only post-polish with an explicit supplementary optimization stage only after the core-stage prototype gate is genuinely passing.
- [ ] Preserve the current direct-global, cuckoo-global, and CMA-ES local refinement behavior unless separate evidence justifies changing those methods too.
- [ ] Update docs and run the required verification gate after implementation.

## Surprises & Discoveries

- Observation: Our current `before_post_polish` winner already lands on the same endpoint pair and radius family as Slide2 Case 2 Iter 1, which means the basic midpoint-pair generation and beta sweep are not the main problem.
  Evidence: Case 2 Bishop Slide2 Iter 1 reports left `(10.1, 10.05)`, right `(28.565, 17.5)`, radius `15.231`; our `before_post_polish` for 1 iteration uses the same geometry family.

- Observation: The current core search can freeze across later iterations even when Slide2 keeps moving.
  Evidence: For Case 2 Bishop and Spencer, our `before_post_polish` stays at the Iter 1 surface for Iter 2, Iter 3, and final, while Slide2 moves through `(28.565 -> 27.952 -> 27.952 -> 28.073)` on the right endpoint.

- Observation: The current `after_post_polish` stage improves final parity but mostly erases iteration-count sensitivity.
  Evidence: For Case 4 Bishop, our `after_post_polish` is already about `FOS 1.234215` at Iter 1 and stays there through Iter 15, while Slide2 moves from `1.23590` at Iter 1 to `1.23469` at final with different right endpoints and radii.

- Observation: The "optimize off" experiments did not change the engineering result in either Case 2 Iter 1 or Case 4 Iter 1.
  Evidence: The modified `.rfcreport` files differ only in metadata noise such as project title, file name, compute time, and temporary image paths; the `.s01` files differ only in the first version-header line and are otherwise byte-for-byte identical.

- Observation: Changing the current auto-refine post-polish helpers in place would unintentionally change other search methods.
  Evidence: `src/slope_stab/search/direct_global.py`, `src/slope_stab/search/cuckoo_global.py`, and `src/slope_stab/search/cmaes_global.py` import refinement helpers from `src/slope_stab/search/auto_refine.py`.

- Observation: The dedicated baseline artifact makes the current core-stage mismatch measurable instead of anecdotal.
  Evidence: `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json` records mean `before_post_polish` ladder errors of `0.095225` for Case 2 Bishop, `0.096221` for Case 2 Spencer, `0.403926` for Case 4 Bishop, and `0.570304` for Case 4 Spencer.

- Observation: The retained-path implementation does preserve non-contiguous kept regions, but that alone does not reproduce the saved Slide2 ladder.
  Evidence: Case 2 Bishop Iteration 1 now produces three `next_active_path_segments`, yet the global incumbent remains the Iter 1 surface through Iter 2, Iter 3, and final.

- Observation: The retained-path-only change helps one ladder, leaves one unchanged, and makes one worse.
  Evidence: Comparing `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json` against `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`, the mean `before_post_polish` ladder-error delta is `0.00%` for Case 2 Bishop, `0.00%` for Case 2 Spencer, `-30.73%` for Case 4 Bishop, and `+23.82%` for Case 4 Spencer, where positive means improvement.

- Observation: The retained-path-only change is still compatible with the existing final-stage parity checks.
  Evidence: `tests.regression.test_case3_auto_refine`, `tests.regression.test_case4_auto_refine`, and `tests.regression.test_auto_refine_slide2_case2_case4_alignment` all passed after the core-loop refactor.

- Observation: `Case4_Iter1_Simple` contains both the raw construction-point circle and the clipped intercept version of the same circle.
  Evidence: In `Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`, one entry uses `(x1,y1)=(19.2015621,25)` to `(x2,y2)=(85.7984379,45)` and another entry with center `(14.2649653,162.3166928)` uses the clipped left intercept `(31.1983666,25.9586933)` with the same radius family.

- Observation: Our pre-change implementation would reject the `Case4_Iter1_Simple` construction-point circle even though Slide2 keeps it.
  Evidence: The equivalent prescribed circle raises `GeometryError: Negative slice height while integrating area segment [19.2016, 21.865472]` in our current prescribed-surface path unless it is clipped to the later ground intercept.

- Observation: Construction-point intercept clipping materially improves three of the four `before_post_polish` ladder comparisons.
  Evidence: Comparing `docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json` against `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`, mean normalized ladder-error improvement is `+44.84%` for Case 2 Spencer, `+26.18%` for Case 4 Bishop, and `+58.46%` for Case 4 Spencer, while Case 2 Bishop remains unchanged at `0.00%`.

- Observation: The speculative Milestone 4 heuristics were not the right direction once clipping was implemented.
  Evidence: The temporary gap-padding and shared-ranking variants produced mixed results and also pushed existing parity tests over tolerance; removing them while keeping intercept clipping restored the existing Case 3/Case 4 parity regressions to green.

## Decision Log

- Decision: Target the saved Slide2 verification-project behavior, not only the public algorithm description.
  Rationale: The user provided Iter 1, Iter 2, Iter 3, and final verification files, and those saved outputs are the strongest repository-local evidence of what Slide2 actually does for these cases.
  Date/Author: 2026-04-04 / Codex

- Decision: Treat `before_post_polish` as the core auto-refine stage and `after_post_polish` as a separate supplementary optimization stage.
  Rationale: The saved ladder behavior and the current implementation both show that one stage is the iterative retain-and-repeat search and another stage is a later local-improvement step; separating them is necessary for honest diagnostics and targeted alignment.
  Date/Author: 2026-04-04 / Codex

- Decision: Prototype the retained-path composite polyline fix before replacing the supplementary optimization stage.
  Rationale: The current evidence strongly suggests the min/max `x` collapse is a real core mismatch, and this fix is cheaper and safer than immediately redesigning the refinement stage.
  Date/Author: 2026-04-04 / Codex

- Decision: Do not silently change the direct-global, cuckoo-global, or CMA-ES refinement behavior as part of this plan.
  Rationale: Those methods currently reuse auto-refine helpers, but this plan is specifically about aligning `auto_refine_circular`; changing all search methods at once would blur regressions and violate the verification-first principle.
  Date/Author: 2026-04-04 / Codex

- Decision: Preserve the current `before_post_polish` and `after_post_polish` metadata keys for backward compatibility, even if new stage names are added.
  Rationale: Existing regression coverage and diagnostics already depend on those keys.
  Date/Author: 2026-04-04 / Codex

- Decision: Land the Milestone 3 ladder checks as `expectedFailure` prototype tests instead of hard pass/fail regressions for now.
  Rationale: The retained-path-only change did not satisfy the agreed prototype acceptance criteria, but keeping the checks executable preserves the target behavior and the gap-to-goal without breaking the repository gate.
  Date/Author: 2026-04-04 / Codex

- Decision: Do not move into supplementary optimization redesign until the core ladder mechanics are re-evaluated.
  Rationale: The post-change artifact shows that retained-path-only narrowing is not sufficient and may even be the wrong retained-polyline interpretation for some cases, especially Case 2 and Case 4 Bishop.
  Date/Author: 2026-04-04 / Codex

- Decision: Treat division-point pairs as circle-construction points and clip the resulting lower arc to actual ground intercepts before evaluation in auto-refine.
  Rationale: `Case4_Iter1_Simple` provides direct repository-local evidence that Slide2 persists these clipped surfaces, and our previous fixed-endpoint interpretation rejects circles that Slide2 clearly keeps.
  Date/Author: 2026-04-04 / Codex

- Decision: Remove the speculative Milestone 4 runtime heuristics and keep only the evidence-backed clipping change.
  Rationale: Gap-padding and shared-ranking experiments did not produce a clean or stable improvement story, while construction-point clipping alone preserved the existing parity gates and delivered clear ladder gains.
  Date/Author: 2026-04-04 / Codex

## Outcomes & Retrospective

Milestones 1 through 3 are implemented in prototype form. The repository now has a reusable ladder-capture script, a committed pre-change baseline artifact, a retained-path core-loop implementation with explicit path-segment diagnostics, a retained-path artifact, and an executable prototype regression harness.

The retained-path-only hypothesis did not clear the Milestone 3 acceptance gate. It preserved non-contiguous kept regions exactly as intended, but the measurable outcome was mixed: Case 2 did not improve at all, Case 4 Bishop regressed, and Case 4 Spencer improved materially but still missed the `25%` mean-error reduction target.

The immediate takeaway is that the original "bounding window vs retained path" diagnosis was real but incomplete. Milestone 4 added a second genuine core correction: circles in auto-refine must be treated as construction circles and then clipped to actual ground intercepts before they are evaluated.

That clipping change is a meaningful step forward. It explains the `Case4_Iter1_Simple` evidence, restores compatibility with the existing Case 3/Case 4 parity regressions, and materially improves three of the four ladder comparisons. But it still does not solve Case 2 Bishop, so there is at least one additional unresolved core mismatch before the supplementary optimization stage should be redesigned.

## Context and Orientation

The current auto-refine implementation lives in `src/slope_stab/search/auto_refine.py`. It divides a current ground polyline into equal arc-length divisions, takes one midpoint from each division, generates circles for every midpoint pair using a linear beta schedule, averages factor of safety by division, keeps the lowest-average divisions, and repeats. After that iterative loop, it runs three deterministic local refinement passes and reports both the core-stage winner (`before_post_polish`) and the final winner (`after_post_polish`) through `src/slope_stab/analysis.py`.

In this repository, a "retained division" is one of the lowest-average divisions selected for the next auto-refine iteration. A "composite retained path" is the ordered collection of only those kept ground segments, with discarded gaps removed from the retained arc length. This term matters because the current code does not keep such a path; it only keeps `next_x_min` and `next_x_max`, which fills in discarded gaps whenever the retained divisions are non-contiguous.

The Slide2 verification assets used in this plan are:

- `Verification/Bishop/Case 2/Case2_Search_Iter_1/Case2_Search_Iter_1-i.rfcreport`
- `Verification/Bishop/Case 2/Case2_Search_Iter_2/Case2_Search_Iter_2-i.rfcreport`
- `Verification/Bishop/Case 2/Case2_Search_Iter_3/Case2_Search_Iter_3-i.rfcreport`
- `Verification/Bishop/Case 2/Case2_Search/Case2_Search-i.rfcreport`
- `Verification/Bishop/Case 4/Case4_Iter1/Case4_Iter1-i.rfcreport`
- `Verification/Bishop/Case 4/Case4_Iter2/Case4_Iter2-i.rfcreport`
- `Verification/Bishop/Case 4/Case4_Iter3/Case4_Iter3-i.rfcreport`
- `Verification/Bishop/Case 4/Case4/Case4-i.rfcreport`

The matching `.slmd` bundles are zip archives that contain a `.slsc` configuration file and a `.s01` result file. In those bundles, this search appears under `maxcoverage search`, which stores `divisionsalong`, `circlesperdiv`, `iterations`, and `percentkept`. The public Slide2 help text describes the iterative retain-and-repeat loop, but the saved project behavior also shows a later refinement effect that is not disabled by changing the exposed `optimize` flags in the `.slsc`.

Current repository files that matter for this work are:

- `src/slope_stab/search/auto_refine.py`
- `src/slope_stab/analysis.py`
- `src/slope_stab/search/direct_global.py`
- `src/slope_stab/search/cuckoo_global.py`
- `src/slope_stab/search/cmaes_global.py`
- `scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py`
- `tests/unit/test_search_auto_refine.py`
- `tests/regression/test_case3_auto_refine.py`
- `tests/regression/test_case4_auto_refine.py`
- `tests/regression/test_auto_refine_slide2_case2_case4_alignment.py`
- `tests/regression/test_auto_refine_slide2_iteration_ladders.py`
- `docs/auto-refine-explainer.md`
- `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`
- `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json`
- `docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json`
- `docs/benchmarks/auto_refine_slide2_case2_case4_new.json`
- `docs/benchmarks/auto_refine_post_polish_ab.json`
- `docs/benchmarks/auto_refine_post_polish_ab.md`

## Plan of Work

### Milestone 1: Capture a Ladder Baseline and Make the Current Mismatch Observable

Create a dedicated diagnostic script, `scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py`, that does for the Iter 1/2/3/final ladder what `capture_slide2_auto_refine_case2_case4.py` already does for the final cases. The new script must parse the saved Slide2 reports for Case 2 and Case 4, both Bishop and Spencer, and then run our current analysis at the matching iteration counts to capture `before_post_polish`, `after_post_polish`, and normalized error metrics.

Write the resulting artifact to `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`. The artifact must include the Slide2 reference surface, our stage outputs, and a normalized ladder error per row. Define normalized ladder error as:

    endpoint_rel = (abs(dx_left) + abs(dx_right)) / (2 * H)
    center_rel = center_distance / H
    ladder_error = abs(dFOS) + endpoint_rel + center_rel + radius_rel_delta

where `H` is the scenario slope height from the case geometry. This metric is dimensionless and lets later milestones prove objective improvement without relying only on narrative comparisons.

Do not add failing regression tests in this milestone. The output of this script is the baseline that later milestones must beat.

### Milestone 2: Replace the Bounding-Window Core Loop with a Composite Retained Path

Refactor the core loop in `src/slope_stab/search/auto_refine.py` so the next iteration is built from the retained divisions themselves, not from one continuous `x_min..x_max` envelope. Introduce an internal retained-path representation that can describe multiple kept ground sub-segments in order.

The key rule is this: discarded gaps contribute zero retained arc length. If divisions `4`, `5`, and `14` are kept, the next iteration must divide and sample only those kept sub-segments, not the discarded span between them.

Implement this with new helpers inside `src/slope_stab/search/auto_refine.py` or a nearby module:

1. Build the initial retained path from the configured search limits.
2. Divide total retained arc length across the retained path only.
3. Sample boundaries and midpoints across only the kept segments, preserving their order.
4. After ranking divisions, rebuild the retained path from the kept boundary intervals only.
5. Merge adjacent kept intervals that share an endpoint within a tight deterministic tolerance.
6. Keep retained-path diagnostics so later tests can confirm that non-contiguous kept regions are not silently re-expanded.

The candidate generation rule itself must remain unchanged in this milestone. The midpoint-pair loop and linear beta schedule already appear to be close to Slide2 for the initial family, so this milestone focuses only on how the search narrows.

### Milestone 3: Prototype Gate for the Core Fix

Once the composite retained path is implemented, rerun `capture_slide2_auto_refine_iteration_ladders.py` and store the result as `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json`.

Then add a regression test, `tests/regression/test_auto_refine_slide2_iteration_ladders.py`, that checks two prototype outcomes for `before_post_polish`:

1. The `before_post_polish` ladder must no longer collapse to one repeated surface when the saved Slide2 ladder changes. For Case 2 and Case 4, both Bishop and Spencer, the tuple `(x_left, x_right, r)` for Iter 1, Iter 2, Iter 3, and final must not all be identical once this milestone is complete.
2. The mean normalized ladder error for `before_post_polish` must improve by at least 25% versus `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json` for each of the four case-method combinations.

This is a prototyping milestone. If the retained-path change fails either gate, do not continue into the supplementary optimization rewrite without first updating this plan's `Decision Log` and `Surprises & Discoveries` sections to explain why.

### Milestone 4: Re-evaluate the Core Ladder Mechanics Before Touching Supplementary Optimization

The retained-path-only prototype established that the existing `x_min/x_max` collapse was not the whole story. Before any supplementary-optimization redesign, resolve the remaining core mismatch with a focused round of experiments driven by the new ladder artifacts and diagnostics.

The leading open hypotheses are:

1. Slide2 may not be compressing retained divisions with zero gap length the way this prototype assumes.
2. Slide2 may use a different division score or tie rule than our straight average-FOS ranking.
3. Slide2 may carry iteration incumbents or ranking data differently when later iterations do not beat earlier ones.
4. Slide2 may handle Case 2 Bishop construction-circle ranking differently even after intercept clipping.

Use `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`, `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json`, `docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json`, and the `iteration_diagnostics.active_path_segments` / `next_active_path_segments` data to test these hypotheses one at a time. Do not proceed until the `before_post_polish` prototype gate in `tests/regression/test_auto_refine_slide2_iteration_ladders.py` can be converted away from `expectedFailure`.

### Milestone 5: Isolate Legacy Refinement and Build an Explicit Supplementary Optimization Stage

Once the core-stage ladder gate is genuinely passing, isolate the current shared refinement helpers before changing auto-refine refinement behavior. Move the existing helper implementations into a new shared module such as `src/slope_stab/search/legacy_post_polish.py`, and repoint the direct-global, cuckoo-global, and CMA-ES search paths there so their behavior stays unchanged.

Then create an auto-refine-only supplementary optimization stage in a new module such as `src/slope_stab/search/auto_refine_supplementary.py`. This stage must be explicit in name and deterministic in mechanics. It must start from the core auto-refine winner and search a local neighborhood of that incumbent instead of immediately sweeping broad toe/crest windows.

Use a bounded pattern-search style implementation in endpoint-plus-angle space. A good parameterization for this repository is `(x_left, x_right, beta)`, because the existing geometry helpers already construct circles from endpoints and tangent angle. The step schedule must be deterministic, the direction order must be fixed, and the search must stop on explicit size or evaluation-count limits. The stage may include a narrow toe-anchored recovery branch only if the incumbent is already close to the toe and the retained-path diagnostics justify it; if that branch is added, document the trigger and bounds in code comments and in this plan.

This new supplementary stage must populate the existing `after_post_polish` metadata, but it should also be serialized under a clearer alias such as `search.stage_outputs.supplementary_optimization` so future readers do not have to infer what "post polish" means.

### Milestone 6: Ladder Regressions, Final Parity, and Documentation

Extend `tests/regression/test_auto_refine_slide2_iteration_ladders.py` so `after_post_polish` is compared against the saved Slide2 Iter 1/2/3/final ladders for Case 2 and Case 4, both Bishop and Spencer. The acceptance rule for each saved ladder row is:

- `abs(dFOS) <= 0.01`
- `abs(dx_left) <= 0.40 m`
- `abs(dx_right) <= 0.40 m`
- `radius_rel_delta <= 0.12`

In addition, the mean normalized ladder error for `after_post_polish` must improve versus `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json` for each case-method pair.

Keep the existing final parity regressions green:

- `tests/regression/test_case3_auto_refine.py`
- `tests/regression/test_case4_auto_refine.py`
- `tests/regression/test_auto_refine_slide2_case2_case4_alignment.py`

Update `docs/auto-refine-explainer.md` so it explains three distinct concepts in plain language: the core retain-and-repeat search, the retained-path composite polyline, and the supplementary optimization stage. The explainer must no longer present the current broad toe/crest sweeps as if they were the documented Slide2 core algorithm.

## Concrete Steps

Run all commands from:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Always set:

    $env:PYTHONPATH='src'

Baseline capture before implementation:

    python scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py --implementation-label current --output docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json

Targeted checks during Milestone 2 and Milestone 3:

    python -m unittest tests.unit.test_search_auto_refine
    python -m unittest tests.regression.test_auto_refine_slide2_iteration_ladders

Prototype evidence commands completed for Milestones 1 through 3:

    python scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py --implementation-label current --output docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json
    python scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py --implementation-label retained_path --output docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json

Prototype evidence commands completed for Milestone 4:

    python scripts/diagnostics/capture_slide2_auto_refine_iteration_ladders.py --implementation-label construction_intercept_clipped --output docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json

Case-specific parity checks after supplementary optimization work lands:

    python -m unittest tests.regression.test_case3_auto_refine
    python -m unittest tests.regression.test_case4_auto_refine
    python -m unittest tests.regression.test_auto_refine_slide2_case2_case4_alignment
    python -m unittest tests.regression.test_auto_refine_slide2_iteration_ladders

Full required gate after implementation:

    python scripts/benchmarks/run_guarded_gate.py

If `run_guarded_gate.py` is unavailable or intentionally skipped for a local debugging pass, use the repository's required commands one stage at a time with the repo-standard environment rules:

    python -m slope_stab.cli verify
    python -m slope_stab.cli test

## Validation and Acceptance

Hard non-regression acceptance:

- `tests/regression/test_case3_auto_refine.py` passes.
- `tests/regression/test_case4_auto_refine.py` passes.
- `tests/regression/test_auto_refine_slide2_case2_case4_alignment.py` passes.
- The full required gate passes without loosening existing Case 3 or Case 4 final tolerances.

Core-stage prototype acceptance:

- `before_post_polish` no longer remains the same repeated surface across the full Iter 1/2/3/final ladder for Case 2 and Case 4 when the saved Slide2 ladder changes.
- The mean normalized ladder error for `before_post_polish` improves by at least 25% versus `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json` for each of:
  - Case 2 Bishop
  - Case 2 Spencer
  - Case 4 Bishop
  - Case 4 Spencer

Current status after Milestones 1 through 3:

- Not met. The executable prototype checks live in `tests/regression/test_auto_refine_slide2_iteration_ladders.py` as `expectedFailure` until the core-stage hypothesis is revised and the gate is actually passing.

Final-stage ladder acceptance:

- For every saved ladder row in Case 2 and Case 4, both Bishop and Spencer, `after_post_polish` satisfies:
  - `abs(dFOS) <= 0.01`
  - `abs(dx_left) <= 0.40 m`
  - `abs(dx_right) <= 0.40 m`
  - `radius_rel_delta <= 0.12`
- The mean normalized ladder error for `after_post_polish` improves versus `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json` for each case-method pair.

Behavioral acceptance:

- The auto-refine explainer clearly distinguishes the documented core loop from the repository's supplementary optimization stage.
- Direct-global, cuckoo-global, and CMA-ES regression behavior remains unchanged unless this plan is explicitly amended to cover those methods too.

## Idempotence and Recovery

All planned changes are additive or refactoring-safe if executed in order. If the retained-path prototype fails its improvement gate, keep the diagnostic capture script and regression harness, revert only the core-loop changes, and record the failed hypothesis in this plan before trying a different narrowing rule.

If the new supplementary optimization stage causes drift in direct-global, cuckoo-global, or CMA-ES tests, move those methods back to the isolated legacy refinement module immediately and rerun the targeted regressions before changing auto-refine again.

Do not change the established Case 3 or Case 4 expected values or their tolerances as part of this plan. If those final gates fail, treat that as a regression in the new implementation rather than a reason to re-baseline.

## Artifacts and Notes

Known baseline observations from the research pass that motivated this plan:

- Case 2 Iter 1 already matches the Slide2 midpoint-pair geometry family in `before_post_polish`.
- Case 2 `before_post_polish` currently freezes from Iter 1 through final, while Slide2 keeps moving.
- Case 4 `after_post_polish` currently reaches near-final parity almost immediately, while the saved Slide2 ladder still changes across Iter 1, Iter 2, Iter 3, and final.
- Zeroing the exposed `optimize` and `optimization_option` fields in the Case 2 Iter 1 and Case 4 Iter 1 `.slsc` files does not change the reported engineering result.

Additional milestone artifacts now captured in-repo:

- `docs/benchmarks/auto_refine_slide2_iteration_ladders_current.json`
- `docs/benchmarks/auto_refine_slide2_iteration_ladders_retained_path.json`
- `docs/benchmarks/auto_refine_slide2_iteration_ladders_construction_intercept_clipped.json`

These two artifacts are now the concrete "before" and "after retained-path" baselines for future iterations of this plan.
They are joined by the new clipping artifact, which is now the best current evidence-backed core variant.

These observations should be copied into the new ladder baseline artifact so the next contributor can see the "before" state without re-running the whole research pass first.

## Interfaces and Dependencies

Expected internal interfaces after implementation:

- `src/slope_stab/search/auto_refine.py` continues to expose:

    run_auto_refine_search(...)

  but its internal active-search representation changes from a simple `x_min/x_max` window to a retained-path composite polyline.

- A new internal retained-path type exists in `src/slope_stab/search/auto_refine.py` or a nearby helper module. It must be able to:
  - represent ordered retained ground sub-segments
  - compute total retained arc length
  - sample boundaries and midpoints across retained sub-segments only
  - rebuild itself from kept division boundaries

- A new auto-refine-only supplementary optimization module exists, for example:

    src/slope_stab/search/auto_refine_supplementary.py

  It must accept the incumbent surface, the profile, the search limits, and the evaluation callback, and return a deterministic improved surface or the unchanged incumbent.

- The current shared refinement behavior used by other global-search methods must be isolated in a dedicated module such as:

    src/slope_stab/search/legacy_post_polish.py

- `src/slope_stab/analysis.py` must continue to emit `before_post_polish` and `after_post_polish`, and may add a nested `stage_outputs` payload for clearer naming.

No new runtime dependencies are allowed. Keep using the current project stack (`numpy`, `scipy`, `cma`) and the existing geometry/search helpers where they fit.

Plan revision note: Created on 2026-04-04 after reviewing the current auto-refine implementation, the new Case 2 and Case 4 Iter 1/2/3/final verification ladders, the saved `.slmd` bundles, and the negative-result "Opt Off" experiments for Case 2 Iter 1 and Case 4 Iter 1. Revised on 2026-04-04 after Milestones 1 through 3 landed in prototype form, including the new ladder artifacts, retained-path diagnostics, `expectedFailure` prototype harness, and the finding that retained-path-only narrowing is not sufficient. Revised again on 2026-04-04 after Milestone 4 established construction-point intercept clipping as a second major core correction, removed the speculative Milestone 4 heuristics, and captured the new clipping artifact plus targeted regression results.
