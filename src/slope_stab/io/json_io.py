from __future__ import annotations

import json
from pathlib import Path

from slope_stab.exceptions import InputValidationError
from slope_stab.models import (
    AnalysisInput,
    AnalysisResult,
    AutoRefineInput,
    GeometryInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
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


def _parse_prescribed_surface(surface_data: dict | None) -> PrescribedCircleInput | None:
    if surface_data is None:
        return None
    if not isinstance(surface_data, dict):
        raise InputValidationError("'prescribed_surface' must be an object when provided.")

    return PrescribedCircleInput(
        xc=_as_float(_require_key(surface_data, "xc"), "prescribed_surface.xc"),
        yc=_as_float(_require_key(surface_data, "yc"), "prescribed_surface.yc"),
        r=_as_float(_require_key(surface_data, "r"), "prescribed_surface.r"),
        x_left=_as_float(_require_key(surface_data, "x_left"), "prescribed_surface.x_left"),
        y_left=_as_float(_require_key(surface_data, "y_left"), "prescribed_surface.y_left"),
        x_right=_as_float(_require_key(surface_data, "x_right"), "prescribed_surface.x_right"),
        y_right=_as_float(_require_key(surface_data, "y_right"), "prescribed_surface.y_right"),
    )


def _parse_auto_refine(data: dict | None) -> AutoRefineInput:
    if data is None:
        return AutoRefineInput()
    if not isinstance(data, dict):
        raise InputValidationError("'auto_refine' must be an object when provided.")

    return AutoRefineInput(
        divisions=_as_int(data.get("divisions", 20), "auto_refine.divisions"),
        circles_per_pair=_as_int(data.get("circles_per_pair", 10), "auto_refine.circles_per_pair"),
        iterations=_as_int(data.get("iterations", 10), "auto_refine.iterations"),
        retain_ratio=_as_float(data.get("retain_ratio", 0.5), "auto_refine.retain_ratio"),
        toe_extension_h=_as_float(data.get("toe_extension_h", 1.0), "auto_refine.toe_extension_h"),
        crest_extension_h=_as_float(data.get("crest_extension_h", 2.0), "auto_refine.crest_extension_h"),
        min_span_h=_as_float(data.get("min_span_h", 0.10), "auto_refine.min_span_h"),
        radius_max_h=_as_float(data.get("radius_max_h", 10.0), "auto_refine.radius_max_h"),
        seed=_as_int(data.get("seed", 42), "auto_refine.seed"),
    )


def parse_project_input(payload: dict) -> ProjectInput:
    units = str(_require_key(payload, "units")).strip().lower()
    if units not in {"metric", "metric_units"}:
        raise InputValidationError("Only metric units are supported in MVP.")

    geom_data = _require_key(payload, "geometry")
    mat_data = _require_key(payload, "material")
    ana_data = _require_key(payload, "analysis")
    surface_data = payload.get("prescribed_surface")
    auto_refine_data = payload.get("auto_refine")

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
        mode=str(ana_data.get("mode", "prescribed")).strip().lower(),
    )
    surface = _parse_prescribed_surface(surface_data)
    auto_refine = _parse_auto_refine(auto_refine_data) if analysis.mode == "auto_refine" else None

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
    if analysis.mode not in {"prescribed", "auto_refine"}:
        raise InputValidationError("analysis.mode must be either 'prescribed' or 'auto_refine'.")

    if analysis.mode == "prescribed":
        if surface is None:
            raise InputValidationError("'prescribed_surface' is required when analysis.mode='prescribed'.")
        if surface.r <= 0:
            raise InputValidationError("prescribed_surface.r must be greater than zero.")
        if surface.x_right <= surface.x_left:
            raise InputValidationError("prescribed_surface.x_right must exceed x_left.")

    if analysis.mode == "auto_refine" and auto_refine is not None:
        if auto_refine.divisions < 2:
            raise InputValidationError("auto_refine.divisions must be at least 2.")
        if auto_refine.circles_per_pair <= 0 or auto_refine.iterations <= 0:
            raise InputValidationError("auto_refine.circles_per_pair and iterations must be > 0.")
        if not (0.0 < auto_refine.retain_ratio <= 1.0):
            raise InputValidationError("auto_refine.retain_ratio must be in (0, 1].")
        if auto_refine.toe_extension_h <= 0 or auto_refine.crest_extension_h <= 0:
            raise InputValidationError("auto_refine toe/crest extensions must be > 0.")
        if auto_refine.min_span_h <= 0 or auto_refine.radius_max_h <= 0:
            raise InputValidationError("auto_refine min_span_h and radius_max_h must be > 0.")

    return ProjectInput(
        units=units,
        geometry=geometry,
        material=material,
        analysis=analysis,
        prescribed_surface=surface,
        auto_refine=auto_refine,
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
