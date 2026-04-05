# Codify the Slide2 Reverse-Curvature Invariant for Auto-Refine

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md` at repo root. This ExecPlan must be maintained in accordance with that file. This plan builds on `docs/execplans/auto-refine-slide2-iteration1-candidate-generation-parity.md`, but it is narrower and more specific: it only codifies the reverse-curvature rule that Slide2 documents for circular searches and then measures whether that rule explains any of the remaining iteration-1 extras.

## Purpose / Big Picture

After this change, the auto-refine candidate generator will make Slide2's reverse-curvature rule explicit instead of leaving it as an implicit consequence of the current lower-arc implementation. Users inspecting the one-iteration comparison cases will be able to see, in code, diagnostics, tests, and plots, whether any current or stored Slide2 surfaces violate that rule. The expected visible outcome is not a new parity win. The expected visible outcome is clarity: the reverse-curvature count should stay zero for the one-iteration Slide2 comparison cases, proving that this rule is a correctness invariant rather than the missing explanation for the remaining over-generated surfaces.

This plan intentionally does not try to solve the remaining `ours_only` surfaces. If the reverse-curvature counts stay zero, the next follow-on work should focus on interval-selection or candidate-pruning behavior, not reverse curvature.

## Progress

- [x] (2026-04-04 22:38 +13:00) Re-read `PLANS.md`, `docs/execplans/auto-refine-slide2-iteration1-candidate-generation-parity.md`, `src/slope_stab/search/auto_refine.py`, `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py`, `scripts/diagnostics/plot_case4_iter1_simple_surfaces.py`, and `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py` to confirm the current iteration-1 parity instrumentation.
- [x] (2026-04-04 22:39 +13:00) Re-checked the official Slide2 circular-search documentation and paraphrased the relevant rule into this plan: Grid Search can produce reverse-curvature circles, while Auto Refine Search says reverse-curvature surfaces are not possible because of the way the circles are generated.
- [x] (2026-04-04 22:41 +13:00) Measured the current iteration-1 comparison sets against the official reverse-curvature definition and confirmed zero reverse-curvature surfaces in every stored Slide2 set and every generated set for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`.
- [x] (2026-04-04 22:45 +13:00) Added an explicit reverse-curvature guard to `src/slope_stab/search/auto_refine.py` so candidate generation rejects any clipped surface whose stored endpoints or sampled lower-arc ordinates rise above the circle center.
- [x] (2026-04-04 22:48 +13:00) Extended `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py` to report reverse-curvature counts for `slide2`, `ours`, `shared`, `slide2_only`, and `ours_only`.
- [x] (2026-04-04 22:51 +13:00) Updated `scripts/diagnostics/plot_case4_iter1_simple_surfaces.py` so the Case 4 comparison plots render the reverse-curvature counts directly on the figure.
- [x] (2026-04-04 22:54 +13:00) Added unit and regression coverage that proves malformed endpoint-above-center surfaces are rejected by the new helper and that the three iteration-1 comparison cases still contain zero reverse-curvature surfaces.
- [x] (2026-04-04 23:17 +13:00) Re-ran `python scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py` and confirmed the parity counts stayed unchanged while the reverse-curvature counts remained zero for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`.
- [x] (2026-04-04 23:18 +13:00) Regenerated the Case 4 plot artifacts so the figures now display the zero reverse-curvature counts directly on the image.
- [x] (2026-04-04 23:19 +13:00) Ran the focused unittest command `python -m unittest tests.unit.test_search_auto_refine tests.regression.test_auto_refine_slide2_iteration1_candidate_generation`; it passed with the pre-existing exact-parity assertion still marked as one `expectedFailure`.
- [x] (2026-04-04 23:36 +13:00) Ran the required repository gate. `python -m slope_stab.cli verify` passed, and `python -m slope_stab.cli test` passed with the expected-failure iteration-ladder and exact-set parity diagnostics still intact.

## Surprises & Discoveries

- Observation: The official Slide2 documentation makes a stronger claim than the user hypothesis.
  Evidence: The circular Grid Search documentation discusses reverse-curvature circles as a real possibility, but the Auto Refine Search documentation says reverse-curvature surfaces are not possible for auto-refine because of the way those circles are generated.

- Observation: The remaining iteration-1 extras are not reverse-curvature surfaces under that official definition.
  Evidence: Before any code changes for this plan, the comparison harness measured `0` reverse-curvature surfaces in all three generated sets and all three Slide2 sets. The pre-change counts were:
  `Case2_Search_Iter_1: ours 0 / 1702, slide2 0 / 1562, ours_only 0 / 140`
  `Case4_Iter1: ours 0 / 4597, slide2 0 / 4536, ours_only 0 / 61`
  `Case4_Iter1_Simple: ours 0 / 40, slide2 0 / 38, ours_only 0 / 2`

- Observation: In this repository, "reverse curvature" is best represented as a lower-branch invariant, not as a center-height heuristic.
  Evidence: Many valid shared Slide2 surfaces have `yc` below the crest elevation, so "center below upper slope y" alone is far too broad. The useful invariant is whether the analyzed circular arc rises above its own center. Our lower-branch representation keeps that count at zero.

- Observation: Making the reverse-curvature rule explicit does not change the iteration-1 parity counts.
  Evidence: After the new guard landed, the refreshed comparison harness still reports
  `Case2_Search_Iter_1: shared=1562, slide2_only=0, ours_only=140`
  `Case4_Iter1: shared=4536, slide2_only=0, ours_only=61`
  `Case4_Iter1_Simple: shared=38, slide2_only=0, ours_only=2`
  with `reverse_curvature(ours=0, slide2=0)` for all three cases.

- Observation: The first implementation of the helper falsely reported reverse curvature after the `.s01` surface sets were quantized to six decimals.
  Evidence: Reconstructing a rounded surface key can move a tangent endpoint just outside the exact circle domain, which initially triggered the helper's fallback path. Replacing that hard failure with a domain tolerance tied to `2 * r * tol` restored the correct zero-count result.

## Decision Log

- Decision: Implement reverse-curvature handling as an explicit invariant in `src/slope_stab/search/auto_refine.py`, even though current evidence says it will be a no-op for the tracked iteration-1 cases.
  Rationale: The user asked for Slide2 alignment, and the official Slide2 docs make reverse-curvature impossibility part of the auto-refine contract. Encoding that contract directly makes the behavior easier to reason about and protects against future regressions that might accidentally introduce upper-arc behavior.
  Date/Author: 2026-04-04 / Codex

- Decision: Define reverse curvature narrowly as "stored endpoint or sampled lower-arc ordinate rises above the circle center," not as "circle center below crest elevation."
  Rationale: The narrow definition matches the way this repository represents circular slip surfaces and avoids incorrectly rejecting many Slide2-shared surfaces.
  Date/Author: 2026-04-04 / Codex

- Decision: Treat this work as documentation-and-diagnostics alignment, not as the missing iteration-1 parity fix.
  Rationale: The measured reverse-curvature counts are already zero across the target cases, so any implementation here is clarifying and defensive, not explanatory for the remaining extras.
  Date/Author: 2026-04-04 / Codex

## Outcomes & Retrospective

Implementation and validation are complete. Auto-refine now has an explicit reverse-curvature guard, the comparison harness reports reverse-curvature counts, the Case 4 plots display those counts on the figure, and the tests pin the invariant in place.

The main result is a negative but valuable one: this rule does not reduce the current `ours_only` mismatch families. The refreshed diagnostics keep the exact same parity counts as before while reporting zero reverse-curvature surfaces in both our generated sets and Slide2's stored sets. That is strong local evidence that the next iteration-1 parity investigation must focus on some other Slide2 pruning or interval-selection rule.

The repository gate stayed green after the change. `python -m slope_stab.cli verify` passed, and `python -m slope_stab.cli test` passed. The pre-existing exact-set regression remains an `expectedFailure`, which is correct because this plan intentionally did not solve the remaining extras.

## Context and Orientation

The one-iteration Slide2 parity work currently lives in a few concentrated places. `src/slope_stab/search/auto_refine.py` generates, clips, and filters auto-refine circular candidates before they are evaluated. `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py` compares our generated iteration-1 candidate set against the stored Slide2 `.s01` files for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`. `scripts/diagnostics/plot_case4_iter1_simple_surfaces.py` renders the shared and mismatched surface families for the Case 4 one-iteration comparisons. `tests/unit/test_search_auto_refine.py` covers candidate-generation helper behavior, and `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py` covers the iteration-1 comparison sets.

