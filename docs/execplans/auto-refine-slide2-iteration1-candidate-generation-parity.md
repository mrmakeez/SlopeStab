# Achieve Slide2 Iteration-1 Candidate-Generation Parity for Auto-Refine Circular Search

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes `PLANS.md` at repo root. This ExecPlan must be maintained in accordance with that file. This plan also builds on `docs/execplans/auto-refine-slide2-iteration-ladder-alignment.md`, but it is intentionally narrower: it stops at iteration-1 candidate-generation parity and defers later-iteration ladder parity to a future ExecPlan.

## Purpose / Big Picture

After this change, users who inspect the first iteration of `search.method = "auto_refine_circular"` for the Slide2 verification cases will see the same candidate slip-surface families that Slide2 stores, not just a similar governing minimum. The proof will be observable in two ways. First, a new regression will compare our generated iteration-1 surface set against the Slide2 `.s01` files for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`, and it will report zero `Slide2-only` and zero `ours-only` surfaces. Second, a diagnostic plotting script will produce overlays where the current red-versus-blue mismatch families disappear because every plotted surface is shared.

This plan deliberately does not try to solve later-iteration retained-division behavior, supplementary optimization, or final ladder parity. Those are important, but they become easier to reason about only after iteration-1 candidate generation is exact.

## Progress

- [x] (2026-04-04 18:36 +13:00) Re-read `PLANS.md`, `docs/execplans/auto-refine-slide2-iteration-ladder-alignment.md`, `src/slope_stab/search/auto_refine.py`, `src/slope_stab/search/common.py`, `src/slope_stab/models.py`, and `src/slope_stab/io/json_io.py` to confirm the current candidate-generation flow and current input contract.
- [x] (2026-04-04 18:36 +13:00) Confirmed that for the one-iteration cases, every Slide2 stored surface is attributable to our midpoint construction lattice. Construction-point mismatch is no longer the leading problem.
- [x] (2026-04-04 18:36 +13:00) Confirmed that Slide2 stores no equal-entry-elevation surfaces in `Case2_Search_Iter_1`, `Case4_Iter1`, or `Case4_Iter1_Simple`.
- [x] (2026-04-04 18:36 +13:00) Confirmed that in `Case4_Iter1_Simple`, the entire `ours-only` mismatch set is explained by two rules: equal entry/exit elevation or lower-arc crossing below the Slide2 model floor.
- [x] (2026-04-04 18:36 +13:00) Confirmed that we already request five beta values per midpoint pair, but the fifth surface for rising pairs is being dropped by the `circle_from_endpoints_and_tangent` boundary guard before clipping.
- [x] (2026-04-04 20:57 +13:00) Added the iteration-1 comparison harness at `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py` and captured `docs/benchmarks/auto_refine_slide2_iteration1_candidate_generation_current.json`.
- [x] (2026-04-04 20:57 +13:00) Implemented the terminal-beta construction fix so non-flat limiting circles are no longer dropped at the construction step.
- [x] (2026-04-04 20:57 +13:00) Kept the construction-point interpretation, rejected equal-elevation clipped surfaces, and kept the model-floor validation inside candidate generation.
- [x] (2026-04-04 20:57 +13:00) Tightened candidate clipping with a larger ground-contact tolerance and breakpoint snapping of near-toe/crest/search-boundary intercepts.
- [x] (2026-04-04 20:57 +13:00) Added regression coverage in `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py` that proves `slide2_only == 0` for the three target cases and leaves the still-unmet exact-set equality as an `expectedFailure`.
- [x] (2026-04-04 21:12 +13:00) Re-ran the required repository gate. `python -m slope_stab.cli verify` and `python -m slope_stab.cli test` both passed, with the new iteration-1 regression and the pre-existing expected-failure ladder regression targets still behaving as expected.

## Surprises & Discoveries

- Observation: Construction points already match Slide2 for the one-iteration cases.
  Evidence: Every Slide2 surface in `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple` either matches one of our raw circles `(xc, yc, r)` directly or uses endpoints that are exactly on our midpoint lattice. The current gap is downstream of midpoint placement.

- Observation: Slide2 stores zero equal-elevation surfaces in the one-iteration cases we inspected.
  Evidence: Counting `y_left == y_right` surfaces in the Slide2 `.s01` files gives `0 / 1562` for `Case2_Search_Iter_1`, `0 / 4536` for `Case4_Iter1`, and `0 / 38` for `Case4_Iter1_Simple`.

- Observation: In `Case4_Iter1_Simple`, all seven `ours-only` surfaces are explained by two validity rules.
  Evidence: Five `ours-only` surfaces have `y_left == y_right`, and the remaining two have lower-arc minima below the Slide2 model floor `y = 20`. No `shared` or `Slide2-only` surfaces dip below `y = 20`.

- Observation: The apparent "missing fifth beta" is mostly not because we fail to ask for a fifth angle.
  Evidence: `_generate_slide2_betas` returns five betas per pair in the simple case, but for pair `(1,2)` the fifth candidate is rejected in `src/slope_stab/search/common.py` because `yc == max(y1, y2)` trips the current `yc <= max(y1, y2) + 1e-9` guard.

- Observation: The iteration-1 verification cases already use `search_limits` as the Slide2 side boundaries.
  Evidence: `Case2_Search_Iter_1-i.rfcreport` lists external boundary points from `x = 0` to `x = 35`, which matches the case search limits. `Case4_Iter1-i.rfcreport` and `Case4_Iter1_Simple-i.rfcreport` list external boundary points from `x = 10` to `x = 95`, which also matches the case search limits. The extra missing validity rule in current evidence is the model floor (`y = 0` for Case 2, `y = 20` for Case 4), not distinct side walls.

- Observation: `Case4_Iter1_Simple` is the most useful proving ground because it reduces the surface count while preserving the same mismatch shape.
  Evidence: The current comparison there is `38` Slide2 surfaces, `40` current surfaces, `33` shared, `5` Slide2-only, and `7` ours-only. The mismatch families are easy to visualize in `tmp/plots/case4_iter1_simple_match_and_mismatch_overlay.png`.

- Observation: Most of the missing `Case4_Iter1` surfaces were caused by our ground-contact tolerance being too tight for terminal and near-terminal roots.
  Evidence: Raising `_GROUND_DIFF_TOL` from `1e-7` to `1.5e-6` collapses `Case4_Iter1` `slide2_only` from `45` to `3` in the comparison harness, and the remaining `3` are the same circles with left intercepts off the toe by only `0.000107` to `0.000357`.

- Observation: Snapping near-breakpoint intercepts to exact toe/crest/search-boundary coordinates closes the last `Case4_Iter1` missing-surface gap.
  Evidence: With the updated snapping in `src/slope_stab/search/auto_refine.py`, the iteration-1 harness now reports `slide2_only = 0` for `Case4_Iter1`, `Case4_Iter1_Simple`, and `Case2_Search_Iter_1`.

- Observation: The remaining gap is now entirely over-generation, not missing Slide2 coverage.
  Evidence: The current harness artifact `docs/benchmarks/auto_refine_slide2_iteration1_candidate_generation_current.json` reports:
  `Case2_Search_Iter_1: shared=1562, slide2_only=0, ours_only=140`
  `Case4_Iter1: shared=4536, slide2_only=0, ours_only=61`
  `Case4_Iter1_Simple: shared=38, slide2_only=0, ours_only=2`

- Observation: The unresolved extras are dominated by terminal-beta circles plus a smaller family of shallow entry/exit delta cases.
  Evidence: In the current harness output, `Case4_Iter1` `ours_only` contains `43` beta-15 surfaces out of `61`, while `Case2_Search_Iter_1` `ours_only` contains `49` beta-10 surfaces out of `140` and many of the remainder have `|y_right - y_left|` below `0.1`.

## Decision Log

- Decision: Split iteration-1 candidate-generation parity into a dedicated ExecPlan instead of folding it into the existing ladder-parity plan.
  Rationale: The current evidence isolates a smaller, more testable problem: exact first-iteration surface-set parity. Solving that first reduces ambiguity before revisiting retained-path ladder behavior.
  Date/Author: 2026-04-04 / Codex

- Decision: Keep the construction-point interpretation as the foundation of the search.
  Rationale: The one-iteration cases now show that Slide2's stored surfaces are built from the same midpoint lattice we already generate. Reverting that interpretation would move away from the strongest direct evidence.
  Date/Author: 2026-04-04 / Codex

- Decision: Treat `search_limits.x_min` and `search_limits.x_max` as the side-boundary limits for this plan, and add only floor validation as a new explicit rule.
  Rationale: In the current one-iteration verification cases, the Slide2 external-boundary side walls already coincide with search limits. The remaining uncovered validity rule is the model floor. A floor-only addition is the narrowest change that matches the evidence.
  Date/Author: 2026-04-04 / Codex

- Decision: Implement equal-elevation rejection only in the auto-refine candidate-generation path, not in the prescribed-surface solver.
  Rationale: This plan is about Slide2-style search candidate validity. Changing the prescribed-surface solver would broaden scope and risk baseline regressions without evidence that Slide2 applies the same rule there.
  Date/Author: 2026-04-04 / Codex

- Decision: Use exact quantized surface-set parity as the acceptance target for iteration 1.
  Rationale: The user asked about surfaces generated, not only minima. Exact set equality is the clearest proof that candidate generation now matches Slide2 at iteration 1.
  Date/Author: 2026-04-04 / Codex

- Decision: Defer later-iteration ladder parity and supplementary optimization to a future ExecPlan.
  Rationale: Even perfect iteration-1 parity will not automatically solve retained-division behavior, incumbent carry-over, or final local improvement. Those need a separate, less ambiguous plan after candidate generation is exact.
  Date/Author: 2026-04-04 / Codex

- Decision: Increase the ground-contact tolerance used by intercept discovery to `1.5e-6`.
  Rationale: The remaining `Case4_Iter1` `slide2_only` surfaces were valid Slide2 circles whose right intercepts missed our acceptance check by only `O(10^-7)` to `O(10^-6)`. The broader tolerance eliminates those false negatives without creating any `slide2_only` regressions in the target cases.
  Date/Author: 2026-04-04 / Codex

- Decision: Snap clipped intercepts that land within `4e-4` of the toe, crest, or search-limit breakpoints onto the exact breakpoint coordinate.
  Rationale: Three residual `Case4_Iter1` mismatches were the same Slide2 circles with left intercepts numerically near `x = 30` but not snapped. Snapping those roots to the exact breakpoint matches Slide2's stored surface coordinates.
  Date/Author: 2026-04-04 / Codex

- Decision: Land the new exact-parity regression as an `expectedFailure` until the over-generation rules are understood.
  Rationale: The harness and zero-`slide2_only` coverage are already valuable, but exact set equality is not yet achieved. Keeping the exact assertion visible as an expected failure preserves the remaining target without breaking the repository gate.
  Date/Author: 2026-04-04 / Codex

## Outcomes & Retrospective

Implementation is partially complete. The current code now:
- keeps the non-flat terminal beta circles that Slide2 stores
- clips construction circles to ground intercepts
- rejects equal-elevation and below-floor clipped surfaces
- snaps near-breakpoint intercepts to exact toe/crest/search boundaries
- covers every Slide2 iteration-1 surface in the three target cases

What remains unresolved is over-generation. The comparison harness shows that we now have zero `slide2_only` surfaces for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`, but we still generate extra surfaces that Slide2 does not store. That means the next follow-on plan should focus on identifying Slide2's remaining candidate-pruning rule or interval-selection rule, not on basic circle construction or root clipping.

