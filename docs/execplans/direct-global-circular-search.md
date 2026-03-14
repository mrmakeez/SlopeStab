# Implement Deterministic DIRECT Global Circular Search for Global-Minimum FOS

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository includes a repo-root `PLANS.md`. This ExecPlan must be maintained in accordance with `PLANS.md`.

## Purpose / Big Picture

Users can currently run prescribed Bishop analysis and Slide2-inspired auto-refine search, but the current auto-refine flow is still a narrowing heuristic and can miss a lower factor-of-safety (FOS) basin if that basin is not retained early. After this change, users will be able to run a deterministic global optimization search for circular slip surfaces that explores the full bounded domain and converges toward the global minimum FOS rather than only refining a locally retained window.

The user-visible outcome is a new search mode that reports a governing circular surface, convergence diagnostics, and deterministic repeatability. The new mode is additive and does not change Case 1 through Case 4 baseline behavior.

## Progress

- [x] (2026-03-14 19:20 +13:00) Reviewed current `auto_refine.py`, parser/dispatch boundaries, verification gates, and `PLANS.md` requirements.
- [x] (2026-03-14 19:20 +13:00) Ran baseline safety gate (`python -m slope_stab.cli verify` and `python -m unittest discover -s tests -p "test_*.py"`); all tests passed before any changes.
- [x] (2026-03-14 19:20 +13:00) Completed research pass and selected a deterministic DIRECT-style global optimizer design for circular surface search.
- [ ] Implement additive input contract for new global optimization mode.
- [ ] Implement deterministic DIRECT search core with objective caching and stable tie-break rules.
- [ ] Integrate search mode into analysis and metadata output.
- [ ] Add regression tests that prove global-minimum capture against bounded-domain oracle baselines.
- [ ] Run required verification gate and full tests after implementation.
- [ ] Update this ExecPlan sections (`Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective`) throughout implementation.

## Surprises & Discoveries

- Observation: The current `auto_refine_circular` approach can prune away regions early based on per-division average FOS, which is useful for parity but not a global-optimality guarantee.
  Evidence: In `src/slope_stab/search/auto_refine.py`, retained divisions are selected per iteration and next search limits are narrowed to retained boundaries.

- Observation: Slide2 documentation explicitly warns that lower FOS surfaces can exist if search settings are not broad enough.
  Evidence: Slide2 online help section "Finding the True Global Minimum in Surface Search" warns that reported surfaces depend on search limits and settings.

- Observation: DIRECT (DIviding RECTangles) is a deterministic global optimization method with established global-convergence results for continuous bounded objectives and no required user-supplied Lipschitz constant.
  Evidence: Standard references used by SciPy `optimize.direct` cite Jones et al. (1993) and Gablonsky and Kelley (2001).

## Decision Log

- Decision: Add a new method (`search.method = "direct_global_circular"`) instead of replacing `auto_refine_circular`.
  Rationale: `AGENTS.md` requires verification-first additive changes and preservation of existing parity and benchmark behavior.
  Date/Author: 2026-03-14 / Codex

- Decision: Use a deterministic DIRECT-style hyperrectangle partitioning algorithm over a normalized 3-parameter circular-surface space.
  Rationale: DIRECT is deterministic, globally convergent under standard continuity assumptions, and practical for expensive black-box objectives like Bishop FOS.
  Date/Author: 2026-03-14 / Codex

- Decision: Define convergence claims in two layers: asymptotic global convergence in the bounded continuous domain and explicit global-optimum checks against dense bounded-domain oracle fixtures.
  Rationale: This keeps mathematical claims honest while still giving strong, testable evidence that the implementation finds global minima in representative slope problems.
  Date/Author: 2026-03-14 / Codex

- Decision: Keep dependencies to Python standard library and existing project modules only.
  Rationale: Avoid dependency drift and preserve deterministic behavior across environments.
  Date/Author: 2026-03-14 / Codex

## Outcomes & Retrospective

Implementation has not started yet. This section will be updated at each major milestone with delivered behavior, residual gaps, and lessons learned.

## Context and Orientation

The repository currently supports two analysis modes: prescribed circular surface and `auto_refine_circular` search. Parsing happens in `src/slope_stab/io/json_io.py`, runtime dispatch happens in `src/slope_stab/analysis.py`, and current search logic is in `src/slope_stab/search/auto_refine.py`.

