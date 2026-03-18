from __future__ import annotations

from slope_stab.models import AutoRefineSearchInput, SearchLimitsInput


def default_post_polish_refine_config(search_limits: SearchLimitsInput) -> AutoRefineSearchInput:
    return AutoRefineSearchInput(
        divisions_along_slope=2,
        circles_per_division=15,
        iterations=1,
        divisions_to_use_next_iteration_pct=50.0,
        search_limits=search_limits,
    )
