from __future__ import annotations

import os


def effective_cpu_count() -> int:
    try:
        if hasattr(os, "sched_getaffinity"):
            affinity_count = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
            if affinity_count > 0:
                return affinity_count
    except Exception:
        pass
    return max(1, int(os.cpu_count() or 1))


def resolve_requested_workers(configured_workers: int, available_workers: int) -> int:
    if configured_workers == 0:
        return min(4, available_workers)
    return min(max(1, configured_workers), available_workers)
