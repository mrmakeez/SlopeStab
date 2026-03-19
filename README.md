# SlopeStab

Verification-first slope stability program supporting Bishop simplified and Spencer methods.

## Runtime Dependencies

- Python `>=3.11`
- `numpy`
- `scipy`
- `cma` (pycma)

The `cmaes_global_circular` path requires `scipy` and `cma`; fallback implementations are intentionally not provided.

## Quick Start

1. `python -m slope_stab.cli analyze --input tests/fixtures/case1.json`
2. `python -m slope_stab.cli verify` (built-in verification covers Case 1-4, DIRECT global benchmarks for Cases 2-4, Cuckoo global benchmarks for Cases 2-4, and CMAES global benchmarks for Cases 2-4)
3. `python -m unittest discover -s tests -p "test_*.py"`

## Documentation

- Auto-refine algorithm explainer (beginner-friendly, with step-by-step SVG diagrams and formulas): `docs/auto-refine-explainer.md`
- DIRECT global algorithm explainer (implementation-accurate): `docs/direct-global-explainer.md`
- Cuckoo global algorithm explainer (seeded stochastic global search): `docs/cuckoo-global-explainer.md`
- CMAES global algorithm explainer (hybrid DIRECT + CMA-ES + polish): `docs/cmaes-global-explainer.md`
- Spencer solver explainer (force and moment equilibrium with lambda coupling): `docs/spencer-explainer.md`

## Analysis Methods

- `analysis.method = bishop_simplified` for Bishop simplified LEM solving.
- `analysis.method = spencer` for Spencer LEM solving.
- Both methods are supported for prescribed surfaces and all circular search methods.

## Search Methods

- `search.method = auto_refine_circular` for deterministic Slide2-style narrowing search.
- `search.method = direct_global_circular` for deterministic DIRECT-style global search.
- `search.method = cuckoo_global_circular` for seeded stochastic Cuckoo global search with deterministic repeatability per seed.
- `search.method = cmaes_global_circular` for seeded hybrid DIRECT prescan + CMA-ES + Nelder-Mead polish.
- Input settings and output diagnostics for each method are documented in the explainer files above.

## Search Architecture

- Shared circular geometry and candidate validity rules: `src/slope_stab/search/common.py`
- Shared objective/caching/evaluation counters for global methods: `src/slope_stab/search/objective_evaluator.py`
- Shared DIRECT partition primitive used by DIRECT and CMAES prescan: `src/slope_stab/search/direct_partition.py`
- Shared deterministic post-polish config for global methods: `src/slope_stab/search/post_polish.py`

This keeps the method-specific files focused on their search strategy while preserving consistent scoring, tie-break, and invalid-candidate behavior.

## Performance and Repeatability Notes

- Deterministic paths (`auto_refine_circular`, `direct_global_circular`) remain deterministic.
- Seeded stochastic paths (`cuckoo_global_circular`, `cmaes_global_circular`) remain repeatable for fixed seeds.
- Non-gating performance snapshots can be captured with the fixture timing command documented in `PLANS.md` for regression tracking.

## Solver Validity Rules

- Any converged slip surface with final-iteration `m_alpha < 0.2` in any slice is treated as invalid.
- Base tension induced negative slice shear strength is clamped to zero.
