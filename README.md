# SlopeStab

Verification-first Bishop simplified slope stability program.

## Quick Start

1. `python -m slope_stab.cli analyze --input tests/fixtures/case1.json`
2. `python -m slope_stab.cli verify` (built-in verification covers Case 1-4, DIRECT global benchmarks for Cases 2-4, Cuckoo global benchmarks for Cases 2-4, and CMAES global benchmarks for Cases 2-4)
3. `python -m unittest discover -s tests -p "test_*.py"`

## Documentation

- Auto-refine algorithm explainer (beginner-friendly, with step-by-step SVG diagrams and formulas): `docs/auto-refine-explainer.md`
- DIRECT global algorithm explainer (implementation-accurate): `docs/direct-global-explainer.md`
- Cuckoo global algorithm explainer (seeded stochastic global search): `docs/cuckoo-global-explainer.md`
- CMAES global algorithm explainer (hybrid DIRECT + CMA-ES + polish): `docs/cmaes-global-explainer.md`

## Search Methods

- `search.method = auto_refine_circular` for deterministic Slide2-style narrowing search.
- `search.method = direct_global_circular` for deterministic DIRECT-style global search.
- `search.method = cuckoo_global_circular` for seeded stochastic Cuckoo global search with deterministic repeatability per seed.
- `search.method = cmaes_global_circular` for seeded hybrid DIRECT prescan + CMA-ES + Nelder-Mead polish.
- Input settings and output diagnostics for each method are documented in the explainer files above.