The repository gate remained green after these changes. That is a useful checkpoint because it means the candidate-generation alignment work improved Slide2 coverage without regressing the existing Bishop/Spencer verification baseline or the other circular-search methods.

## Context and Orientation

The current auto-refine implementation lives primarily in `src/slope_stab/search/auto_refine.py`. The helper that turns two construction points plus a beta angle into a circle lives in `src/slope_stab/search/common.py` as `circle_from_endpoints_and_tangent`. The search input types live in `src/slope_stab/models.py`, and JSON parsing for those inputs lives in `src/slope_stab/io/json_io.py`. Search dispatch and metadata serialization live in `src/slope_stab/analysis.py`.

In this plan, a "construction point" means one of the equal-arc-length division midpoints on the ground profile. The auto-refine search chooses two of these points, builds a circle through them, and then clips that lower arc to actual ground intercepts before evaluation. A "terminal beta" or "beta5" means the final angle in the evenly spaced beta sweep for a midpoint pair. In the simple five-circle case it is the fifth angle, not a special Slide2 keyword. A "candidate-generation parity" check means comparing the actual stored surface set `(xc, yc, r, x_left, y_left, x_right, y_right)` against the Slide2 `.s01` file, not only comparing the global minimum.

The relevant verification files are:

- `Verification/Bishop/Case 2/Case2_Search_Iter_1/Case2_Search_Iter_1-i.rfcreport`
- `Verification/Bishop/Case 2/Case2_Search_Iter_1/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01`
- `Verification/Bishop/Case 4/Case4_Iter1/Case4_Iter1-i.rfcreport`
- `Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`
- `Verification/Bishop/Case 4/Case4_Iter1_Simple/Case4_Iter1_Simple-i.rfcreport`
- `Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01`

