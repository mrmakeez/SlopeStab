from __future__ import annotations

import json
from pathlib import Path

from slope_stab.exceptions import InputValidationError
from slope_stab.models import (
    AnalysisInput,
    AnalysisResult,
    AutoRefineSearchInput,
    CmaesGlobalSearchInput,
    CuckooGlobalSearchInput,
    DirectGlobalSearchInput,
    GeometryInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
    SearchInput,
    SearchLimitsInput,
)


def _require_key(data: dict, key: str) -> object:
    if key not in data:
        raise InputValidationError(f"Missing required key: {key}")
    return data[key]


def _as_float(v: object, key: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"Key '{key}' must be numeric.") from exc


def _as_int(v: object, key: str) -> int:
    try:
        iv = int(v)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"Key '{key}' must be an integer.") from exc
    if float(v) != iv:
        raise InputValidationError(f"Key '{key}' must be an integer.")
    return iv


def _as_bool(v: object, key: str) -> bool:
    if isinstance(v, bool):
        return v
    raise InputValidationError(f"Key '{key}' must be a boolean.")


def _parse_search_limits(
    limits_data: object,
    geometry: GeometryInput,
    key_prefix: str,
) -> SearchLimitsInput:
    if limits_data is None:
        return SearchLimitsInput(
            x_min=geometry.x_toe - geometry.h,
            x_max=geometry.x_toe + geometry.l + 2.0 * geometry.h,
        )

    if not isinstance(limits_data, dict):
        raise InputValidationError(f"'{key_prefix}.search_limits' must be an object.")

    return SearchLimitsInput(
        x_min=_as_float(_require_key(limits_data, "x_min"), f"{key_prefix}.search_limits.x_min"),
        x_max=_as_float(_require_key(limits_data, "x_max"), f"{key_prefix}.search_limits.x_max"),
    )


def _parse_search_common(
    auto_data: dict,
    geometry: GeometryInput,
    key_prefix: str,
) -> tuple[int, int, int, float, SearchLimitsInput]:
    limits = _parse_search_limits(auto_data.get("search_limits"), geometry, key_prefix)

    divisions_along_slope = _as_int(_require_key(auto_data, "divisions_along_slope"), f"{key_prefix}.divisions_along_slope")
    circles_per_division = _as_int(_require_key(auto_data, "circles_per_division"), f"{key_prefix}.circles_per_division")
    iterations = _as_int(_require_key(auto_data, "iterations"), f"{key_prefix}.iterations")
    divisions_to_use_next_iteration_pct = _as_float(
        _require_key(auto_data, "divisions_to_use_next_iteration_pct"),
        f"{key_prefix}.divisions_to_use_next_iteration_pct",
    )

    if divisions_along_slope <= 1:
        raise InputValidationError(f"{key_prefix}.divisions_along_slope must be greater than 1.")
    if circles_per_division <= 0:
        raise InputValidationError(f"{key_prefix}.circles_per_division must be greater than zero.")
    if iterations <= 0:
        raise InputValidationError(f"{key_prefix}.iterations must be greater than zero.")
    if divisions_to_use_next_iteration_pct <= 0 or divisions_to_use_next_iteration_pct > 100:
        raise InputValidationError(
            f"{key_prefix}.divisions_to_use_next_iteration_pct must be in (0, 100]."
        )
    if limits.x_max <= limits.x_min:
        raise InputValidationError(
            f"{key_prefix}.search_limits.x_max must exceed x_min."
        )

    return (
        divisions_along_slope,
        circles_per_division,
        iterations,
        divisions_to_use_next_iteration_pct,
        limits,
    )


