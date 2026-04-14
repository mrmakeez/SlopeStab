from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import TypeAlias

from slope_stab.materials.uniform_soils import build_uniform_soils
from slope_stab.models import (
    AnalysisInput,
    AutoRefineSearchInput,
    CmaesGlobalSearchInput,
    CuckooGlobalSearchInput,
    DirectGlobalSearchInput,
    GeometryInput,
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
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


def _uniform_soils(*, gamma: float, c: float, phi_deg: float):
    return build_uniform_soils(gamma=gamma, cohesion=c, phi_deg=phi_deg)


def _case11_soils() -> SoilsInput:
    return SoilsInput(
        materials=(
            SoilMaterialInput(id="soil_1", gamma=19.5, c=0.0, phi_deg=38.0),
            SoilMaterialInput(id="soil_2", gamma=19.5, c=5.3, phi_deg=23.0),
            SoilMaterialInput(id="soil_3", gamma=19.5, c=7.2, phi_deg=20.0),
        ),
        external_boundary=(
            (20.0, 20.0),
            (70.0, 20.0),
            (70.0, 24.0),
            (70.0, 31.0),
            (70.0, 35.0),
            (50.0, 35.0),
            (30.0, 25.0),
            (20.0, 25.0),
        ),
        material_boundaries=(
            ((40.0, 27.0), (52.0, 24.0), (70.0, 24.0)),
            ((30.0, 25.0), (40.0, 27.0), (50.0, 29.0), (54.0, 31.0), (70.0, 31.0)),
        ),
        region_assignments=(
            SoilRegionAssignmentInput(material_id="soil_1", seed_x=66.0, seed_y=33.0),
            SoilRegionAssignmentInput(material_id="soil_2", seed_x=66.0, seed_y=27.0),
            SoilRegionAssignmentInput(material_id="soil_3", seed_x=66.0, seed_y=22.0),
        ),
    )


def _case12_soils() -> SoilsInput:
    return SoilsInput(
        materials=(
            SoilMaterialInput(id="top_layer", gamma=18.82, c=29.4, phi_deg=12.0),
            SoilMaterialInput(id="middle_layer", gamma=18.82, c=9.8, phi_deg=5.0),
            SoilMaterialInput(id="lower_layer", gamma=18.82, c=294.0, phi_deg=40.0),
        ),
        external_boundary=(
            (0.0, 3.0),
            (96.0, 3.0),
            (96.0, 35.0),
            (72.0, 35.0),
            (48.0, 35.0),
            (24.0, 19.0),
            (18.0, 15.0),
            (0.0, 15.0),
        ),
        material_boundaries=(
            ((24.0, 19.0), (72.0, 35.0)),
            ((0.0, 3.0), (96.0, 35.0)),
        ),
        region_assignments=(
            SoilRegionAssignmentInput(material_id="top_layer", seed_x=70.0, seed_y=34.8),
            SoilRegionAssignmentInput(material_id="middle_layer", seed_x=32.0, seed_y=21.0),
            SoilRegionAssignmentInput(material_id="lower_layer", seed_x=32.0, seed_y=10.0),
        ),
    )


@dataclass(frozen=True)
class PrescribedVerificationCase:
    case_type: str
    name: str
    project: ProjectInput
    expected_fos: float
    fos_tolerance: float
    expected_driving_moment: float | None = None
    expected_resisting_moment: float | None = None
    moment_rel_tolerance: float | None = None
    analysis_method: str = "bishop_simplified"


@dataclass(frozen=True)
class AutoRefineVerificationCase:
    case_type: str
    name: str
    project: ProjectInput
    expected_fos: float
    fos_tolerance: float
    expected_radius: float
    radius_rel_tolerance: float
    expected_center: tuple[float, float]
    expected_left: tuple[float, float]
    expected_right: tuple[float, float]
    endpoint_abs_tolerance: float
    analysis_method: str = "bishop_simplified"
    radius_hard_check: bool = True


@dataclass(frozen=True)
class GlobalSearchBenchmarkVerificationCase:
    case_type: str
    search_method: str
    name: str
    project: ProjectInput
    benchmark_fos: float
    margin: float
    analysis_method: str = "bishop_simplified"


VerificationCase: TypeAlias = (
    PrescribedVerificationCase
    | AutoRefineVerificationCase
    | GlobalSearchBenchmarkVerificationCase
)


_CASE11_CASE12_SLIDE2_MANIFEST_PATH = (
    Path(__file__).resolve().parent / "data" / "case11_case12_slide2_manifest.json"
)
_NON_UNIFORM_SEARCH_MARGIN = 0.01
_NON_UNIFORM_SEARCH_LABELS = {
    "auto_refine_circular": "Auto-Refine",
    "direct_global_circular": "Direct Global",
    "cuckoo_global_circular": "Cuckoo Global",
    "cmaes_global_circular": "CMAES Global",
}


def _load_case11_case12_slide2_manifest() -> dict[str, object]:
    return json.loads(_CASE11_CASE12_SLIDE2_MANIFEST_PATH.read_text(encoding="utf-8"))


_CASE11_CASE12_SLIDE2_MANIFEST = _load_case11_case12_slide2_manifest()


def _slide2_search_fos(scenario_key: str, analysis_method: str) -> float:
    if analysis_method not in {"bishop_simplified", "spencer"}:
        raise KeyError(f"Unsupported analysis method for Slide2 manifest lookup: {analysis_method}")
    scenario = _CASE11_CASE12_SLIDE2_MANIFEST["scenarios"][scenario_key]
    method_entry = scenario["methods"][analysis_method]
    return float(method_entry["s01"]["fos"])


def _case11_water_seismic_surcharge_loads() -> LoadsInput:
    return LoadsInput(
        seismic=SeismicLoadInput(model="pseudo_static", kh=0.2, kv=0.0),
        uniform_surcharge=UniformSurchargeInput(
            magnitude_kpa=10.0,
            placement="crest_range",
            x_start=50.0,
            x_end=70.0,
        ),
        groundwater=GroundwaterInput(
            model="water_surfaces",
            surface=((20.0, 25.0), (30.0, 25.0), (50.0, 29.0), (70.0, 33.3746)),
            hu=GroundwaterHuInput(mode="custom", value=1.0),
            gamma_w=9.81,
        ),
    )


def _case12_water_surcharge_loads() -> LoadsInput:
    return LoadsInput(
        uniform_surcharge=UniformSurchargeInput(
            magnitude_kpa=100.0,
            placement="crest_range",
            x_start=48.0,
            x_end=55.0,
        ),
        groundwater=GroundwaterInput(
            model="water_surfaces",
            surface=((0.0, 19.0), (24.0, 19.0), (56.976, 32.2524), (96.0, 32.2524)),
            hu=GroundwaterHuInput(mode="auto", value=None),
            gamma_w=9.81,
        ),
    )


def _non_uniform_scenario_definition(
    scenario_key: str,
) -> tuple[str, GeometryInput, SoilsInput, LoadsInput | None, SearchLimitsInput]:
    if scenario_key == "Case11":
        return (
            "Case 11 (Non-Uniform)",
            GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            _case11_soils(),
            None,
            SearchLimitsInput(x_min=20.0, x_max=70.0),
        )
    if scenario_key == "Case11_Water_Seismic_Surcharge":
        return (
            "Case 11 (Water Seismic Surcharge Non-Uniform)",
            GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            _case11_soils(),
            _case11_water_seismic_surcharge_loads(),
            SearchLimitsInput(x_min=20.0, x_max=70.0),
        )
    if scenario_key == "Case12":
        return (
            "Case 12 (Non-Uniform)",
            GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            _case12_soils(),
            None,
            SearchLimitsInput(x_min=15.0, x_max=65.0),
        )
    if scenario_key == "Case12_Water_Surcharge":
        return (
            "Case 12 (Water Surcharge Non-Uniform)",
            GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            _case12_soils(),
            _case12_water_surcharge_loads(),
            SearchLimitsInput(x_min=15.0, x_max=65.0),
        )
    raise KeyError(f"Unsupported non-uniform scenario key: {scenario_key}")


def _build_non_uniform_search_input(search_method: str, limits: SearchLimitsInput) -> SearchInput:
    if search_method == "auto_refine_circular":
        return SearchInput(
            method=search_method,
            auto_refine_circular=AutoRefineSearchInput(
                divisions_along_slope=20,
                circles_per_division=10,
                iterations=10,
                divisions_to_use_next_iteration_pct=50.0,
                search_limits=limits,
            ),
        )
    if search_method == "direct_global_circular":
        return SearchInput(
            method=search_method,
            direct_global_circular=DirectGlobalSearchInput(
                max_iterations=90,
                max_evaluations=1200,
                min_improvement=0.0001,
                stall_iterations=12,
                min_rectangle_half_size=0.001,
                search_limits=limits,
            ),
        )
    if search_method == "cuckoo_global_circular":
        return SearchInput(
            method=search_method,
            cuckoo_global_circular=CuckooGlobalSearchInput(
                population_size=40,
                max_iterations=300,
                max_evaluations=7000,
                discovery_rate=0.25,
                levy_beta=1.5,
                alpha_max=0.5,
                alpha_min=0.05,
                min_improvement=0.0001,
                stall_iterations=25,
                seed=0,
                post_polish=True,
                search_limits=limits,
            ),
        )
    if search_method == "cmaes_global_circular":
        return SearchInput(
            method=search_method,
            cmaes_global_circular=CmaesGlobalSearchInput(
                max_evaluations=4500,
                direct_prescan_evaluations=600,
                cmaes_population_size=8,
                cmaes_max_iterations=180,
                cmaes_restarts=2,
                cmaes_sigma0=0.15,
                polish_max_evaluations=80,
                min_improvement=0.0001,
                stall_iterations=25,
                seed=1,
                post_polish=True,
                invalid_penalty=1_000_000.0,
                nonconverged_penalty=100_000.0,
                search_limits=limits,
            ),
        )
    raise KeyError(f"Unsupported non-uniform search method: {search_method}")


def _build_non_uniform_search_project(scenario_key: str, analysis_method: str, search_method: str) -> ProjectInput:
    _, geometry, soils, loads, limits = _non_uniform_scenario_definition(scenario_key)
    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=soils,
        analysis=AnalysisInput(
            method=analysis_method,
            n_slices=50,
            tolerance=0.001,
            max_iter=75,
            f_init=1.0,
        ),
        prescribed_surface=None,
        search=_build_non_uniform_search_input(search_method, limits),
        loads=loads,
    )