The Slide2 external-boundary tables already tell us the model floor heights for the relevant one-iteration cases. `Case2_Search_Iter_1` uses floor `y = 0` with side limits `x = 0` and `x = 35`. `Case4_Iter1` and `Case4_Iter1_Simple` use floor `y = 20` with side limits `x = 10` and `x = 95`. Those side limits already match the search limits in our verification definitions, so this plan only needs an explicit floor-validity rule to match the current evidence.

The most important current code locations are:

- `src/slope_stab/search/common.py`
- `src/slope_stab/search/auto_refine.py`
- `src/slope_stab/models.py`
- `src/slope_stab/io/json_io.py`
- `src/slope_stab/analysis.py`
- `tests/unit/test_search_auto_refine.py`
- `src/slope_stab/verification/cases.py`
- `docs/execplans/auto-refine-slide2-iteration-ladder-alignment.md`

The most important current artifacts are:

- `tmp/plots/case4_iter1_simple_current_auto_refine_surfaces.png`
- `tmp/plots/case4_iter1_simple_slide2_surfaces.png`
- `tmp/plots/case4_iter1_simple_slide2_vs_current_overlay.png`
- `tmp/plots/case4_iter1_simple_mismatch_only_overlay.png`
- `tmp/plots/case4_iter1_simple_match_and_mismatch_overlay.png`