def _parse_direct_global_search(
    direct_data: dict,
    geometry: GeometryInput,
) -> DirectGlobalSearchInput:
    key_prefix = "search.direct_global_circular"
    limits = _parse_search_limits(direct_data.get("search_limits"), geometry, key_prefix)

    max_iterations = _as_int(_require_key(direct_data, "max_iterations"), f"{key_prefix}.max_iterations")
    max_evaluations = _as_int(_require_key(direct_data, "max_evaluations"), f"{key_prefix}.max_evaluations")
    min_improvement = _as_float(_require_key(direct_data, "min_improvement"), f"{key_prefix}.min_improvement")
    stall_iterations = _as_int(_require_key(direct_data, "stall_iterations"), f"{key_prefix}.stall_iterations")
    min_rectangle_half_size = _as_float(
        _require_key(direct_data, "min_rectangle_half_size"),
        f"{key_prefix}.min_rectangle_half_size",
    )

    if max_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.max_iterations must be greater than zero.")
    if max_evaluations <= 0:
        raise InputValidationError(f"{key_prefix}.max_evaluations must be greater than zero.")
    if min_improvement < 0.0:
        raise InputValidationError(f"{key_prefix}.min_improvement must be greater than or equal to zero.")
    if stall_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.stall_iterations must be greater than zero.")
    if min_rectangle_half_size <= 0.0:
        raise InputValidationError(f"{key_prefix}.min_rectangle_half_size must be greater than zero.")
    if limits.x_max <= limits.x_min:
        raise InputValidationError(
            f"{key_prefix}.search_limits.x_max must exceed x_min."
        )

    return DirectGlobalSearchInput(
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
        min_improvement=min_improvement,
        stall_iterations=stall_iterations,
        min_rectangle_half_size=min_rectangle_half_size,
        search_limits=limits,
    )


def _parse_cuckoo_global_search(
    cuckoo_data: dict,
    geometry: GeometryInput,
) -> CuckooGlobalSearchInput:
    key_prefix = "search.cuckoo_global_circular"
    limits = _parse_search_limits(cuckoo_data.get("search_limits"), geometry, key_prefix)

    population_size = _as_int(cuckoo_data.get("population_size", 40), f"{key_prefix}.population_size")
    max_iterations = _as_int(cuckoo_data.get("max_iterations", 200), f"{key_prefix}.max_iterations")
    max_evaluations = _as_int(cuckoo_data.get("max_evaluations", 4000), f"{key_prefix}.max_evaluations")
    discovery_rate = _as_float(cuckoo_data.get("discovery_rate", 0.20), f"{key_prefix}.discovery_rate")
    levy_beta = _as_float(cuckoo_data.get("levy_beta", 1.5), f"{key_prefix}.levy_beta")
    alpha_max = _as_float(cuckoo_data.get("alpha_max", 0.5), f"{key_prefix}.alpha_max")
    alpha_min = _as_float(cuckoo_data.get("alpha_min", 0.05), f"{key_prefix}.alpha_min")
    min_improvement = _as_float(cuckoo_data.get("min_improvement", 1e-4), f"{key_prefix}.min_improvement")
    stall_iterations = _as_int(cuckoo_data.get("stall_iterations", 25), f"{key_prefix}.stall_iterations")
    seed = _as_int(cuckoo_data.get("seed", 0), f"{key_prefix}.seed")
    post_polish = _as_bool(cuckoo_data.get("post_polish", True), f"{key_prefix}.post_polish")

    if population_size <= 1:
        raise InputValidationError(f"{key_prefix}.population_size must be greater than 1.")
    if max_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.max_iterations must be greater than zero.")
    if max_evaluations <= 0:
        raise InputValidationError(f"{key_prefix}.max_evaluations must be greater than zero.")
    if discovery_rate <= 0.0 or discovery_rate >= 1.0:
        raise InputValidationError(f"{key_prefix}.discovery_rate must be in (0, 1).")
    if levy_beta <= 1.0 or levy_beta > 2.0:
        raise InputValidationError(f"{key_prefix}.levy_beta must be in (1, 2].")
    if alpha_max <= 0.0:
        raise InputValidationError(f"{key_prefix}.alpha_max must be greater than zero.")
    if alpha_min <= 0.0:
        raise InputValidationError(f"{key_prefix}.alpha_min must be greater than zero.")
    if alpha_max <= alpha_min:
        raise InputValidationError(f"{key_prefix}.alpha_max must exceed alpha_min.")
    if min_improvement < 0.0:
        raise InputValidationError(f"{key_prefix}.min_improvement must be greater than or equal to zero.")
    if stall_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.stall_iterations must be greater than zero.")
    if limits.x_max <= limits.x_min:
        raise InputValidationError(
            f"{key_prefix}.search_limits.x_max must exceed x_min."
        )

    return CuckooGlobalSearchInput(
        population_size=population_size,
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
        discovery_rate=discovery_rate,
        levy_beta=levy_beta,
        alpha_max=alpha_max,
        alpha_min=alpha_min,
        min_improvement=min_improvement,
        stall_iterations=stall_iterations,
        seed=seed,
        post_polish=post_polish,
        search_limits=limits,
    )


