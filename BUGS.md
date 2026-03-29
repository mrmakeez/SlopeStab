# BUGS

This file tracks verified, reproducible bugs found in this workspace.

## BUG-001
- ID: `BUG-001`
- Severity: `High`
- Status: `Open`
- Summary: JSON numeric parsing accepts booleans as numeric values (`True -> 1`, `False -> 0.0`) in fields that should require numeric input.
- Evidence:
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:36) (`_as_float` delegates directly to `float(v)`).
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:43) (`_as_int` delegates to `int(v)` then compares `float(v)`).
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:536) (`analysis.n_slices` parsed via `_as_int`).
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:69) (`loads.uniform_surcharge.magnitude_kpa` parsed via `_as_float`).
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  python -c "import json,pathlib; from slope_stab.io.json_io import parse_project_input; d=json.loads(pathlib.Path('tests/fixtures/case3_auto_refine.json').read_text()); d['analysis']['n_slices']=True; print(parse_project_input(d).analysis.n_slices); d=json.loads(pathlib.Path('tests/fixtures/case3_auto_refine.json').read_text()); d['search']['auto_refine_circular']['iterations']=True; print(parse_project_input(d).search.auto_refine_circular.iterations)"
  python -c "import json,pathlib; from slope_stab.io.json_io import parse_project_input; d=json.loads(pathlib.Path('tests/fixtures/case3_auto_refine.json').read_text()); d['loads']={'uniform_surcharge':{'magnitude_kpa':False,'placement':'crest_infinite'}}; print(parse_project_input(d).loads.uniform_surcharge.magnitude_kpa)"
  ```
- Expected vs Actual:
  - Expected: boolean values in numeric fields raise `InputValidationError`.
  - Actual: values are accepted and coerced to numeric (`1`, `1`, `0.0`).
- Suggested Fix Direction:
  - Reject `bool` explicitly in `_as_int` and `_as_float` before conversion.
  - Add schema tests for boolean rejection on representative numeric fields.

## BUG-002
- ID: `BUG-002`
- Severity: `High`
- Status: `Open`
- Summary: Non-finite numeric values (for example `"nan"`) are accepted by `_as_float`, allowing invalid runtime numeric state.
- Evidence:
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:36) (`_as_float` accepts `float('nan')`).
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:537) (`analysis.tolerance` parsed through `_as_float`).
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:549) (`analysis.tolerance <= 0` does not reject `nan`).
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  python -c "import json,pathlib; from slope_stab.io.json_io import parse_project_input; d=json.loads(pathlib.Path('tests/fixtures/case1.json').read_text()); d['analysis']['tolerance']='nan'; print(parse_project_input(d).analysis.tolerance)"
  ```
- Expected vs Actual:
  - Expected: non-finite numeric input (`nan`, `inf`, `-inf`) is rejected with `InputValidationError`.
  - Actual: payload parses successfully with `analysis.tolerance = nan`.
- Suggested Fix Direction:
  - Require finite floats in `_as_float` (for example via `math.isfinite` check).
  - Add finite-number validation tests for key numeric fields (`analysis.tolerance`, geometry/material values, search config values).