## Plan of Work

### Milestone 1: Build an Iteration-1 Surface-Set Comparison Harness

Create a dedicated diagnostic script at `scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py`. This script must parse the Slide2 `.s01` surface records for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple`, enumerate our current auto-refine iteration-1 candidates for the same search settings, and emit a JSON artifact that counts `shared`, `Slide2-only`, and `ours-only` surfaces after quantizing each surface to six decimal places. Six-decimal quantization is required because that is already sufficient to distinguish the current mismatch families while remaining stable across the stored Slide2 values.

The script must also classify each mismatch family by rule. At minimum, each `ours-only` surface should be marked as one of: `equal_elevation`, `below_model_floor`, `terminal_beta_missing_from_ours`, or `unclassified`. Each `Slide2-only` surface should record whether it matches one of our raw circles `(xc, yc, r)` and whether its endpoints are construction midpoints or clipped ground intercepts. This JSON artifact becomes the before-and-after proof for the later milestones.

If practical, the script should also regenerate the current plotting artifacts in `tmp/plots/`, because the visual overlays are already helping explain the mismatch to a human reviewer.

### Milestone 2: Fix Terminal-Beta Construction So the Fifth Circle Can Exist

Update `src/slope_stab/search/common.py` so `circle_from_endpoints_and_tangent` no longer discards the limiting non-flat circle just because its center ordinate equals the higher construction-point elevation. The concrete bug is the current guard:

    if yc <= max(y1, y2) + 1e-9:
        return None

That guard rejects the `Case4_Iter1_Simple` pair `(1,2)` terminal-beta circle even though Slide2 stores it. Replace it with logic that rejects only circles whose center is materially below the higher endpoint, not circles that merely touch that limiting value within tolerance. Also make the beta upper bound inclusive enough that the terminal limit can be represented safely when finite geometry allows it.

Do not let this milestone broaden into a general solver change. This is still candidate-generation-only work. Add unit tests in `tests/unit/test_search_auto_refine.py` for the pair `(35.938262, 29.750610)` to `(50.308688, 41.246950)` so the expected terminal-beta circle `(xc, yc, r) = (38.524939, 41.246950, 11.783749)` is constructed instead of dropped. Also add a flat-pair test that proves equal-elevation crest-crest terminal-beta circles are still rejected later by the candidate-validity rules, not accidentally promoted.

### Milestone 3: Reject Equal-Elevation Clipped Surfaces

Keep the current construction-point interpretation and lower-arc clipping in `src/slope_stab/search/auto_refine.py`, but add a post-clipping validity rule that rejects any clipped surface with `abs(y_left - y_right) <= tol`. The tolerance must be deterministic and tight enough to treat Slide2's "same elevation" cases as equal without destabilizing non-flat cases. Use the same tolerance value across the search path and the tests so the behavior is transparent.

This rule must be applied after clipping and before evaluation. It belongs in the auto-refine candidate-generation flow, not in the global prescribed-surface solver. Add unit tests covering the five known equal-elevation `ours-only` surfaces from `Case4_Iter1_Simple`, and add a regression expectation in the new comparison harness that Slide2 stores zero equal-elevation surfaces for the one-iteration cases.

### Milestone 4: Add Model-Floor Validation to Candidate Generation

Extend `AutoRefineSearchInput` in `src/slope_stab/models.py` with an optional `model_boundary_floor_y: float | None = None`. Parse it from JSON in `src/slope_stab/io/json_io.py` under `search.auto_refine_circular.model_boundary_floor_y`, validate that it is finite, and serialize it through `src/slope_stab/analysis.py` metadata so parity diagnostics can show whether the rule is active.

Use this new floor value inside `src/slope_stab/search/auto_refine.py` after clipping and before evaluation. For each candidate, inspect the lower arc on the closed interval `[x_left, x_right]`. If any point on that lower arc falls below `model_boundary_floor_y - tol`, reject the candidate. This must be a candidate-generation rule only. It must not alter slice generation, solver math, or prescribed-surface validity. In current verification evidence, the side boundaries already match `search_limits`, so this milestone should keep using `search_limits.x_min` and `search_limits.x_max` as the side limits and should not invent a separate side-boundary input unless new evidence proves it is needed.

Add unit tests for the two known long-span `Case4_Iter1_Simple` `ours-only` surfaces whose minima are about `19.440448` and `14.582590`. Also add parser coverage so `model_boundary_floor_y` is optional, round-trips cleanly, and is absent by default for existing search fixtures.

### Milestone 5: Turn the Comparison Harness into an Exact Regression Gate

Add a new regression test file `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py`. This test must compare the unique quantized surface sets for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple` against the corresponding Slide2 `.s01` files. The test should instantiate those iteration-1 projects with the new `model_boundary_floor_y` values derived from the Slide2 external-boundary tables:

