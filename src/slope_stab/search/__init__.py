"""Search algorithms for critical circular slip surfaces."""

from slope_stab.search.auto_refine import (
    build_pair_indices,
    build_search_domain,
    build_surface_from_endpoints_and_radius,
    is_surface_below_ground,
    run_auto_refine_search,
)

__all__ = [
    "build_pair_indices",
    "build_search_domain",
    "build_surface_from_endpoints_and_radius",
    "is_surface_below_ground",
    "run_auto_refine_search",
]