In this plan, a "reverse-curvature surface" means a circular slip arc that rises above the circle center over the interval that is actually analyzed. That is the behavior Slide2 documents for grid-style circular searches, and it is exactly the behavior auto-refine says it does not create. In this repository, the lower circular branch is evaluated by `_circle_lower_y(...)`, so the practical question is whether any stored endpoint elevation or sampled lower-arc ordinate exceeds the center ordinate `yc`.

The three comparison cases used in this plan are:

- `Verification/Bishop/Case 2/Case2_Search_Iter_1/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01`
- `Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`
- `Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`

The existing Case 4 plot artifacts that this plan refreshes live under `tmp/plots/`. The most useful visual checkpoints are `tmp/plots/case4_iter1_simple_match_and_mismatch_overlay.png` and `tmp/plots/case4_iter1_match_and_mismatch_overlay.png`.

## Plan of Work

First, add a dedicated reverse-curvature helper in `src/slope_stab/search/auto_refine.py` close to `_circle_lower_y(...)`, because that module already owns the candidate clipping and validity rules. The helper should accept a `PrescribedCircleInput` and return `True` only when the surface violates the lower-branch invariant by rising above the center. It should use both the stored endpoints and a few sampled ordinates on the lower branch so that a malformed candidate is rejected even if future edits disturb the current assumptions.