def _parse_cmaes_global_search(
    cmaes_data: dict,
    geometry: GeometryInput,
) -> CmaesGlobalSearchInput:
    key_prefix = "search.cmaes_global_circular"
    limits = _parse_search_limits(cmaes_data.get("search_limits"), geometry, key_prefix)

    max_evaluations = _as_int(cmaes_data.get("max_evaluations", 5000), f"{key_prefix}.max_evaluations")
    direct_prescan_evaluations = _as_int(
        cmaes_data.get("direct_prescan_evaluations", 300), f"{key_prefix}.direct_prescan_evaluations"
    )
    cmaes_population_size = _as_int(
        cmaes_data.get("cmaes_population_size", 8), f"{key_prefix}.cmaes_population_size"
    )
    cmaes_max_iterations = _as_int(
        cmaes_data.get("cmaes_max_iterations", 200), f"{key_prefix}.cmaes_max_iterations"
    )
    cmaes_restarts = _as_int(cmaes_data.get("cmaes_restarts", 2), f"{key_prefix}.cmaes_restarts")
    cmaes_sigma0 = _as_float(cmaes_data.get("cmaes_sigma0", 0.15), f"{key_prefix}.cmaes_sigma0")
    polish_max_evaluations = _as_int(
        cmaes_data.get("polish_max_evaluations", 80), f"{key_prefix}.polish_max_evaluations"
    )
    min_improvement = _as_float(cmaes_data.get("min_improvement", 1e-4), f"{key_prefix}.min_improvement")
    stall_iterations = _as_int(cmaes_data.get("stall_iterations", 25), f"{key_prefix}.stall_iterations")
    seed = _as_int(cmaes_data.get("seed", 0), f"{key_prefix}.seed")
    post_polish = _as_bool(cmaes_data.get("post_polish", True), f"{key_prefix}.post_polish")
    invalid_penalty = _as_float(cmaes_data.get("invalid_penalty", 1e6), f"{key_prefix}.invalid_penalty")
    nonconverged_penalty = _as_float(
        cmaes_data.get("nonconverged_penalty", 1e5), f"{key_prefix}.nonconverged_penalty"
    )

    if max_evaluations <= 0:
        raise InputValidationError(f"{key_prefix}.max_evaluations must be greater than zero.")
    if direct_prescan_evaluations <= 0:
        raise InputValidationError(f"{key_prefix}.direct_prescan_evaluations must be greater than zero.")
    if direct_prescan_evaluations >= max_evaluations:
        raise InputValidationError(f"{key_prefix}.direct_prescan_evaluations must be less than max_evaluations.")
    if cmaes_population_size <= 1:
        raise InputValidationError(f"{key_prefix}.cmaes_population_size must be greater than 1.")
    if cmaes_max_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.cmaes_max_iterations must be greater than zero.")
    if cmaes_restarts < 0:
        raise InputValidationError(f"{key_prefix}.cmaes_restarts must be greater than or equal to zero.")
    if cmaes_sigma0 <= 0.0:
        raise InputValidationError(f"{key_prefix}.cmaes_sigma0 must be greater than zero.")
    if polish_max_evaluations <= 0:
        raise InputValidationError(f"{key_prefix}.polish_max_evaluations must be greater than zero.")
    if min_improvement < 0.0:
        raise InputValidationError(f"{key_prefix}.min_improvement must be greater than or equal to zero.")
    if stall_iterations <= 0:
        raise InputValidationError(f"{key_prefix}.stall_iterations must be greater than zero.")
    if invalid_penalty <= 0.0:
        raise InputValidationError(f"{key_prefix}.invalid_penalty must be greater than zero.")
    if nonconverged_penalty <= 0.0:
        raise InputValidationError(f"{key_prefix}.nonconverged_penalty must be greater than zero.")
    if invalid_penalty <= nonconverged_penalty:
        raise InputValidationError(f"{key_prefix}.invalid_penalty must exceed nonconverged_penalty.")
    if limits.x_max <= limits.x_min:
        raise InputValidationError(
            f"{key_prefix}.search_limits.x_max must exceed x_min."
        )

    return CmaesGlobalSearchInput(
        max_evaluations=max_evaluations,
        direct_prescan_evaluations=direct_prescan_evaluations,
        cmaes_population_size=cmaes_population_size,
        cmaes_max_iterations=cmaes_max_iterations,
        cmaes_restarts=cmaes_restarts,
        cmaes_sigma0=cmaes_sigma0,
        polish_max_evaluations=polish_max_evaluations,
        min_improvement=min_improvement,
        stall_iterations=stall_iterations,
        seed=seed,
        post_polish=post_polish,
        invalid_penalty=invalid_penalty,
        nonconverged_penalty=nonconverged_penalty,
        search_limits=limits,
    )