In this repository, "global minimum FOS" means the smallest valid Bishop simplified factor of safety over all admissible circular surfaces in a user-bounded horizontal search interval. A "valid" surface means the circle geometry is finite, endpoints are ordered left-to-right, and Bishop solver evaluation converges with finite terms.

DIRECT means DIviding RECTangles: an algorithm that repeatedly partitions a bounded parameter domain into smaller boxes, evaluates the objective at box centers, and keeps subdividing boxes that could still contain the global minimum. "Potentially optimal rectangle" means a box that is competitive under some objective-versus-size tradeoff and is therefore eligible for subdivision.

The existing `auto_refine_circular` code already has robust circle construction helpers and deterministic tie-break conventions. The new method should reuse these conventions where possible so that determinism and geometry consistency remain aligned.

## Plan of Work

Milestone 1 introduces additive data and parser interfaces for a new method without touching prescribed-surface behavior or existing `auto_refine_circular` behavior. Update `src/slope_stab/models.py` to support a second search configuration object and update `src/slope_stab/io/json_io.py` validation so exactly one of `search.auto_refine_circular` or `search.direct_global_circular` is required when `search.method` is set. Keep existing validation messages intact for current fixtures.

Milestone 2 builds `src/slope_stab/search/direct_global.py` with a deterministic objective adapter and search core. The objective adapter maps a normalized parameter vector `(u_left, u_span, u_beta)` in `[0,1]^3` to a circular surface, evaluates Bishop FOS through the supplied callback, and returns `+inf` for infeasible or non-converged surfaces. Use strict caching keyed by normalized coordinates so repeated evaluations are not re-solved. Keep stable tie-break ordering for equal FOS candidates using lexicographic surface keys.

Milestone 3 implements the DIRECT rectangle lifecycle. Define a rectangle model containing center coordinates, half-sizes per dimension, center objective value, and a stable rectangle id. Implement potentially-optimal selection and trisection along the largest dimensions. Each split must be deterministic in ordering, and children must be reproducible across runs on the same input.

Milestone 4 adds an optional deterministic local polish pass around the current incumbent after a configurable number of global iterations. Use a bounded pattern search with fixed direction order and fixed step-reduction schedule so no randomness is introduced. Local polish must never override a better global incumbent and must be reported as a separate diagnostic contribution.

Milestone 5 wires analysis dispatch. In `src/slope_stab/analysis.py`, route `search.method == "direct_global_circular"` to the new engine and serialize typed metadata including total evaluations, valid evaluations, infeasible evaluations, iteration diagnostics, incumbent history, and termination reason.

Milestone 6 adds verification coverage that specifically tests global-minimum behavior instead of only parity to Slide2. Add new fixtures in `tests/fixtures/` with bounded search domains designed to contain multiple local minima. For each fixture, generate a high-density deterministic brute-force oracle baseline (offline once, stored in fixture metadata) and assert the new method reaches the same minimum within tight tolerance. Keep Case 1 through Case 4 unchanged and still required in `cli verify`.

Milestone 7 updates documentation in `docs/` and `README.md` with method intent, limits, expected runtime tradeoffs, and deterministic guarantees. Include clear language on what is guaranteed (bounded-domain deterministic convergence) and what is approximation-controlled (finite budget termination).

## Concrete Steps

Run all commands from:

    C:\Users\JamesMcKerrow\Stanley Gray Limited\SP - ENG\Technical\JAMES TECHNICAL\Codex\SlopeStab

Baseline before implementation:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Implement Milestone 1 to Milestone 5, then run targeted tests:

    python -m unittest tests.unit.test_search_direct_global
    python -m unittest tests.regression.test_direct_global_oracle_case5
    python -m unittest tests.regression.test_direct_global_oracle_case6
    $env:PYTHONPATH='src'; python -m slope_stab.cli analyze --input tests/fixtures/case5_direct_global.json

Run full required gate at each merge-ready checkpoint:

    $env:PYTHONPATH='src'; python -m slope_stab.cli verify
    python -m unittest discover -s tests -p "test_*.py"

Expected success markers after implementation:

    verify output still reports Case 1 through Case 4 passed.
    new direct-global regression tests pass and report deterministic repeatability.
    repeated runs of case5/case6 return identical FOS and identical governing surface coordinates.

## Validation and Acceptance