## BUG-003
- ID: `BUG-003`
- Severity: `Medium`
- Status: `Open`
- Summary: Auto-mode process startup fallback in `run_analysis` does not cover failures raised during context entry (`__enter__`), producing inconsistent startup-failure behavior.
- Evidence:
  - [analysis.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/analysis.py:540) (`try` only wraps `ParallelSurfaceExecutor(...)` construction).
  - [analysis.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/analysis.py:560) (`with executor_cm as executor:` is outside the startup-fallback `except`).
  - [test_auto_parallel_policy.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/tests/unit/test_auto_parallel_policy.py:144) covers constructor-side startup failure fallback, but not `__enter__` startup failure.
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  @'
  import json
  import pathlib
  from unittest.mock import patch
  from slope_stab.io.json_io import parse_project_input
  from slope_stab.analysis import run_analysis

  payload = json.loads(pathlib.Path('tests/fixtures/case3_auto_refine.json').read_text())
  payload['search']['parallel'] = {'mode': 'auto', 'workers': 0, 'min_batch_size': 1}
  project = parse_project_input(payload)

  class BoomExecutor:
      def __init__(self, *args, **kwargs): pass
      def __enter__(self): raise PermissionError('enter denied')
      def __exit__(self, exc_type, exc, tb): return False

  with patch('slope_stab.analysis.effective_cpu_count', return_value=4), \
       patch('slope_stab.analysis.process_policy_allows_parallel', return_value=True), \
       patch('slope_stab.analysis.ParallelSurfaceExecutor', BoomExecutor):
      run_analysis(project)
  '@ | python -
  ```
- Expected vs Actual:
  - Expected: in `auto` mode, process startup failures consistently resolve to serial with `decision_reason=process_backend_startup_failed_serial`.
  - Actual: `PermissionError` from `__enter__` is propagated directly.
- Suggested Fix Direction:
  - Treat constructor and context-entry startup as one startup-failure boundary for `auto` mode.
  - Keep policy alignment: do not convert runtime worker failures (timeout, invalid payload, evaluation exceptions) into silent serial fallback.

## BUG-004
- ID: `BUG-004`
- Severity: `Medium`
- Status: `Open`
- Summary: CLI stdout write path can fail noisily when downstream pipe closes, instead of terminating cleanly.
- Evidence:
  - [cli.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/cli.py:33) (`_cmd_analyze` unguarded `print(text)`).
  - [cli.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/cli.py:83) (`_cmd_verify` unguarded `print(text)`).
  - [cli.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/cli.py:121) (`_cmd_test` unguarded `print(text)`).
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  python -c "import os,subprocess,sys; env=os.environ.copy(); env['PYTHONPATH']='src'; p=subprocess.Popen([sys.executable,'-m','slope_stab.cli','analyze','--input','tests/fixtures/case1.json','--compact'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env); p.stdout.close(); err=p.stderr.read(); rc=p.wait(); print(rc); print(err)"
  ```
  Observed in this Windows workspace: non-zero exit and stderr containing `Exception ignored while flushing sys.stdout: OSError: [Errno 22] Invalid argument`.
- Expected vs Actual:
  - Expected: graceful termination when stdout consumer closes early (no noisy traceback-style stderr noise).
  - Actual: noisy stderr on broken/closed stdout path (platform-specific symptom).
- Suggested Fix Direction:
  - Centralize safe stdout emission in CLI commands and handle closed-pipe conditions across platforms.
  - Cover both `BrokenPipeError` and flush/closed-stream `OSError` manifestations.

