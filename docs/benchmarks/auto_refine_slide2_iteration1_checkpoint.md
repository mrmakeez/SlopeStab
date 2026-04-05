# Auto-Refine Slide2 Iteration-1 Checkpoint

This note records the current stopping point for the Slide2 auto-refine parity investigation.

The current implementation is intentionally conservative. We prefer to generate a few extra surfaces rather than risk missing surfaces that Slide2 can generate or evaluate.

## Current Candidate-Generation Position

Iteration-1 candidate generation now covers every Slide2-stored surface in the three benchmark scenarios captured by [auto_refine_slide2_iteration1_candidate_generation_current.json](./auto_refine_slide2_iteration1_candidate_generation_current.json):

- `Case2_Search_Iter_1`: `shared=1562`, `slide2_only=0`, `ours_only=140`
- `Case4_Iter1`: `shared=4536`, `slide2_only=0`, `ours_only=61`
- `Case4_Iter1_Simple`: `shared=38`, `slide2_only=0`, `ours_only=2`

That means the remaining gap is over-generation only. We are no longer missing any Slide2-stored iteration-1 surfaces in these benchmark cases.

## Defined-Surface Replay Findings

The saved `.s01` files are not a complete record of all theoretical iteration-1 surfaces. The new error harness in [auto_refine_slide2_iteration1_error_harness_current.json](./auto_refine_slide2_iteration1_error_harness_current.json) shows:

- `Case2_Search_Iter_1`: `1900` theoretical slots, `1562` stored
- `Case4_Iter1`: `6525` theoretical slots, `4536` stored
- `Case4_Iter1_Simple`: `50` theoretical slots, `38` stored

To understand the omitted circles better, the remaining `ours_only` circles were replayed into Slide2 as explicitly defined surfaces.

### Case4_Iter1_SimpleDBG

The two remaining simple-case extras split cleanly:

- one circle is explicitly rejected by Slide2 as `-114` in both Bishop and Spencer
- one circle is valid in both Bishop and Spencer

So omission from the normal auto-refine `.s01` is not equivalent to invalidity.

### Case4_Iter1DBG

The full-case replay added all `61` remaining `ours_only` circles back into the stored geometry set:

- original stored geometries: `4536`
- debug stored geometries: `4597`
- delta: `61`

Slide2 classified those `61` circles as:

- Bishop: `24 valid`, `13 x -114`, `15 x -108`, `7 x -106`, `2 x -107`
- Spencer: `11 valid`, `13 x -114`, `15 x -108`, `7 x -106`, `2 x -107`, `13 x -111`

This is the main reason we are stopping at a conservative checkpoint instead of chasing exact set equality right now:

- many remaining extras are clearly invalid in Slide2
- some remaining extras are still valid when defined directly
- therefore `.s01` omission alone is not a safe runtime pruning rule

## Current Policy

Until a stronger rule is justified, the repository should continue to favor:

- zero `slide2_only` coverage misses in the tracked iteration-1 cases
- mild over-generation over aggressive pruning
- diagnostics and replay harnesses as evidence, not as direct runtime filters

In particular, Spencer-style `-111` behavior should not be used as a pruning rule at this stage. Some of those circles are Bishop-valid and some are Slide2-valid when replayed directly.

## Visual Checkpoints

Committed snapshot plots:

- [Case4 Iter1 Simple Shared vs Mismatch](./plots/case4_iter1_simple_match_and_mismatch_overlay.png)
- [Case4 Iter1 Shared vs Mismatch](./plots/case4_iter1_match_and_mismatch_overlay.png)

These are documentation snapshots. The plotting script still regenerates scratch versions under `tmp/plots/` when rerun.