def _non_uniform_search_case_name(scenario_key: str, analysis_method: str, search_method: str) -> str:
    scenario_label, _, _, _, _ = _non_uniform_scenario_definition(scenario_key)
    search_label = _NON_UNIFORM_SEARCH_LABELS[search_method]
    if analysis_method == "spencer":
        return scenario_label.replace("(", "(Spencer ", 1).replace(")", f" {search_label} Search Benchmark)", 1)
    return scenario_label.replace(")", f" {search_label} Search Benchmark)", 1)


def _build_non_uniform_search_verification_cases() -> tuple[VerificationCase, ...]:
    scenario_keys = (
        "Case11",
        "Case11_Water_Seismic_Surcharge",
        "Case12",
        "Case12_Water_Surcharge",
    )
    search_methods = (
        "auto_refine_circular",
        "direct_global_circular",
        "cuckoo_global_circular",
        "cmaes_global_circular",
    )
    analysis_methods = ("bishop_simplified", "spencer")
    cases: list[VerificationCase] = []
    for scenario_key in scenario_keys:
        for analysis_method in analysis_methods:
            for search_method in search_methods:
                cases.append(
                    GlobalSearchBenchmarkVerificationCase(
                        case_type="non_uniform_search_benchmark",
                        search_method=search_method,
                        name=_non_uniform_search_case_name(scenario_key, analysis_method, search_method),
                        project=_build_non_uniform_search_project(
                            scenario_key=scenario_key,
                            analysis_method=analysis_method,
                            search_method=search_method,
                        ),
                        benchmark_fos=_slide2_search_fos(scenario_key, analysis_method),
                        margin=_NON_UNIFORM_SEARCH_MARGIN,
                        analysis_method=analysis_method,
                    )
                )
    return tuple(cases)