def parse_project_input(payload: dict) -> ProjectInput:
    units = str(_require_key(payload, "units")).strip().lower()
    if units not in {"metric", "metric_units"}:
        raise InputValidationError("Only metric units are supported in MVP.")

    geom_data = _require_key(payload, "geometry")
    mat_data = _require_key(payload, "material")
    ana_data = _require_key(payload, "analysis")
    surface_data = payload.get("prescribed_surface")
    search_data = payload.get("search")

    if not isinstance(geom_data, dict) or not isinstance(mat_data, dict):
        raise InputValidationError("'geometry' and 'material' must be objects.")
    if not isinstance(ana_data, dict):
        raise InputValidationError("'analysis' must be an object.")

    geometry = GeometryInput(
        h=_as_float(_require_key(geom_data, "h"), "geometry.h"),
        l=_as_float(_require_key(geom_data, "l"), "geometry.l"),
        x_toe=_as_float(_require_key(geom_data, "x_toe"), "geometry.x_toe"),
        y_toe=_as_float(_require_key(geom_data, "y_toe"), "geometry.y_toe"),
    )
    material = MaterialInput(
        gamma=_as_float(_require_key(mat_data, "gamma"), "material.gamma"),
        c=_as_float(_require_key(mat_data, "c"), "material.c"),
        phi_deg=_as_float(_require_key(mat_data, "phi_deg"), "material.phi_deg"),
    )
    analysis = AnalysisInput(
        method=str(_require_key(ana_data, "method")).strip().lower(),
        n_slices=_as_int(_require_key(ana_data, "n_slices"), "analysis.n_slices"),
        tolerance=_as_float(_require_key(ana_data, "tolerance"), "analysis.tolerance"),
        max_iter=_as_int(_require_key(ana_data, "max_iter"), "analysis.max_iter"),
        f_init=_as_float(ana_data.get("f_init", 1.0), "analysis.f_init"),
    )
    if geometry.h <= 0 or geometry.l <= 0:
        raise InputValidationError("geometry.h and geometry.l must be greater than zero.")
    if material.gamma <= 0:
        raise InputValidationError("material.gamma must be greater than zero.")
    if analysis.method not in {"bishop_simplified", "spencer"}:
        raise InputValidationError("Only analysis.method='bishop_simplified' or 'spencer' is supported.")
    if analysis.n_slices <= 0 or analysis.max_iter <= 0:
        raise InputValidationError("n_slices and max_iter must be greater than zero.")
    if analysis.tolerance <= 0:
        raise InputValidationError("analysis.tolerance must be greater than zero.")
    if analysis.f_init <= 0:
        raise InputValidationError("analysis.f_init must be greater than zero.")
    has_surface = surface_data is not None
    has_search = search_data is not None
    if has_surface == has_search:
        raise InputValidationError("Exactly one of 'prescribed_surface' or 'search' must be provided.")

    surface: PrescribedCircleInput | None = None
    search: SearchInput | None = None

    if has_surface:
        if not isinstance(surface_data, dict):
            raise InputValidationError("'prescribed_surface' must be an object.")

        surface = PrescribedCircleInput(
            xc=_as_float(_require_key(surface_data, "xc"), "prescribed_surface.xc"),
            yc=_as_float(_require_key(surface_data, "yc"), "prescribed_surface.yc"),
            r=_as_float(_require_key(surface_data, "r"), "prescribed_surface.r"),
            x_left=_as_float(_require_key(surface_data, "x_left"), "prescribed_surface.x_left"),
            y_left=_as_float(_require_key(surface_data, "y_left"), "prescribed_surface.y_left"),
            x_right=_as_float(_require_key(surface_data, "x_right"), "prescribed_surface.x_right"),
            y_right=_as_float(_require_key(surface_data, "y_right"), "prescribed_surface.y_right"),
        )

        if surface.r <= 0:
            raise InputValidationError("prescribed_surface.r must be greater than zero.")
        if surface.x_right <= surface.x_left:
            raise InputValidationError("prescribed_surface.x_right must exceed x_left.")
    else:
        if not isinstance(search_data, dict):
            raise InputValidationError("'search' must be an object.")

        method = str(_require_key(search_data, "method")).strip().lower()
        if method == "auto_refine_circular":
            auto_data = _require_key(search_data, "auto_refine_circular")
            if not isinstance(auto_data, dict):
                raise InputValidationError("'search.auto_refine_circular' must be an object.")

            (
                divisions_along_slope,
                circles_per_division,
                iterations,
                divisions_to_use_next_iteration_pct,
                limits,
            ) = _parse_search_common(auto_data, geometry, "search.auto_refine_circular")

            auto = AutoRefineSearchInput(
                divisions_along_slope=divisions_along_slope,
                circles_per_division=circles_per_division,
                iterations=iterations,
                divisions_to_use_next_iteration_pct=divisions_to_use_next_iteration_pct,
                search_limits=limits,
            )
            search = SearchInput(method=method, auto_refine_circular=auto)
        elif method == "direct_global_circular":
            direct_data = _require_key(search_data, "direct_global_circular")
            if not isinstance(direct_data, dict):
                raise InputValidationError("'search.direct_global_circular' must be an object.")
            direct = _parse_direct_global_search(direct_data, geometry)
            search = SearchInput(method=method, direct_global_circular=direct)
        elif method == "cuckoo_global_circular":
            cuckoo_data = _require_key(search_data, "cuckoo_global_circular")
            if not isinstance(cuckoo_data, dict):
                raise InputValidationError("'search.cuckoo_global_circular' must be an object.")
            cuckoo = _parse_cuckoo_global_search(cuckoo_data, geometry)
            search = SearchInput(method=method, cuckoo_global_circular=cuckoo)
        elif method == "cmaes_global_circular":
            cmaes_data = _require_key(search_data, "cmaes_global_circular")
            if not isinstance(cmaes_data, dict):
                raise InputValidationError("'search.cmaes_global_circular' must be an object.")
            cmaes = _parse_cmaes_global_search(cmaes_data, geometry)
            search = SearchInput(method=method, cmaes_global_circular=cmaes)
        else:
            raise InputValidationError(
                "Only search.method='auto_refine_circular', 'direct_global_circular', or "
                "'cuckoo_global_circular', or 'cmaes_global_circular' is supported."
            )

    return ProjectInput(
        units=units,
        geometry=geometry,
        material=material,
        analysis=analysis,
        prescribed_surface=surface,
        search=search,
    )


def load_project_input(path: str | Path) -> ProjectInput:
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InputValidationError("Root JSON payload must be an object.")
    return parse_project_input(payload)


def dump_result_json(result: AnalysisResult, path: str | Path | None = None, pretty: bool = True) -> str:
    indent = 2 if pretty else None
    text = json.dumps(result.to_dict(), indent=indent, sort_keys=False)
    if path is not None:
        Path(path).write_text(text + "\n", encoding="utf-8")
    return text