Second, call that helper inside `_clip_construction_circle_to_ground_intercepts(...)` after the existing equal-elevation rule and before the model-floor rule. That keeps the new behavior squarely inside the auto-refine candidate-generation path and avoids any changes to prescribed-surface analysis, slice generation, or solver math.

Third, extend the comparison harness in `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py` so each scenario summary reports reverse-curvature counts for the full Slide2 set, the full generated set, the shared subset, the `slide2_only` subset, and the `ours_only` subset. The JSON artifact should carry those counts because they are now part of the parity investigation record.

Fourth, update `scripts/diagnostics/plot_case4_iter1_simple_surfaces.py` so the rendered figures display the reverse-curvature counts. The goal is not a new plot type. The goal is that the existing comparison plots now carry the extra diagnostic note directly on the image so a human reviewer can tell at a glance whether reverse curvature is present.

Fifth, add tests. In `tests/unit/test_search_auto_refine.py`, add one malformed surface whose stored endpoint is above its center and prove the helper flags it, plus one known Slide2-style clipped surface and prove the helper does not flag it. In `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py`, add a scenario loop that proves all three comparison cases contain zero reverse-curvature surfaces in the Slide2 set, the generated set, and the `ours_only` set.

Finally, rerun the comparison harness, rerender the Case 4 plots, and rerun the required repository gate. Update the benchmark JSON, the plot artifacts, and this plan with the observed outputs.

## Concrete Steps

All commands below must run from the repository root `C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab` with `PYTHONPATH=src`.

Run the focused comparison harness and expect the same parity counts as before, plus explicit zero reverse-curvature counts:

    $env:PYTHONPATH='src'; python scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py

Expected summary shape:

    Case2_Search_Iter_1: shared=1562 slide2_only=0 ours_only=140 reverse_curvature(ours=0, slide2=0)
    Case4_Iter1: shared=4536 slide2_only=0 ours_only=61 reverse_curvature(ours=0, slide2=0)
    Case4_Iter1_Simple: shared=38 slide2_only=0 ours_only=2 reverse_curvature(ours=0, slide2=0)

Refresh the Case 4 plots:

    $env:PYTHONPATH='src'; python scripts/diagnostics/plot_case4_iter1_simple_surfaces.py --scenario case4_iter1_simple
    $env:PYTHONPATH='src'; python scripts/diagnostics/plot_case4_iter1_simple_surfaces.py --scenario case4_iter1

Run the focused tests first:

    $env:PYTHONPATH='src'; python -m unittest tests.unit.test_search_auto_refine tests.regression.test_auto_refine_slide2_iteration1_candidate_generation