- Case 2 iteration 1: `model_boundary_floor_y = 0.0`
- Case 4 iteration 1: `model_boundary_floor_y = 20.0`
- Case 4 iteration 1 simple: `model_boundary_floor_y = 20.0`

Acceptance is exact set equality after six-decimal quantization of `(xc, yc, r, x_left, y_left, x_right, y_right)`. In addition, `Case4_Iter1_Simple` should assert the per-pair stored-surface counts because that smaller case is the clearest canary for terminal-beta behavior and equal-elevation rejection.

Do not declare success if only the counts match. The exact surfaces must match too. The comparison harness should still emit the diagnostic JSON and plots so any remaining mismatch can be inspected quickly.

### Milestone 6: Preserve Existing Baselines and Hand Off to a Future Ladder-Parity Plan

Once the iteration-1 set-equality gate passes, rerun the existing parity-focused tests and the required repository gate. The goal here is to prove that tightening iteration-1 candidate generation did not regress the broader baseline:

- `python -m unittest tests.unit.test_search_auto_refine`
- `python -m unittest tests.regression.test_case3_auto_refine tests.regression.test_case4_auto_refine tests.regression.test_auto_refine_slide2_case2_case4_alignment`
- `python -m slope_stab.cli verify`
- `python -m slope_stab.cli test`

