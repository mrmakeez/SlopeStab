from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from slope_stab.execution.worker_policy import effective_cpu_count as _effective_cpu_count
from slope_stab.execution.worker_policy import resolve_requested_workers as _resolve_requested_workers
from slope_stab.models import SearchInput


EVIDENCE_VERSION: Final[str] = "auto-v3"

REASON_PRESCRIBED_ANALYSIS_SERIAL: Final[str] = "prescribed_analysis_serial"
REASON_FORCED_SERIAL_MODE: Final[str] = "forced_serial_mode"
REASON_FORCED_PARALLEL_MODE: Final[str] = "forced_parallel_mode"
REASON_WORKERS_LE_ONE_SERIAL: Final[str] = "workers_le_one_serial"
REASON_PROCESS_BACKEND_STARTUP_FAILED_SERIAL: Final[str] = "process_backend_startup_failed_serial"
REASON_THREAD_BACKEND_DEFAULT_SERIAL: Final[str] = "thread_backend_default_serial"
REASON_THREAD_BACKEND_WHITELIST_PARALLEL: Final[str] = "thread_backend_whitelist_parallel"
REASON_UNSUPPORTED_WORKLOAD_SERIAL: Final[str] = "unsupported_workload_serial"
REASON_UNSUPPORTED_BATCHING_SERIAL: Final[str] = "unsupported_batching_serial"
REASON_POLICY_THRESHOLD_PARALLEL: Final[str] = "policy_threshold_parallel"
REASON_POLICY_THRESHOLD_SERIAL: Final[str] = "policy_threshold_serial"

DEFAULT_BATCHING_CLASS: Final[str] = "default_batching"
RESTRICTED_BATCHING_CLASS: Final[str] = "restricted_batching"
UNSUPPORTED_WORKLOAD_CLASS: Final[str] = "unsupported"

_ALLOWED_MODES: Final[set[str]] = {"auto", "serial", "parallel"}
_DEFAULT_BATCHING_MAX: Final[int] = 8

# Conservative process-backend policy entries. Any missing tuple defaults serial.
_PROCESS_PARALLEL_WHITELIST: Final[set[tuple[str, str, str, str]]] = {
    ("auto_refine_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "spencer", "medium", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
}

# Non-uniform auto-refine policy. Keep this explicit so uniform small-workload
# auto-refine behavior remains unchanged.
_PROCESS_PARALLEL_WHITELIST_NON_UNIFORM: Final[set[tuple[str, str, str, str]]] = {
    ("auto_refine_circular", "bishop_simplified", "small", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "bishop_simplified", "medium", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "spencer", "small", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "spencer", "medium", DEFAULT_BATCHING_CLASS),
    ("auto_refine_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "bishop_simplified", "small", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "bishop_simplified", "medium", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "spencer", "small", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "spencer", "medium", DEFAULT_BATCHING_CLASS),
    ("direct_global_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "bishop_simplified", "small", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "bishop_simplified", "medium", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "spencer", "small", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "spencer", "medium", DEFAULT_BATCHING_CLASS),
    ("cuckoo_global_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "bishop_simplified", "small", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "bishop_simplified", "medium", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "bishop_simplified", "large", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "spencer", "small", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "spencer", "medium", DEFAULT_BATCHING_CLASS),
    ("cmaes_global_circular", "spencer", "large", DEFAULT_BATCHING_CLASS),
}

# v1 intentionally empty: thread backend remains serial-by-default in auto mode.
_THREAD_PARALLEL_WHITELIST: Final[set[tuple[str, str, str, str]]] = set()


@dataclass(frozen=True)
class ParallelResolution:
    requested_mode: str
    requested_workers: int
    resolved_mode: str
    resolved_workers: int
    decision_reason: str
    workload_class: str
    batching_class: str
    evidence_version: str
    backend: str

    @property
    def run_parallel(self) -> bool:
        return self.resolved_mode == "parallel" and self.resolved_workers > 1


def allowed_parallel_modes() -> set[str]:
    return set(_ALLOWED_MODES)


def effective_cpu_count() -> int:
    return _effective_cpu_count()


def resolve_requested_workers(configured_workers: int, available_workers: int) -> int:
    return _resolve_requested_workers(configured_workers, available_workers)


def classify_batching(min_batch_size: int) -> str:
    if min_batch_size <= _DEFAULT_BATCHING_MAX:
        return DEFAULT_BATCHING_CLASS
    return RESTRICTED_BATCHING_CLASS


def classify_workload(search: SearchInput, analysis_method: str) -> str:
    method = search.method
    if method == "auto_refine_circular" and search.auto_refine_circular is not None:
        cfg = search.auto_refine_circular
        surfaces_per_iter = cfg.circles_per_division * cfg.divisions_along_slope * (cfg.divisions_along_slope - 1) / 2.0
        proxy = cfg.iterations * surfaces_per_iter
        if proxy < 20_000:
            return "small"
        if proxy <= 80_000:
            return "medium"
        return "large"

    if method == "direct_global_circular" and search.direct_global_circular is not None:
        cfg = search.direct_global_circular
        proxy = max(float(cfg.max_evaluations), float(cfg.max_iterations) * 15.0)
        if proxy <= 1_500:
            return "small"
        if proxy <= 3_500:
            return "medium"
        return "large"

    if method == "cuckoo_global_circular" and search.cuckoo_global_circular is not None:
        cfg = search.cuckoo_global_circular
        proxy = min(float(cfg.max_evaluations), float(cfg.population_size * cfg.max_iterations))
        if proxy <= 2_000:
            return "small"
        if proxy <= 6_000:
            return "medium"
        return "large"

    if method == "cmaes_global_circular" and search.cmaes_global_circular is not None:
        cfg = search.cmaes_global_circular
        cma_budget_proxy = float(cfg.cmaes_population_size * cfg.cmaes_max_iterations * (cfg.cmaes_restarts + 1))
        prescan = float(cfg.direct_prescan_evaluations)
        polish = float(cfg.polish_max_evaluations)
        proxy = min(float(cfg.max_evaluations), prescan + cma_budget_proxy + polish)
        if proxy <= 2_500:
            return "small"
        if proxy <= 8_000:
            return "medium"
        return "large"

    # analysis_method currently unused for classification logic, but kept in
    # signature so policy features remain explicit and testable.
    _ = analysis_method
    return UNSUPPORTED_WORKLOAD_CLASS


def process_policy_allows_parallel(
    *,
    search_method: str,
    analysis_method: str,
    workload_class: str,
    batching_class: str,
    is_non_uniform: bool = False,
) -> bool:
    key = (search_method, analysis_method, workload_class, batching_class)
    if is_non_uniform and key in _PROCESS_PARALLEL_WHITELIST_NON_UNIFORM:
        return True
    return key in _PROCESS_PARALLEL_WHITELIST


def thread_policy_allows_parallel(
    *,
    search_method: str,
    analysis_method: str,
    workload_class: str,
    batching_class: str,
) -> bool:
    return (search_method, analysis_method, workload_class, batching_class) in _THREAD_PARALLEL_WHITELIST