Then run the required repository gate in sequence:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    $env:PYTHONPATH='src'; python -m slope_stab.cli test

## Validation and Acceptance

Acceptance for this plan is deliberately narrow and observable.

The code-level acceptance is that `src/slope_stab/search/auto_refine.py` contains an explicit reverse-curvature guard in the candidate-generation path, and the new unit test proves that a malformed endpoint-above-center surface is flagged while a known Slide2-style clipped surface is not.

The diagnostic acceptance is that `docs/benchmarks/auto_refine_slide2_iteration1_candidate_generation_current.json` now includes reverse-curvature counts for every comparison case and those counts are zero for `slide2`, `ours`, `shared`, `slide2_only`, and `ours_only`.

The visual acceptance is that the refreshed Case 4 plots in `tmp/plots/` show the reverse-curvature counts on the figure. A human reviewer should be able to open `tmp/plots/case4_iter1_simple_match_and_mismatch_overlay.png` or `tmp/plots/case4_iter1_match_and_mismatch_overlay.png` and immediately see that the reverse-curvature counts are zero.

The repository acceptance is that `python -m slope_stab.cli verify` and `python -m slope_stab.cli test` both pass after the change.

The parity-interpretation acceptance is that the parity counts remain unchanged. If `slide2_only` and `ours_only` counts stay the same while reverse-curvature counts stay zero, this plan has still succeeded because it proves that reverse curvature is not the missing iteration-1 pruning rule.

## Idempotence and Recovery

This plan is safe to repeat. The comparison harness overwrites a JSON artifact, and the plot script overwrites PNG files in `tmp/plots/`. Re-running either command is the intended way to refresh evidence after future edits.

If a validation command fails, start by re-running the focused unittest command so you can tell whether the failure is local to the reverse-curvature work or an unrelated repository issue. If the comparison harness or plots show nonzero reverse-curvature counts for the tracked cases, inspect the new helper first and then inspect any recent changes to endpoint snapping or circle clipping before touching solver code.

## Artifacts and Notes

The important artifact for this plan is the updated benchmark JSON:

- `docs/benchmarks/auto_refine_slide2_iteration1_candidate_generation_current.json`

The important visual artifacts are the refreshed Case 4 overlay plots:

- `tmp/plots/case4_iter1_simple_match_and_mismatch_overlay.png`
- `tmp/plots/case4_iter1_match_and_mismatch_overlay.png`

Representative command output after the final helper adjustment:

    Case2_Search_Iter_1: shared=1562 slide2_only=0 ours_only=140 reverse_curvature(ours=0, slide2=0)
    Case4_Iter1: shared=4536 slide2_only=0 ours_only=61 reverse_curvature(ours=0, slide2=0)
    Case4_Iter1_Simple: shared=38 slide2_only=0 ours_only=2 reverse_curvature(ours=0, slide2=0)

Focused regression output:

    Ran 40 tests in 17.214s
    OK (expected failures=1)

Repository gate outcome:

    python -m slope_stab.cli verify  -> all_passed: true
    python -m slope_stab.cli test    -> all_passed: true

The important code locations are:

- `src/slope_stab/search/auto_refine.py`
- `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py`
- `scripts/diagnostics/plot_case4_iter1_simple_surfaces.py`
- `tests/unit/test_search_auto_refine.py`
- `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py`

## Interfaces and Dependencies

No new third-party dependency is needed for this plan. The code continues to use the existing `matplotlib` diagnostic plotting path and the existing `PrescribedCircleInput` model.

At the end of the plan, `src/slope_stab/search/auto_refine.py` must expose a private helper with the effective shape:

    def _surface_has_reverse_curvature(surface: PrescribedCircleInput, tol: float = ...) -> bool:
        ...

That helper must be used inside `_clip_construction_circle_to_ground_intercepts(...)` before evaluation. The comparison harness and tests may import the private helper because it is diagnostic infrastructure rather than public library API.

Plan revision note: Created on 2026-04-04 after the user proposed that the remaining one-iteration extras might be reverse-curvature surfaces. Completed the same day after measuring the current sets, landing an explicit invariant guard plus diagnostics, correcting a rounding-induced false-positive in the first helper version, refreshing the benchmark JSON and plot artifacts, and rerunning the full repository gate.
