from __future__ import annotations

import json
import math
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
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
    ParallelExecutionInput,
    PrescribedCircleInput,
    ProjectInput,
    SeismicLoadInput,
    SoilMaterialInput,
    SoilRegionAssignmentInput,
    SoilsInput,
    SearchInput,
    SearchLimitsInput,
    UniformSurchargeInput,
)
from slope_stab.search.auto_parallel_policy import allowed_parallel_modes


def _require_key(data: dict, key: str) -> object:
    if key not in data:
        raise InputValidationError(f"Missing required key: {key}")
    return data[key]


def _as_float(v: object, key: str) -> float:
    if isinstance(v, bool):
        raise InputValidationError(f"Key '{key}' must be numeric.")
    try:
        fv = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InputValidationError(f"Key '{key}' must be numeric.") from exc
    if not math.isfinite(fv):
        raise InputValidationError(f"Key '{key}' must be finite numeric.")
    return fv


def _as_int(v: object, key: str) -> int:
    if isinstance(v, bool):
        raise InputValidationError(f"Key '{key}' must be an integer.")
    try:
        iv = int(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InputValidationError(f"Key '{key}' must be an integer.") from exc
    try:
        fv = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InputValidationError(f"Key '{key}' must be an integer.") from exc
    if not math.isfinite(fv) or fv != iv:
        raise InputValidationError(f"Key '{key}' must be an integer.")
    return iv


def _as_bool(v: object, key: str) -> bool:
    if isinstance(v, bool):
        return v
    raise InputValidationError(f"Key '{key}' must be a boolean.")


def _parse_point_pair(value: object, key: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise InputValidationError(f"{key} must be a [x, y] pair.")
    return (_as_float(value[0], f"{key}[0]"), _as_float(value[1], f"{key}[1]"))


def _parse_polyline_points(value: object, key: str, min_points: int) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list):
        raise InputValidationError(f"{key} must be an array of [x, y] points.")
    if len(value) < min_points:
        raise InputValidationError(f"{key} must contain at least {min_points} points.")
    points = tuple(_parse_point_pair(point, f"{key}[{idx}]") for idx, point in enumerate(value))
    for idx, (x1, y1) in enumerate(points[:-1]):
        x2, y2 = points[idx + 1]
        if math.hypot(x2 - x1, y2 - y1) <= 0.0:
            raise InputValidationError(f"{key}[{idx}] and {key}[{idx + 1}] must not be identical points.")
    return points


def _parse_soils(soils_data: object) -> SoilsInput:
    key_prefix = "soils"
    if not isinstance(soils_data, dict):
        raise InputValidationError("'soils' must be an object.")

    materials_raw = _require_key(soils_data, "materials")
    if not isinstance(materials_raw, list) or len(materials_raw) == 0:
        raise InputValidationError("soils.materials must be a non-empty array.")

    materials: list[SoilMaterialInput] = []
    seen_ids: set[str] = set()
    for idx, entry in enumerate(materials_raw):
        prefix = f"{key_prefix}.materials[{idx}]"
        if not isinstance(entry, dict):
            raise InputValidationError(f"{prefix} must be an object.")
        material_id = str(_require_key(entry, "id")).strip()
        if not material_id:
            raise InputValidationError(f"{prefix}.id must be a non-empty string.")
        if material_id in seen_ids:
            raise InputValidationError(f"{prefix}.id '{material_id}' is duplicated.")
        seen_ids.add(material_id)
        materials.append(
            SoilMaterialInput(
                id=material_id,
                gamma=_as_float(_require_key(entry, "gamma"), f"{prefix}.gamma"),
                c=_as_float(_require_key(entry, "c"), f"{prefix}.c"),
                phi_deg=_as_float(_require_key(entry, "phi_deg"), f"{prefix}.phi_deg"),
            )
        )

    external_boundary = _parse_polyline_points(
        _require_key(soils_data, "external_boundary"),
        f"{key_prefix}.external_boundary",
        min_points=3,
    )

    boundaries_raw = soils_data.get("material_boundaries", [])
    if not isinstance(boundaries_raw, list):
        raise InputValidationError("soils.material_boundaries must be an array.")
    material_boundaries: list[tuple[tuple[float, float], ...]] = []
    for idx, entry in enumerate(boundaries_raw):
        material_boundaries.append(
            _parse_polyline_points(entry, f"{key_prefix}.material_boundaries[{idx}]", min_points=2)
        )

    assignments_raw = _require_key(soils_data, "region_assignments")
    if not isinstance(assignments_raw, list) or len(assignments_raw) == 0:
        raise InputValidationError("soils.region_assignments must be a non-empty array.")
    region_assignments: list[SoilRegionAssignmentInput] = []
    for idx, entry in enumerate(assignments_raw):
        prefix = f"{key_prefix}.region_assignments[{idx}]"
        if not isinstance(entry, dict):
            raise InputValidationError(f"{prefix} must be an object.")
        material_id = str(_require_key(entry, "material_id")).strip()
        if material_id not in seen_ids:
            raise InputValidationError(f"{prefix}.material_id '{material_id}' is not defined in soils.materials.")
        region_assignments.append(
            SoilRegionAssignmentInput(
                material_id=material_id,
                seed_x=_as_float(_require_key(entry, "seed_x"), f"{prefix}.seed_x"),
                seed_y=_as_float(_require_key(entry, "seed_y"), f"{prefix}.seed_y"),
            )
        )

    return SoilsInput(
        materials=tuple(materials),
        external_boundary=external_boundary,
        material_boundaries=tuple(material_boundaries),
        region_assignments=tuple(region_assignments),
    )


def _parse_uniform_surcharge(
    surcharge_data: object,
    geometry: GeometryInput,
) -> UniformSurchargeInput:
    key_prefix = "loads.uniform_surcharge"
    if surcharge_data is None:
        raise InputValidationError(f"'{key_prefix}' must be an object.")
    if not isinstance(surcharge_data, dict):
        raise InputValidationError(f"'{key_prefix}' must be an object.")

    magnitude_kpa = _as_float(_require_key(surcharge_data, "magnitude_kpa"), f"{key_prefix}.magnitude_kpa")
    placement = str(_require_key(surcharge_data, "placement")).strip().lower()
    if magnitude_kpa < 0.0:
        raise InputValidationError(f"{key_prefix}.magnitude_kpa must be greater than or equal to zero.")
    if placement not in {"crest_infinite", "crest_range"}:
        raise InputValidationError(f"{key_prefix}.placement must be one of: crest_infinite, crest_range.")

    crest_x = geometry.x_toe + geometry.l
    if placement == "crest_infinite":
        if surcharge_data.get("x_start") is not None or surcharge_data.get("x_end") is not None:
            raise InputValidationError(f"{key_prefix}.x_start/x_end are not allowed for placement='crest_infinite'.")
        return UniformSurchargeInput(
            magnitude_kpa=magnitude_kpa,
            placement=placement,
            x_start=None,
            x_end=None,
        )

    x_start = _as_float(_require_key(surcharge_data, "x_start"), f"{key_prefix}.x_start")
    x_end = _as_float(_require_key(surcharge_data, "x_end"), f"{key_prefix}.x_end")
    if x_end <= x_start:
        raise InputValidationError(f"{key_prefix}.x_end must exceed x_start.")
    if x_start < crest_x or x_end < crest_x:
        raise InputValidationError(
            f"{key_prefix} crest_range must lie on the crest region where x >= geometry.x_toe + geometry.l."
        )
    return UniformSurchargeInput(
        magnitude_kpa=magnitude_kpa,
        placement=placement,
        x_start=x_start,
        x_end=x_end,
    )


def _parse_seismic_load(seismic_data: object) -> SeismicLoadInput | None:
    key_prefix = "loads.seismic"
    if seismic_data is None:
        return None
    if not isinstance(seismic_data, dict):
        raise InputValidationError(f"'{key_prefix}' must be an object.")
    model = str(_require_key(seismic_data, "model")).strip().lower()
    if model == "none":
        return SeismicLoadInput(model=model, kh=0.0, kv=0.0)
    if model != "pseudo_static":
        raise InputValidationError(f"{key_prefix}.model must be one of: none, pseudo_static.")

    kh = _as_float(_require_key(seismic_data, "kh"), f"{key_prefix}.kh")
    if kh < 0.0 or kh > 1.0:
        raise InputValidationError(f"{key_prefix}.kh must be in [0, 1].")

    kv = _as_float(seismic_data.get("kv", 0.0), f"{key_prefix}.kv")
    if kv != 0.0:
        raise InputValidationError(f"{key_prefix}.kv must be exactly 0.0 in v1.")

    return SeismicLoadInput(model=model, kh=kh, kv=kv)


def _parse_water_surface_points(surface_data: object, key_prefix: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(surface_data, list):
        raise InputValidationError(f"{key_prefix}.surface must be an array of [x, y] points.")
    if len(surface_data) < 2:
        raise InputValidationError(f"{key_prefix}.surface must contain at least two points.")

    points: list[tuple[float, float]] = []
    last_x: float | None = None
    for idx, point in enumerate(surface_data):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise InputValidationError(f"{key_prefix}.surface[{idx}] must be a [x, y] pair.")
        x = _as_float(point[0], f"{key_prefix}.surface[{idx}][0]")
        y = _as_float(point[1], f"{key_prefix}.surface[{idx}][1]")
        if last_x is not None and x <= last_x:
            raise InputValidationError(f"{key_prefix}.surface x values must be strictly increasing.")
        points.append((x, y))
        last_x = x
    return tuple(points)


def _parse_groundwater_load(groundwater_data: object) -> GroundwaterInput | None:
    key_prefix = "loads.groundwater"
    if groundwater_data is None:
        return None
    if not isinstance(groundwater_data, dict):
        raise InputValidationError(f"'{key_prefix}' must be an object.")
    model = str(_require_key(groundwater_data, "model")).strip().lower()
    if model == "none":
        return GroundwaterInput(model=model)

    if model == "water_surfaces":
        surface = _parse_water_surface_points(groundwater_data.get("surface"), key_prefix)
        hu_data = _require_key(groundwater_data, "hu")
        if not isinstance(hu_data, dict):
            raise InputValidationError(f"{key_prefix}.hu must be an object.")

        hu_mode = str(_require_key(hu_data, "mode")).strip().lower()
        if hu_mode not in {"custom", "auto"}:
            raise InputValidationError(f"{key_prefix}.hu.mode must be one of: custom, auto.")

        hu_value: float | None = None
        if hu_mode == "custom":
            if "value" not in hu_data:
                raise InputValidationError(f"{key_prefix}.hu.value is required when hu.mode='custom'.")
            hu_value = _as_float(hu_data.get("value"), f"{key_prefix}.hu.value")
            if hu_value < 0.0 or hu_value > 1.0:
                raise InputValidationError(f"{key_prefix}.hu.value must be in [0, 1].")
        elif hu_data.get("value") is not None:
            raise InputValidationError(f"{key_prefix}.hu.value is not allowed when hu.mode='auto'.")

        gamma_w = _as_float(groundwater_data.get("gamma_w", 9.81), f"{key_prefix}.gamma_w")
        if gamma_w <= 0.0:
            raise InputValidationError(f"{key_prefix}.gamma_w must be greater than zero.")

        return GroundwaterInput(
            model=model,
            surface=surface,
            hu=GroundwaterHuInput(mode=hu_mode, value=hu_value),
            gamma_w=gamma_w,
            ru=None,
        )

    if model == "ru_coefficient":
        ru = _as_float(_require_key(groundwater_data, "ru"), f"{key_prefix}.ru")
        if ru < 0.0 or ru > 1.0:
            raise InputValidationError(f"{key_prefix}.ru must be in [0, 1].")
        return GroundwaterInput(model=model, ru=ru)

    raise InputValidationError(f"{key_prefix}.model must be one of: none, water_surfaces, ru_coefficient.")


def _parse_loads(loads_data: object, geometry: GeometryInput) -> LoadsInput | None:
    if loads_data is None:
        return None
    if not isinstance(loads_data, dict):
        raise InputValidationError("'loads' must be an object.")

    uniform_surcharge_data = loads_data.get("uniform_surcharge")
    seismic_data = loads_data.get("seismic")
    groundwater_data = loads_data.get("groundwater")

    uniform_surcharge: UniformSurchargeInput | None = None
    if uniform_surcharge_data is not None:
        uniform_surcharge = _parse_uniform_surcharge(uniform_surcharge_data, geometry)
    seismic = _parse_seismic_load(seismic_data)
    groundwater = _parse_groundwater_load(groundwater_data)

    return LoadsInput(
        uniform_surcharge=uniform_surcharge,
        seismic=seismic,
        groundwater=groundwater,
    )


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


def _parse_parallel_execution(parallel_data: object) -> ParallelExecutionInput:
    key_prefix = "search.parallel"
    if parallel_data is None:
        return ParallelExecutionInput(
            mode="auto",
            workers=0,
            min_batch_size=1,
            timeout_seconds=None,
        )
    if not isinstance(parallel_data, dict):
        raise InputValidationError(f"'{key_prefix}' must be an object.")
    if "enabled" in parallel_data:
        raise InputValidationError(
            f"{key_prefix}.enabled is no longer supported; use {key_prefix}.mode."
        )

    mode_raw = parallel_data.get("mode")
    if mode_raw is None:
        mode = "auto"
    else:
        mode = str(mode_raw).strip().lower()
        if mode not in allowed_parallel_modes():
            raise InputValidationError(
                f"{key_prefix}.mode must be one of: auto, serial, parallel."
            )

    workers = _as_int(parallel_data.get("workers", 0), f"{key_prefix}.workers")
    min_batch_size = _as_int(parallel_data.get("min_batch_size", 1), f"{key_prefix}.min_batch_size")
    timeout_raw = parallel_data.get("timeout_seconds")
    timeout_seconds: float | None
    if timeout_raw is None:
        timeout_seconds = None
    else:
        timeout_seconds = _as_float(timeout_raw, f"{key_prefix}.timeout_seconds")

    if workers < 0:
        raise InputValidationError(f"{key_prefix}.workers must be greater than or equal to zero.")
    if min_batch_size <= 0:
        raise InputValidationError(f"{key_prefix}.min_batch_size must be greater than zero.")
    if timeout_seconds is not None and timeout_seconds <= 0.0:
        raise InputValidationError(f"{key_prefix}.timeout_seconds must be greater than zero.")

    return ParallelExecutionInput(
        mode=mode,
        workers=workers,
        min_batch_size=min_batch_size,
        timeout_seconds=timeout_seconds,
    )


def _parse_search_common(
    auto_data: dict,
    geometry: GeometryInput,
    key_prefix: str,
) -> tuple[int, int, int, float, SearchLimitsInput, float | None]:
    limits = _parse_search_limits(auto_data.get("search_limits"), geometry, key_prefix)
    floor_raw = auto_data.get("model_boundary_floor_y")
    model_boundary_floor_y = (
        None
        if floor_raw is None
        else _as_float(floor_raw, f"{key_prefix}.model_boundary_floor_y")
    )

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
        model_boundary_floor_y,
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
    max_iterations = _as_int(cuckoo_data.get("max_iterations", 300), f"{key_prefix}.max_iterations")
    max_evaluations = _as_int(cuckoo_data.get("max_evaluations", 7000), f"{key_prefix}.max_evaluations")
    discovery_rate = _as_float(cuckoo_data.get("discovery_rate", 0.25), f"{key_prefix}.discovery_rate")
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
    seed = _as_int(cmaes_data.get("seed", 1), f"{key_prefix}.seed")
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
    if "material" in payload:
        raise InputValidationError("Top-level key 'material' is no longer supported; use required key 'soils'.")
    soils_data = _require_key(payload, "soils")
    ana_data = _require_key(payload, "analysis")
    surface_data = payload.get("prescribed_surface")
    search_data = payload.get("search")
    loads_data = payload.get("loads")

    if not isinstance(geom_data, dict):
        raise InputValidationError("'geometry' must be an object.")
    if not isinstance(ana_data, dict):
        raise InputValidationError("'analysis' must be an object.")

    geometry = GeometryInput(
        h=_as_float(_require_key(geom_data, "h"), "geometry.h"),
        l=_as_float(_require_key(geom_data, "l"), "geometry.l"),
        x_toe=_as_float(_require_key(geom_data, "x_toe"), "geometry.x_toe"),
        y_toe=_as_float(_require_key(geom_data, "y_toe"), "geometry.y_toe"),
    )
    soils = _parse_soils(soils_data)
    analysis = AnalysisInput(
        method=str(_require_key(ana_data, "method")).strip().lower(),
        n_slices=_as_int(_require_key(ana_data, "n_slices"), "analysis.n_slices"),
        tolerance=_as_float(_require_key(ana_data, "tolerance"), "analysis.tolerance"),
        max_iter=_as_int(_require_key(ana_data, "max_iter"), "analysis.max_iter"),
        f_init=_as_float(ana_data.get("f_init", 1.0), "analysis.f_init"),
    )
    if geometry.h <= 0 or geometry.l <= 0:
        raise InputValidationError("geometry.h and geometry.l must be greater than zero.")
    for material in soils.materials:
        if material.gamma <= 0:
            raise InputValidationError(f"soils.materials[{material.id}].gamma must be greater than zero.")
        if material.phi_deg < 0 or material.phi_deg >= 90:
            raise InputValidationError(f"soils.materials[{material.id}].phi_deg must be in [0, 90).")
    if analysis.method not in {"bishop_simplified", "spencer"}:
        raise InputValidationError("Only analysis.method='bishop_simplified' or 'spencer' is supported.")
    if analysis.n_slices <= 0 or analysis.max_iter <= 0:
        raise InputValidationError("n_slices and max_iter must be greater than zero.")
    if analysis.tolerance <= 0:
        raise InputValidationError("analysis.tolerance must be greater than zero.")
    if analysis.f_init <= 0:
        raise InputValidationError("analysis.f_init must be greater than zero.")
    loads = _parse_loads(loads_data, geometry)
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
        parallel = _parse_parallel_execution(search_data.get("parallel"))

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
                model_boundary_floor_y,
            ) = _parse_search_common(auto_data, geometry, "search.auto_refine_circular")

            auto = AutoRefineSearchInput(
                divisions_along_slope=divisions_along_slope,
                circles_per_division=circles_per_division,
                iterations=iterations,
                divisions_to_use_next_iteration_pct=divisions_to_use_next_iteration_pct,
                search_limits=limits,
                model_boundary_floor_y=model_boundary_floor_y,
            )
            search = SearchInput(method=method, auto_refine_circular=auto, parallel=parallel)
        elif method == "direct_global_circular":
            direct_data = _require_key(search_data, "direct_global_circular")
            if not isinstance(direct_data, dict):
                raise InputValidationError("'search.direct_global_circular' must be an object.")
            direct = _parse_direct_global_search(direct_data, geometry)
            search = SearchInput(method=method, direct_global_circular=direct, parallel=parallel)
        elif method == "cuckoo_global_circular":
            cuckoo_data = _require_key(search_data, "cuckoo_global_circular")
            if not isinstance(cuckoo_data, dict):
                raise InputValidationError("'search.cuckoo_global_circular' must be an object.")
            cuckoo = _parse_cuckoo_global_search(cuckoo_data, geometry)
            search = SearchInput(method=method, cuckoo_global_circular=cuckoo, parallel=parallel)
        elif method == "cmaes_global_circular":
            cmaes_data = _require_key(search_data, "cmaes_global_circular")
            if not isinstance(cmaes_data, dict):
                raise InputValidationError("'search.cmaes_global_circular' must be an object.")
            cmaes = _parse_cmaes_global_search(cmaes_data, geometry)
            search = SearchInput(method=method, cmaes_global_circular=cmaes, parallel=parallel)
        else:
            raise InputValidationError(
                "Only search.method='auto_refine_circular', 'direct_global_circular', or "
                "'cuckoo_global_circular', or 'cmaes_global_circular' is supported."
            )

    return ProjectInput(
        units=units,
        geometry=geometry,
        soils=soils,
        analysis=analysis,
        prescribed_surface=surface,
        search=search,
        loads=loads,
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