_NON_UNIFORM_DEFAULT_SEARCH_CASE_NAMES = (
    "Case 11 (Non-Uniform Auto-Refine Search Benchmark)",
    "Case 11 (Water Seismic Surcharge Non-Uniform Cuckoo Global Search Benchmark)",
    "Case 12 (Non-Uniform Direct Global Search Benchmark)",
    "Case 12 (Water Surcharge Non-Uniform CMAES Global Search Benchmark)",
    "Case 11 (Spencer Non-Uniform CMAES Global Search Benchmark)",
    "Case 11 (Spencer Water Seismic Surcharge Non-Uniform Direct Global Search Benchmark)",
    "Case 12 (Spencer Non-Uniform Cuckoo Global Search Benchmark)",
    "Case 12 (Spencer Water Surcharge Non-Uniform Auto-Refine Search Benchmark)",
)


def _build_non_uniform_default_search_verification_cases(
    full_cases: tuple[VerificationCase, ...],
) -> tuple[VerificationCase, ...]:
    selected_by_name = {case.name: case for case in full_cases}
    return tuple(selected_by_name[name] for name in _NON_UNIFORM_DEFAULT_SEARCH_CASE_NAMES)


VERIFICATION_CASES: tuple[VerificationCase, ...] = (
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 1",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=29.07,
                yc=55.495,
                r=30.4956368485163,
                x_left=30.02888427029,
                y_left=25.014442135145,
                x_right=51.6518254752929,
                y_right=35.0,
            ),
        ),
        expected_fos=0.986763,
        fos_tolerance=1e-4,
        expected_driving_moment=11867.3,
        expected_resisting_moment=11710.2,
        moment_rel_tolerance=1e-3,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 2",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=13.689,
                yc=25.558,
                r=15.989,
                x_left=10.0005216402222,
                y_left=10.0002608201111,
                x_right=27.4990237870903,
                y_right=17.5,
            ),
        ),
        expected_fos=2.11283,
        fos_tolerance=5e-4,
        expected_driving_moment=5715.12,
        expected_resisting_moment=12075.1,
        moment_rel_tolerance=1e-3,
    ),
    AutoRefineVerificationCase(
        case_type="auto_refine_parity",
        name="Case 3",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="auto_refine_circular",
                auto_refine_circular=AutoRefineSearchInput(
                    divisions_along_slope=20,
                    circles_per_division=10,
                    iterations=10,
                    divisions_to_use_next_iteration_pct=50.0,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        expected_fos=0.986442,
        fos_tolerance=0.001,
        expected_radius=26.793,
        radius_rel_tolerance=0.10,
        expected_center=(30.259, 51.792),
        expected_left=(30.0, 25.0),
        expected_right=(51.137, 35.0),
        endpoint_abs_tolerance=0.20,
    ),
    AutoRefineVerificationCase(
        case_type="auto_refine_parity",
        name="Case 4",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="auto_refine_circular",
                auto_refine_circular=AutoRefineSearchInput(
                    divisions_along_slope=30,
                    circles_per_division=15,
                    iterations=15,
                    divisions_to_use_next_iteration_pct=50.0,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        expected_fos=1.234670,
        fos_tolerance=0.001,
        expected_radius=43.234,
        radius_rel_tolerance=0.10,
        expected_center=(21.024, 67.292),
        expected_left=(30.0, 25.0),
        expected_right=(58.068, 45.0),
        endpoint_abs_tolerance=0.30,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 3 (Surcharge 50kPa Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.6485174011401,
                yc=61.5854419184982,
                r=36.6607805519873,
                x_left=30.0003512982362,
                y_left=25.0001756491181,
                x_right=52.891875115183,
                y_right=35.0,
            ),
            loads=LoadsInput(
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=50.0,
                    placement="crest_infinite",
                )
            ),
        ),
        expected_fos=0.903987,
        fos_tolerance=0.005,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 5 (Water Surfaces Hu=1 Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_uniform_soils(gamma=18.82, c=41.65, phi_deg=15.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.7816099623784,
                yc=45.4165765413013,
                r=31.9496411014504,
                x_left=18.0011387032865,
                y_left=15.0007591355243,
                x_right=57.9854921577304,
                y_right=35.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=1.116190,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 5 (Water Surfaces Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_uniform_soils(gamma=18.82, c=41.65, phi_deg=15.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.435184386849,
                yc=45.2985429525467,
                r=31.7351010556423,
                x_left=17.9951137322134,
                y_left=15.0,
                x_right=57.4527900886098,
                y_right=35.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=1.157200,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 6 (Ru Coefficient Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=-30.0, l=60.0, x_toe=10.0, y_toe=40.0),
            soils=_uniform_soils(gamma=18.0, c=10.8, phi_deg=40.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=69.4716746369335,
                yc=90.1503711737807,
                r=80.1517372879095,
                x_left=6.94774912515767,
                y_left=40.0,
                x_right=69.9992594556713,
                y_right=10.0003702721644,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="ru_coefficient",
                    ru=0.5,
                )
            ),
        ),
        expected_fos=1.001250,
        fos_tolerance=0.005,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 7 (Ponded Water Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=6.0, l=2.0, x_toe=5.0, y_toe=3.0),
            soils=_uniform_soils(gamma=16.0, c=12.0, phi_deg=38.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=1.65885679531231,
                yc=9.0,
                r=6.865877145366,
                x_left=5.00078365866115,
                y_left=3.00235097598346,
                x_right=8.52473394067831,
                y_right=9.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 4.609), (5.53621, 4.60862), (6.44028, 7.32085), (12.0, 8.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=0.940158,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 8 (Ponded Water Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=6.0, l=7.0, x_toe=5.0, y_toe=3.0),
            soils=_uniform_soils(gamma=16.0, c=12.0, phi_deg=38.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=5.81157572491755,
                yc=13.042352415468,
                r=10.0749729401736,
                x_left=5.00012832564169,
                y_left=3.00010999340716,
                x_right=15.0400353306367,
                y_right=9.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 7.184), (9.8819, 7.18448), (20.0, 9.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=2.511620,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 9 (Horizontal Seismic + Ru=0.5 Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=25.0, l=75.0, x_toe=0.0, y_toe=0.0),
            soils=_uniform_soils(gamma=20.0, c=25.0, phi_deg=30.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=30,
                tolerance=1e-5,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=20.9283536406624,
                yc=88.4703184347808,
                r=90.9140128025877,
                x_left=-0.00870632289452189,
                y_left=0.0,
                x_right=86.0196464658676,
                y_right=25.0,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0),
                groundwater=GroundwaterInput(
                    model="ru_coefficient",
                    ru=0.5,
                ),
            ),
        ),
        expected_fos=0.987678,
        fos_tolerance=0.01,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 10 (Horizontal Seismic + Surcharge + Ponded Toe Water Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=16.6916223321657,
                yc=25.6398893956998,
                r=17.0901183698696,
                x_left=9.80206461149667,
                y_left=10.0,
                x_right=31.7187426990865,
                y_right=17.5,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.25, kv=0.0),
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=50.0,
                    placement="crest_range",
                    x_start=25.0,
                    x_end=35.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 11.0), (12.0, 11.0), (25.0, 15.0), (35.0, 15.0)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.907907,
        fos_tolerance=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        search_method="direct_global_circular",
        name="Case 2 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=90,
                    max_evaluations=1200,
                    min_improvement=1e-4,
                    stall_iterations=12,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (bishop simplified) global minimum.
        benchmark_fos=2.10296,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        search_method="direct_global_circular",
        name="Case 3 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=120,
                    max_evaluations=1800,
                    min_improvement=1e-4,
                    stall_iterations=15,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.986442,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        search_method="direct_global_circular",
        name="Case 4 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=140,
                    max_evaluations=2200,
                    min_improvement=1e-4,
                    stall_iterations=18,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.234670,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        search_method="cuckoo_global_circular",
        name="Case 2 (Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=300,
                    max_evaluations=7000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (bishop simplified) global minimum.
        benchmark_fos=2.10296,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        search_method="cuckoo_global_circular",
        name="Case 3 (Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=300,
                    max_evaluations=7000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.986442,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        search_method="cuckoo_global_circular",
        name="Case 4 (Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=300,
                    max_evaluations=7000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.234670,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        search_method="cmaes_global_circular",
        name="Case 2 (CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=4500,
                    direct_prescan_evaluations=600,
                    cmaes_population_size=8,
                    cmaes_max_iterations=180,
                    cmaes_restarts=2,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=80,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (bishop simplified) global minimum.
        benchmark_fos=2.10296,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        search_method="cmaes_global_circular",
        name="Case 3 (CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=5500,
                    direct_prescan_evaluations=800,
                    cmaes_population_size=8,
                    cmaes_max_iterations=200,
                    cmaes_restarts=2,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=100,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.986442,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        search_method="cmaes_global_circular",
        name="Case 4 (CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="bishop_simplified",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=7000,
                    direct_prescan_evaluations=1200,
                    cmaes_population_size=10,
                    cmaes_max_iterations=250,
                    cmaes_restarts=3,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=120,
                    min_improvement=1e-4,
                    stall_iterations=30,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.234670,
        margin=0.01,
    ),
)


