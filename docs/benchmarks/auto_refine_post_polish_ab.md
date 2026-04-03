# Auto-Refine Post-Polish A/B Decision Evidence

| Scenario | Total Seconds | Mean |dFOS| | Mean |x_right error| | Mean radius rel error |
|---|---:|---:|---:|---:|
| with_post_polish | 454.12 | 0.002461 | 0.216625 | 0.028921 |
| no_post_polish | 339.30 | 0.004736 | 0.412620 | 0.021163 |

Compared stage: `after_post_polish` (final auto-refine output).
Decision: keep post-polish enabled by default; no-post-polish currently degrades parity accuracy.
