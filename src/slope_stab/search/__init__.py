"""Critical surface search algorithms."""

from slope_stab.search.auto_refine import (
    AutoRefineIterationDiagnostics,
    AutoRefineSearchResult,
    run_auto_refine_search,
)
from slope_stab.search.direct_global import (
    DirectGlobalSearchResult,
    DirectIterationDiagnostics,
    run_direct_global_search,
)
from slope_stab.search.cuckoo_global import (
    CuckooGlobalSearchResult,
    CuckooIterationDiagnostics,
    run_cuckoo_global_search,
)

__all__ = [
    "AutoRefineIterationDiagnostics",
    "AutoRefineSearchResult",
    "CuckooGlobalSearchResult",
    "CuckooIterationDiagnostics",
    "DirectGlobalSearchResult",
    "DirectIterationDiagnostics",
    "run_auto_refine_search",
    "run_cuckoo_global_search",
    "run_direct_global_search",
]