## BUG-005
- ID: `BUG-005`
- Severity: `High`
- Status: `Open`
- Summary: Search evaluation accounting excludes deterministic refinement/post-polish stages, so reported counters (`total_evaluations` and `generated_surfaces`) can significantly under-report actual solver calls.
- Evidence:
  - [direct_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/direct_global.py:57) uses `CachedObjectiveEvaluator` for the global stage but then calls refinement with raw `evaluate_surface`.
  - [direct_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/direct_global.py:177) and [direct_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/direct_global.py:200) return `evaluator.total_evaluations` without counting polish calls.
  - [cuckoo_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/cuckoo_global.py:119) and [cuckoo_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/cuckoo_global.py:236) show the same split between counted global phase and uncounted refinement.
  - [cmaes_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/cmaes_global.py:498), [cmaes_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/cmaes_global.py:460), and [cmaes_global.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/cmaes_global.py:547) show identical pattern.
  - [auto_refine.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/auto_refine.py:229), [auto_refine.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/auto_refine.py:269), and [auto_refine.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/search/auto_refine.py:304) show generated counters finalized before refinement calls.
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  @'
  import json
  import pathlib
  from dataclasses import replace
  from slope_stab.io.json_io import parse_project_input
  from slope_stab.models import AnalysisResult
  from slope_stab.search.surface_solver import build_profile
  from slope_stab.search.direct_global import run_direct_global_search
  from slope_stab.search.cuckoo_global import run_cuckoo_global_search
  from slope_stab.search.cmaes_global import run_cmaes_global_search
  from slope_stab.search.auto_refine import run_auto_refine_search

  root = pathlib.Path('tests/fixtures')
  def load(name): return parse_project_input(json.loads((root / name).read_text()))
  class Counter:
      def __init__(self): self.calls = 0
      def evaluator(self, _surface):
          self.calls += 1
          return AnalysisResult(fos=1.0, converged=True, iterations=1, residual=0.0, driving_moment=1.0, resisting_moment=1.0)

  p = load('case2_direct_global.json'); c = Counter()
  r = run_direct_global_search(build_profile(p.geometry), replace(p.search.direct_global_circular, max_evaluations=1), c.evaluator)
  print('DIRECT', r.total_evaluations, c.calls)

  p = load('case2_cuckoo_global.json'); c = Counter()
  r = run_cuckoo_global_search(build_profile(p.geometry), replace(p.search.cuckoo_global_circular, max_evaluations=10), c.evaluator)
  print('CUCKOO', r.total_evaluations, c.calls)

  p = load('case2_cmaes_global.json'); c = Counter()
  cfg = replace(p.search.cmaes_global_circular, max_evaluations=120, direct_prescan_evaluations=20, cmaes_population_size=4, cmaes_max_iterations=2, cmaes_restarts=0, polish_max_evaluations=10)
  r = run_cmaes_global_search(build_profile(p.geometry), cfg, c.evaluator)
  print('CMAES', r.total_evaluations, c.calls)

  p = load('case3_auto_refine.json'); c = Counter()
  r = run_auto_refine_search(build_profile(p.geometry), p.search.auto_refine_circular, c.evaluator)
  print('AUTO', r.generated_surfaces, c.calls)
  '@ | python -
  ```
  Observed in this workspace:
  - `DIRECT`: reported `1`, actual calls `5336`
  - `CUCKOO`: reported `10`, actual calls `5344`
  - `CMAES` (config above): reported `37`, actual calls `8450`
  - `AUTO`: reported `generated_surfaces=19000`, actual calls `22489`
- Expected vs Actual:
  - Expected: reported search accounting and budget semantics reflect all candidate evaluations performed by the method.
  - Actual: refinement/polish evaluations are excluded from counters and can exceed nominal budgets without being reflected in metadata.
- Suggested Fix Direction:
  - Route refinement/polish evaluations through shared budget/accounting primitives, or explicitly introduce separate counters for post-search refinement and publish both.
  - Keep deterministic ordered-merge behavior intact while enforcing clear budget semantics.

## BUG-006
- ID: `BUG-006`
- Severity: `High`
- Status: `Open`
- Summary: `material.phi_deg` is accepted without physical-range validation, allowing invalid/fragile inputs that fail late or produce absurd converged outputs.
- Evidence:
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:532) reads `phi_deg` via `_as_float` with no bounded validation.
  - [json_io.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/io/json_io.py:543) validates `gamma` only; no `phi_deg` range check is present.
  - [mohr_coulomb.py](/C:/Users/JamesMcKerrow/Stanley%20Gray%20Limited/SP%20-%20ENG/Technical/JAMES%20TECHNICAL/Codex/SlopeStab/src/slope_stab/materials/mohr_coulomb.py:19) uses `tan(radians(phi_deg))` directly.
- Repro:
  ```powershell
  $env:PYTHONPATH='src'
  python -c "import json,pathlib; from slope_stab.io.json_io import parse_project_input; from slope_stab.analysis import run_analysis; base=json.loads(pathlib.Path('tests/fixtures/case1.json').read_text()); \
for phi in (90.0,95.0,-5.0): \
 d=json.loads(json.dumps(base)); d['material']['phi_deg']=phi; \
 print('phi',phi,'->',end=' '); \
 try: p=parse_project_input(d); r=run_analysis(p); print('parsed, fos=',r.fos,'converged=',r.converged); \
 except Exception as e: print(type(e).__name__, str(e))"
  ```
  Observed in this workspace:
  - `phi=90.0` parsed and returned `fos=3.660045926839018e+16` with `converged=True`
  - `phi=95.0` parsed then failed with `ConvergenceError: Non-finite FOS encountered during Bishop iteration.`
  - `phi=-5.0` parsed then failed with `ConvergenceError: Bishop simplified did not converge in 100 iterations.`
- Expected vs Actual:
  - Expected: parser rejects non-finite or out-of-domain friction angles with explicit `InputValidationError`.
  - Actual: invalid values are accepted and only fail later (or yield numerically absurd but converged outputs).
- Suggested Fix Direction:
  - Add strict parser validation for finite `phi_deg` in a physically meaningful range (for example `0 <= phi_deg < 90`).
  - Add focused tests for boundary values (`-epsilon`, `90`, `nan`, `inf`) to keep failures early and deterministic.
