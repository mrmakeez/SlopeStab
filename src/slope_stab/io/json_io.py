from __future__ import annotations

import json
from pathlib import Path

from slope_stab.exceptions import InputValidationError
from slope_stab.models import (
    AnalysisInput,
    AnalysisResult,
    AutoRefineSearchInput,
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
    if analysis.method != "bishop_simplified":
        raise InputValidationError("Only analysis.method='bishop_simplified' is supported.")
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
        if method != "auto_refine_circular":
            raise InputValidationError("Only search.method='auto_refine_circular' is supported.")

        auto_data = _require_key(search_data, "auto_refine_circular")
        if not isinstance(auto_data, dict):
            raise InputValidationError("'search.auto_refine_circular' must be an object.")

        limits_data = auto_data.get("search_limits")
        if limits_data is None:
            limits = SearchLimitsInput(
                x_min=geometry.x_toe - geometry.h,
                x_max=geometry.x_toe + geometry.l + 2.0 * geometry.h,
            )
        else:
            if not isinstance(limits_data, dict):
                raise InputValidationError("'search.auto_refine_circular.search_limits' must be an object.")
            limits = SearchLimitsInput(
                x_min=_as_float(_require_key(limits_data, "x_min"), "search.auto_refine_circular.search_limits.x_min"),
                x_max=_as_float(_require_key(limits_data, "x_max"), "search.auto_refine_circular.search_limits.x_max"),
            )

        auto = AutoRefineSearchInput(
            divisions_along_slope=_as_int(
                _require_key(auto_data, "divisions_along_slope"),
                "search.auto_refine_circular.divisions_along_slope",
            ),
            circles_per_division=_as_int(
                _require_key(auto_data, "circles_per_division"),
                "search.auto_refine_circular.circles_per_division",
            ),
            iterations=_as_int(
                _require_key(auto_data, "iterations"),
                "search.auto_refine_circular.iterations",
            ),
            divisions_to_use_next_iteration_pct=_as_float(
                _require_key(auto_data, "divisions_to_use_next_iteration_pct"),
                "search.auto_refine_circular.divisions_to_use_next_iteration_pct",
            ),
            search_limits=limits,
        )

        if auto.divisions_along_slope <= 1:
            raise InputValidationError("search.auto_refine_circular.divisions_along_slope must be greater than 1.")
        if auto.circles_per_division <= 0:
            raise InputValidationError("search.auto_refine_circular.circles_per_division must be greater than zero.")
        if auto.iterations <= 0:
            raise InputValidationError("search.auto_refine_circular.iterations must be greater than zero.")
        if auto.divisions_to_use_next_iteration_pct <= 0 or auto.divisions_to_use_next_iteration_pct > 100:
            raise InputValidationError(
                "search.auto_refine_circular.divisions_to_use_next_iteration_pct must be in (0, 100]."
            )
        if auto.search_limits.x_max <= auto.search_limits.x_min:
            raise InputValidationError(
                "search.auto_refine_circular.search_limits.x_max must exceed x_min."
            )

        search = SearchInput(method=method, auto_refine_circular=auto)

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