SPENCER_VERIFICATION_CASES: tuple[VerificationCase, ...] = (
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 2 (Spencer Prescribed Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=13.689,
                yc=25.558,
                r=15.989,
                x_left=10.0005216402222,
                y_left=10.0002608201111,
                x_right=27.4990237870903,
                y_right=17.5,
            ),
        ),
        expected_fos=2.11168,
        fos_tolerance=0.005,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 3 (Spencer Prescribed Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=30.2546073537702,
                yc=51.7886948308462,
                r=26.7899128131506,
                x_left=29.9991512988288,
                y_left=25.0,
                x_right=51.1313684630259,
                y_right=35.0,
            ),
        ),
        expected_fos=0.985334,
        fos_tolerance=0.002,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 4 (Spencer Prescribed Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=22.5811777177525,
                yc=64.3127170691117,
                r=39.9948933227408,
                x_left=30.0195115924048,
                y_left=25.0156092739238,
                x_right=57.6041766085651,
                y_right=45.0,
            ),
        ),
        expected_fos=1.23141,
        fos_tolerance=0.002,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 3 (Spencer Surcharge 50kPa Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.6485174011401,
                yc=61.5854419184982,
                r=36.6607805519873,
                x_left=30.0003512982362,
                y_left=25.0001756491181,
                x_right=52.891875115183,
                y_right=35.0,
            ),
            loads=LoadsInput(
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=50.0,
                    placement="crest_infinite",
                )
            ),
        ),
        expected_fos=0.903192,
        fos_tolerance=0.005,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 5 (Spencer Water Surfaces Hu=1 Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_uniform_soils(gamma=18.82, c=41.65, phi_deg=15.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.6258499840977,
                yc=45.3623063863069,
                r=31.8505670075193,
                x_left=18.0011387032865,
                y_left=15.0007591355243,
                x_right=57.7436391635308,
                y_right=35.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=1.116480,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 5 (Spencer Water Surfaces Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_uniform_soils(gamma=18.82, c=41.65, phi_deg=15.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=27.435184386849,
                yc=45.2985429525467,
                r=31.7351010556423,
                x_left=17.9951137322134,
                y_left=15.0,
                x_right=57.4527900886098,
                y_right=35.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 15.0), (18.0, 15.0), (30.0, 23.0), (48.0, 29.0), (66.0, 32.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=1.157020,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 6 (Spencer Ru Coefficient Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=-30.0, l=60.0, x_toe=10.0, y_toe=40.0),
            soils=_uniform_soils(gamma=18.0, c=10.8, phi_deg=40.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=30,
                tolerance=0.0001,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=69.6211856957322,
                yc=90.016174054555,
                r=80.0166969745064,
                x_left=7.16276650620701,
                y_left=40.0,
                x_right=69.9992594556713,
                y_right=10.0003702721644,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="ru_coefficient",
                    ru=0.5,
                )
            ),
        ),
        expected_fos=1.018880,
        fos_tolerance=0.005,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 7 (Spencer Ponded Water Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=6.0, l=2.0, x_toe=5.0, y_toe=3.0),
            soils=_uniform_soils(gamma=16.0, c=12.0, phi_deg=38.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=2.47419041573854,
                yc=10.3792666017876,
                r=7.75902007436276,
                x_left=5.01615097845115,
                y_left=3.04845293535344,
                x_right=10.1096351411987,
                y_right=9.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 4.609), (5.53621, 4.60862), (6.44028, 7.32085), (12.0, 8.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=1.049400,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 8 (Spencer Ponded Water Hu=Auto Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=6.0, l=7.0, x_toe=5.0, y_toe=3.0),
            soils=_uniform_soils(gamma=16.0, c=12.0, phi_deg=38.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=5.81157572491755,
                yc=13.042352415468,
                r=10.0749729401736,
                x_left=5.00012832564169,
                y_left=3.00010999340716,
                x_right=15.0400353306367,
                y_right=9.0,
            ),
            loads=LoadsInput(
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 7.184), (9.8819, 7.18448), (20.0, 9.0)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                )
            ),
        ),
        expected_fos=2.505910,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 9 (Spencer Horizontal Seismic + Ru=0.5 Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=25.0, l=75.0, x_toe=0.0, y_toe=0.0),
            soils=_uniform_soils(gamma=20.0, c=25.0, phi_deg=30.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=30,
                tolerance=1e-5,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=20.7350565491191,
                yc=88.2435394440438,
                r=90.6489158881829,
                x_left=-0.00870632289469242,
                y_left=0.0,
                x_right=85.6771897932044,
                y_right=25.0,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0),
                groundwater=GroundwaterInput(
                    model="ru_coefficient",
                    ru=0.5,
                ),
            ),
        ),
        expected_fos=1.00112,
        fos_tolerance=0.01,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 10 (Spencer Horizontal Seismic + Surcharge + Ponded Toe Water Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=50,
                tolerance=0.001,
                max_iter=75,
                f_init=1.0,
            ),
            prescribed_surface=PrescribedCircleInput(
                xc=16.5999008143235,
                yc=25.5847178540433,
                r=17.0027647055,
                x_left=9.80206461149666,
                y_left=10.0,
                x_right=31.5575525301214,
                y_right=17.5,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.25, kv=0.0),
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=50.0,
                    placement="crest_range",
                    x_start=25.0,
                    x_end=35.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 11.0), (12.0, 11.0), (25.0, 15.0), (35.0, 15.0)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.918623,
        fos_tolerance=0.01,
    ),
    AutoRefineVerificationCase(
        case_type="auto_refine_parity",
        analysis_method="spencer",
        name="Case 3 (Spencer Auto-Refine Parity)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="auto_refine_circular",
                auto_refine_circular=AutoRefineSearchInput(
                    divisions_along_slope=20,
                    circles_per_division=10,
                    iterations=10,
                    divisions_to_use_next_iteration_pct=50.0,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        expected_fos=0.985334,
        fos_tolerance=0.002,
        expected_radius=26.7899128131506,
        radius_rel_tolerance=0.12,
        expected_center=(30.2546073537702, 51.7886948308462),
        expected_left=(29.9991512988288, 25.0),
        expected_right=(51.1313684630259, 35.0),
        endpoint_abs_tolerance=0.30,
    ),
    AutoRefineVerificationCase(
        case_type="auto_refine_parity",
        analysis_method="spencer",
        name="Case 4 (Spencer Auto-Refine Parity)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="auto_refine_circular",
                auto_refine_circular=AutoRefineSearchInput(
                    divisions_along_slope=30,
                    circles_per_division=15,
                    iterations=15,
                    divisions_to_use_next_iteration_pct=50.0,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        expected_fos=1.23141,
        fos_tolerance=0.002,
        expected_radius=39.9948933227408,
        radius_rel_tolerance=0.12,
        expected_center=(22.5811777177525, 64.3127170691117),
        expected_left=(30.0195115924048, 25.0156092739238),
        expected_right=(57.6041766085651, 45.0),
        endpoint_abs_tolerance=0.30,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        analysis_method="spencer",
        search_method="direct_global_circular",
        name="Case 2 (Spencer Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=90,
                    max_evaluations=1200,
                    min_improvement=1e-4,
                    stall_iterations=12,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (spencer) global minimum.
        benchmark_fos=2.09717,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        analysis_method="spencer",
        search_method="direct_global_circular",
        name="Case 3 (Spencer Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=120,
                    max_evaluations=1800,
                    min_improvement=1e-4,
                    stall_iterations=15,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.985334,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        analysis_method="spencer",
        search_method="direct_global_circular",
        name="Case 4 (Spencer Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="direct_global_circular",
                direct_global_circular=DirectGlobalSearchInput(
                    max_iterations=140,
                    max_evaluations=2200,
                    min_improvement=1e-4,
                    stall_iterations=18,
                    min_rectangle_half_size=1e-3,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.23141,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        analysis_method="spencer",
        search_method="cuckoo_global_circular",
        name="Case 2 (Spencer Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=320,
                    max_evaluations=8000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (spencer) global minimum.
        benchmark_fos=2.09717,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        analysis_method="spencer",
        search_method="cuckoo_global_circular",
        name="Case 3 (Spencer Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=300,
                    max_evaluations=7000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.985334,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cuckoo_global_search_benchmark",
        analysis_method="spencer",
        search_method="cuckoo_global_circular",
        name="Case 4 (Spencer Cuckoo Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cuckoo_global_circular",
                cuckoo_global_circular=CuckooGlobalSearchInput(
                    population_size=40,
                    max_iterations=300,
                    max_evaluations=7000,
                    discovery_rate=0.25,
                    levy_beta=1.5,
                    alpha_max=0.5,
                    alpha_min=0.05,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=0,
                    post_polish=True,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.23141,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        analysis_method="spencer",
        search_method="cmaes_global_circular",
        name="Case 2 (Spencer CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            soils=_uniform_soils(gamma=20.0, c=20.0, phi_deg=20.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=7,
                tolerance=0.005,
                max_iter=50,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=4500,
                    direct_prescan_evaluations=600,
                    cmaes_population_size=8,
                    cmaes_max_iterations=180,
                    cmaes_restarts=2,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=80,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=2.5, x_max=40.0),
                ),
            ),
        ),
        # Slide2 Case2_Search (spencer) global minimum.
        benchmark_fos=2.09717,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        analysis_method="spencer",
        search_method="cmaes_global_circular",
        name="Case 3 (Spencer CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=20.0, c=3.0, phi_deg=19.6),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=5500,
                    direct_prescan_evaluations=800,
                    cmaes_population_size=8,
                    cmaes_max_iterations=200,
                    cmaes_restarts=2,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=100,
                    min_improvement=1e-4,
                    stall_iterations=25,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=20.0, x_max=70.0),
                ),
            ),
        ),
        benchmark_fos=0.985334,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="cmaes_global_search_benchmark",
        analysis_method="spencer",
        search_method="cmaes_global_circular",
        name="Case 4 (Spencer CMAES Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            soils=_uniform_soils(gamma=16.0, c=9.0, phi_deg=32.0),
            analysis=AnalysisInput(
                method="spencer",
                n_slices=25,
                tolerance=0.0001,
                max_iter=100,
                f_init=1.0,
            ),
            prescribed_surface=None,
            search=SearchInput(
                method="cmaes_global_circular",
                cmaes_global_circular=CmaesGlobalSearchInput(
                    max_evaluations=7000,
                    direct_prescan_evaluations=1200,
                    cmaes_population_size=10,
                    cmaes_max_iterations=250,
                    cmaes_restarts=3,
                    cmaes_sigma0=0.15,
                    polish_max_evaluations=120,
                    min_improvement=1e-4,
                    stall_iterations=30,
                    seed=1,
                    post_polish=True,
                    invalid_penalty=1e6,
                    nonconverged_penalty=1e5,
                    search_limits=SearchLimitsInput(x_min=10.0, x_max=95.0),
                ),
            ),
        ),
        benchmark_fos=1.23141,
        margin=0.01,
    ),
)