If the full gate stays green, stop. Do not continue into retained-path ladder parity, supplementary optimization redesign, or final-iteration tuning under this plan. Instead, update `docs/execplans/auto-refine-slide2-iteration-ladder-alignment.md` or create a follow-on ExecPlan that begins from a now-exact iteration-1 generator.

## Concrete Steps

Run all commands from:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Always set:

    $env:PYTHONPATH='src'

Use the comparison harness before and after each milestone:

    python scripts/diagnostics/compare_slide2_iteration1_candidate_generation.py --output docs/benchmarks/auto_refine_slide2_iteration1_candidate_generation_current.json

Expected pre-change summary excerpt:

    Case2_Search_Iter_1: shared=1407 slide2_only=155 ours_only=303
    Case4_Iter1: shared=4216 slide2_only=320 ours_only=1874
    Case4_Iter1_Simple: shared=33 slide2_only=5 ours_only=7

After Milestones 2 through 5 are complete, the expected summary excerpt becomes:

    Case2_Search_Iter_1: shared=<all> slide2_only=0 ours_only=0
    Case4_Iter1: shared=<all> slide2_only=0 ours_only=0
    Case4_Iter1_Simple: shared=38 slide2_only=0 ours_only=0

Run the focused tests after each milestone:

    python -m unittest tests.unit.test_search_auto_refine
    python -m unittest tests.regression.test_auto_refine_slide2_iteration1_candidate_generation

Run the existing parity coverage before declaring the plan complete:

    python -m unittest tests.regression.test_case3_auto_refine tests.regression.test_case4_auto_refine tests.regression.test_auto_refine_slide2_case2_case4_alignment

Run the required repository gate at the end:

    python -m slope_stab.cli verify
    python -m slope_stab.cli test

If Windows sandboxing blocks process-parallel gate startup, follow the project guidance in `AGENTS.md` and rerun the required gate outside the sandbox with the approved escalation flow.

## Validation and Acceptance

This plan is complete only when all of the following are true:

The new comparison harness reports exact iteration-1 surface-set parity for `Case2_Search_Iter_1`, `Case4_Iter1`, and `Case4_Iter1_Simple` after six-decimal quantization, with zero `Slide2-only` and zero `ours-only` surfaces.

The new regression `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py` passes.

`tests/unit/test_search_auto_refine.py` passes with new coverage for terminal-beta construction, equal-elevation rejection, floor-boundary rejection, and parser behavior for `model_boundary_floor_y`.

The existing parity-focused regressions still pass:

- `tests/regression/test_case3_auto_refine.py`
- `tests/regression/test_case4_auto_refine.py`
- `tests/regression/test_auto_refine_slide2_case2_case4_alignment.py`

The required repository verification gate passes:

- `python -m slope_stab.cli verify`
- `python -m slope_stab.cli test`

The plotting outputs in `tmp/plots/` show no red-versus-blue mismatch families for the simple comparison case because the surface sets are identical.

## Idempotence and Recovery

All new diagnostics and plots in this plan must be additive and safely repeatable. Re-running the comparison harness may overwrite JSON artifacts in `docs/benchmarks/` and images in `tmp/plots/`, but that is intentional and safe. The harness should always derive its results from checked-in verification assets plus the current working tree.