Hard non-regression acceptance:

- Case 1 and Case 2 benchmark targets and tolerances are unchanged.
- Existing Case 3 and Case 4 parity tests remain passing.
- `python -m slope_stab.cli verify` passes.
- `python -m unittest discover -s tests -p "test_*.py"` passes.

Hard direct-global acceptance:

- New method runs via JSON input `search.method = "direct_global_circular"` and returns a valid prescribed winning surface in metadata.
- Determinism: two identical runs on the same fixture produce identical FOS and identical winning surface coordinates to 12 decimal places.
- Global-minimum oracle parity: for each new oracle fixture, absolute FOS error is within `1e-3` versus dense brute-force baseline and endpoint coordinate absolute error is within `0.10 m`.
- Convergence diagnostics include at least: `total_evaluations`, `valid_evaluations`, `infeasible_evaluations`, `best_fos_history`, `min_rectangle_half_size`, and `termination_reason`.

Behavioral acceptance:

- On a fixture with multiple local minima, the new method must match the known global-minimum basin while a constrained local-only search baseline does not.
- The method must continue exploring globally until stop criteria are met; no single-window narrowing shortcut is allowed.

## Idempotence and Recovery

All steps are additive and rerunnable. If parser changes break existing fixtures, revert only the parser/model edits in the current branch and rerun baseline verification before proceeding. If new regression fixtures are too slow, reduce brute-force oracle density in generation scripts, regenerate fixture expected values, and keep tolerance explicit in the fixture metadata.

Do not alter existing Case 1 through Case 4 expected values or tolerances. If a proposed optimization changes those outputs, treat that as a regression and fix the new code path rather than updating baseline references.

## Artifacts and Notes

Research notes captured for design provenance (implementation must remain self-contained and must not require reading external links):

- DIRECT foundational reference: Jones, Perttunen, and Stuckman, 1993, Journal of Optimization Theory and Applications, "Lipschitzian optimization without the Lipschitz constant."
- DIRECT-L reference for local biasing tradeoff: Gablonsky and Kelley, 2001, Journal of Global Optimization.
- SciPy DIRECT documentation (for algorithm summary and references): https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.direct.html
- Slide2 caution that search settings affect whether true global minimum is found: https://www.rocscience.com/help/slide2/documentation/slide-model/slip-surfaces/surface-options

Baseline verification evidence before implementation:

    python -m slope_stab.cli verify -> all_passed: true (Case 1-4 all passed)
    python -m unittest discover -s tests -p "test_*.py" -> Ran 14 tests, OK

## Interfaces and Dependencies

Add or update these interfaces:

In `src/slope_stab/models.py`, define:

    @dataclass(frozen=True)
    class DirectGlobalCircularInput:
        max_evaluations: int
        max_iterations: int
        min_improvement: float
        min_rectangle_half_size: float
        local_refine_every_iterations: int
        local_refine_max_steps: int
        search_limits: SearchLimitsInput

Update search model to support both methods without ambiguity:

    @dataclass(frozen=True)
    class SearchInput:
        method: str
        auto_refine_circular: AutoRefineSearchInput | None = None
        direct_global_circular: DirectGlobalCircularInput | None = None

In `src/slope_stab/search/direct_global.py`, define:

    @dataclass(frozen=True)
    class DirectIterationDiagnostics:
        iteration: int
        total_evaluations: int
        potentially_optimal_count: int
        incumbent_fos: float
        min_rectangle_half_size: float
        local_refine_improvement: float

    @dataclass(frozen=True)
    class DirectGlobalSearchResult:
        winning_surface: PrescribedCircleInput
        winning_result: AnalysisResult
        iteration_diagnostics: list[DirectIterationDiagnostics]
        total_evaluations: int
        valid_evaluations: int
        infeasible_evaluations: int
        termination_reason: str

    def run_direct_global_search(
        profile: UniformSlopeProfile,
        config: DirectGlobalCircularInput,
        evaluate_surface: SurfaceEvaluator,
    ) -> DirectGlobalSearchResult:
        ...

Implementation dependencies remain limited to Python standard library plus current repository modules. No third-party optimization package should be introduced.

Plan revision note: Created on 2026-03-14 to define the implementation path for a deterministic global-minimum-focused circular search algorithm, prompted by the request to move beyond Slide2-style auto-refine heuristics.
