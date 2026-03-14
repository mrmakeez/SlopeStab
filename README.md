# SlopeStab

Verification-first Bishop simplified slope stability program.

## Quick Start

1. `python -m slope_stab.cli analyze --input tests/fixtures/case1.json`
2. `python -m slope_stab.cli verify` (built-in verification covers Case 1-4, including auto-refine parity for Case 3/4)
3. `python -m unittest discover -s tests -p "test_*.py"`

## Documentation

- Auto-refine algorithm explainer (beginner-friendly, with step-by-step SVG diagrams and formulas): `docs/auto-refine-explainer.md`