The new `model_boundary_floor_y` input must be optional and default to `None`. Existing analysis inputs that do not set it must keep their current behavior. This is the safe recovery path if a regression appears outside the iteration-1 parity fixtures: unset the floor value and confirm whether the regression disappears before changing unrelated solver logic.

If the exact parity gate still fails after Milestones 2 through 4, do not guess. Use the comparison harness JSON plus the plots to classify the remaining mismatch surfaces, record the result in `Surprises & Discoveries`, and update the `Decision Log` before changing scope.

## Artifacts and Notes

Current comparison evidence for `Case4_Iter1_Simple`:

    shared = 33
    slide2_only = 5
    ours_only = 7

Current explanation of the seven `ours-only` surfaces:

    equal_elevation = 5
    below_model_floor = 2
    unexplained = 0

Current per-pair counts in the simple case:

    pair (0,1): raw_betas=5 ours_valid=4 slide2_stored=4
    pair (0,2): raw_betas=5 ours_valid=4 slide2_stored=4
    pair (0,3): raw_betas=5 ours_valid=4 slide2_stored=4
    pair (0,4): raw_betas=5 ours_valid=4 slide2_stored=2
    pair (1,2): raw_betas=5 ours_valid=4 slide2_stored=5
    pair (1,3): raw_betas=5 ours_valid=4 slide2_stored=5
    pair (1,4): raw_betas=5 ours_valid=4 slide2_stored=4
    pair (2,3): raw_betas=5 ours_valid=4 slide2_stored=5
    pair (2,4): raw_betas=5 ours_valid=4 slide2_stored=5
    pair (3,4): raw_betas=5 ours_valid=4 slide2_stored=0

Representative terminal-beta circle that Slide2 keeps and we currently drop:

    pair (1,2)
    start = (35.938262, 29.750610)
    end   = (50.308688, 41.246950)
    expected terminal-beta circle = (xc=38.524939, yc=41.246950, r=11.783749)

Representative current `ours-only` long-span surfaces that should be removed by floor validation:

    (xc=42.134035, yc=69.517043, r=50.076596, x_left=19.201562, y_left=25.0, x_right=85.798438, y_right=45.0) min_arc_y ~= 19.440448
    (xc=46.402532, yc=55.303614, r=40.721024, x_left=19.201562, y_left=25.0, x_right=85.798438, y_right=45.0) min_arc_y ~= 14.582590

## Interfaces and Dependencies

`matplotlib>=3.8` is already available in `pyproject.toml` and may be used by the diagnostic plotting script. The parity implementation itself must not depend on plotting to function.

In `src/slope_stab/models.py`, extend `AutoRefineSearchInput` with:

    model_boundary_floor_y: float | None = None

In `src/slope_stab/io/json_io.py`, parse:

    search.auto_refine_circular.model_boundary_floor_y

and validate that it is finite if present.

In `src/slope_stab/search/common.py`, keep the public helper name:

    circle_from_endpoints_and_tangent(p_left, p_right, beta) -> PrescribedCircleInput | None

but change its limiting-circle behavior so a non-flat terminal-beta circle can be returned instead of being rejected at the boundary.

In `src/slope_stab/search/auto_refine.py`, keep the current construction-point clipping flow centered on:

    _generate_pre_polish_pair_candidates(...)
    _clip_construction_circle_to_ground_intercepts(...)

and insert the new equal-elevation and floor-boundary validity rules there, after clipping and before evaluation.

In `tests/regression/test_auto_refine_slide2_iteration1_candidate_generation.py`, define a single exact-comparison helper that quantizes each surface to six decimal places and compares unique sets. This helper must be used for all three one-iteration parity cases so the acceptance criterion stays uniform.

## Revision Note

Initial creation on 2026-04-04 to split iteration-1 candidate-generation parity from the broader ladder-alignment work. This plan exists because recent evidence reduced the immediate mismatch to four concrete rules: terminal-beta construction, construction-point clipping, equal-elevation rejection, and model-floor rejection.