NON_UNIFORM_PRESCRIBED_CASES: tuple[VerificationCase, ...] = (
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 11 (Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_case11_soils(),
            analysis=AnalysisInput(method="bishop_simplified", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=34.3447952018146,
                yc=43.1772707870956,
                r=18.7077752528147,
                x_left=29.9212579698668,
                y_left=25.0,
                x_right=51.1707601781344,
                y_right=35.0,
            ),
        ),
        expected_fos=1.40357,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 11 (Spencer Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_case11_soils(),
            analysis=AnalysisInput(method="spencer", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=34.2739217263841,
                yc=43.1289861550126,
                r=18.6386863467291,
                x_left=29.9448929989319,
                y_left=25.0,
                x_right=51.0465247689461,
                y_right=35.0,
            ),
        ),
        expected_fos=1.37319,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 11 (Water Seismic Surcharge Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_case11_soils(),
            analysis=AnalysisInput(method="bishop_simplified", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=34.1452863060215,
                yc=47.906488439106,
                r=26.0896796695384,
                x_left=21.6567246335058,
                y_left=25.0,
                x_right=56.8189260983078,
                y_right=35.0,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.2, kv=0.0),
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=10.0,
                    placement="crest_range",
                    x_start=50.0,
                    x_end=70.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((20.0, 25.0), (30.0, 25.0), (50.0, 29.0), (70.0, 33.3746)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.729648,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 11 (Spencer Water Seismic Surcharge Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            soils=_case11_soils(),
            analysis=AnalysisInput(method="spencer", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=34.4313227841838,
                yc=47.6588404609722,
                r=25.6870443751625,
                x_left=22.3316865212303,
                y_left=25.0,
                x_right=56.7825645151308,
                y_right=35.0,
            ),
            loads=LoadsInput(
                seismic=SeismicLoadInput(model="pseudo_static", kh=0.2, kv=0.0),
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=10.0,
                    placement="crest_range",
                    x_start=50.0,
                    x_end=70.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((20.0, 25.0), (30.0, 25.0), (50.0, 29.0), (70.0, 33.3746)),
                    hu=GroundwaterHuInput(mode="custom", value=1.0),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.739875,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 12 (Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_case12_soils(),
            analysis=AnalysisInput(method="bishop_simplified", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=26.9670236395274,
                yc=45.1403590545699,
                r=31.44959404703,
                x_left=17.9872841230053,
                y_left=15.0,
                x_right=56.7369763430066,
                y_right=35.0,
            ),
        ),
        expected_fos=0.419809,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 12 (Spencer Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_case12_soils(),
            analysis=AnalysisInput(method="spencer", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=26.9670236395274,
                yc=45.1403590545699,
                r=31.44959404703,
                x_left=17.9872841230053,
                y_left=15.0,
                x_right=56.7369763430066,
                y_right=35.0,
            ),
        ),
        expected_fos=0.42273,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 12 (Water Surcharge Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_case12_soils(),
            analysis=AnalysisInput(method="bishop_simplified", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=27.0463858773805,
                yc=45.1395477433383,
                r=31.4301149458238,
                x_left=18.0408333231127,
                y_left=15.0272222154085,
                x_right=56.7960362462211,
                y_right=35.0,
            ),
            loads=LoadsInput(
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=100.0,
                    placement="crest_range",
                    x_start=48.0,
                    x_end=55.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 19.0), (24.0, 19.0), (56.976, 32.2524), (96.0, 32.2524)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.310792,
        fos_tolerance=0.001,
    ),
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        analysis_method="spencer",
        name="Case 12 (Spencer Water Surcharge Non-Uniform Prescribed)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=30.0, x_toe=18.0, y_toe=15.0),
            soils=_case12_soils(),
            analysis=AnalysisInput(method="spencer", n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
            prescribed_surface=PrescribedCircleInput(
                xc=27.0463858773805,
                yc=45.1395477433383,
                r=31.4301149458238,
                x_left=18.0408333231127,
                y_left=15.0272222154085,
                x_right=56.7960362462211,
                y_right=35.0,
            ),
            loads=LoadsInput(
                uniform_surcharge=UniformSurchargeInput(
                    magnitude_kpa=100.0,
                    placement="crest_range",
                    x_start=48.0,
                    x_end=55.0,
                ),
                groundwater=GroundwaterInput(
                    model="water_surfaces",
                    surface=((0.0, 19.0), (24.0, 19.0), (56.976, 32.2524), (96.0, 32.2524)),
                    hu=GroundwaterHuInput(mode="auto", value=None),
                    gamma_w=9.81,
                ),
            ),
        ),
        expected_fos=0.31391,
        fos_tolerance=0.001,
    ),
)

NON_UNIFORM_SEARCH_VERIFICATION_CASES_FULL = _build_non_uniform_search_verification_cases()
NON_UNIFORM_SEARCH_VERIFICATION_CASES_DEFAULT = _build_non_uniform_default_search_verification_cases(
    NON_UNIFORM_SEARCH_VERIFICATION_CASES_FULL
)
NON_UNIFORM_SEARCH_VERIFICATION_CASES = NON_UNIFORM_SEARCH_VERIFICATION_CASES_DEFAULT

NON_UNIFORM_VERIFICATION_CASES = (
    NON_UNIFORM_PRESCRIBED_CASES + NON_UNIFORM_SEARCH_VERIFICATION_CASES_DEFAULT
)

VERIFICATION_CASES = VERIFICATION_CASES + SPENCER_VERIFICATION_CASES + NON_UNIFORM_VERIFICATION_CASES

