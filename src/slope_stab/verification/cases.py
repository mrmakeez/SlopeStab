from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from slope_stab.models import (
    AnalysisInput,
    AutoRefineSearchInput,
    DirectGlobalSearchInput,
    GeometryInput,
    MaterialInput,
    PrescribedCircleInput,
    ProjectInput,
    SearchInput,
    SearchLimitsInput,
)


@dataclass(frozen=True)
class PrescribedVerificationCase:
    case_type: str
    name: str
    project: ProjectInput
    expected_fos: float
    fos_tolerance: float
    expected_driving_moment: float
    expected_resisting_moment: float
    moment_rel_tolerance: float


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


@dataclass(frozen=True)
class GlobalSearchBenchmarkVerificationCase:
    case_type: str
    name: str
    project: ProjectInput
    benchmark_fos: float
    margin: float


VerificationCase: TypeAlias = (
    PrescribedVerificationCase
    | AutoRefineVerificationCase
    | GlobalSearchBenchmarkVerificationCase
)


VERIFICATION_CASES: tuple[VerificationCase, ...] = (
    PrescribedVerificationCase(
        case_type="prescribed_benchmark",
        name="Case 1",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            material=MaterialInput(gamma=20.0, c=3.0, phi_deg=19.6),
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
            material=MaterialInput(gamma=20.0, c=20.0, phi_deg=20.0),
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
            material=MaterialInput(gamma=20.0, c=3.0, phi_deg=19.6),
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
            material=MaterialInput(gamma=16.0, c=9.0, phi_deg=32.0),
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
        endpoint_abs_tolerance=0.20,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        name="Case 2 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0),
            material=MaterialInput(gamma=20.0, c=20.0, phi_deg=20.0),
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
        benchmark_fos=2.11283,
        margin=0.01,
    ),
    GlobalSearchBenchmarkVerificationCase(
        case_type="global_search_benchmark",
        name="Case 3 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=10.0, l=20.0, x_toe=30.0, y_toe=25.0),
            material=MaterialInput(gamma=20.0, c=3.0, phi_deg=19.6),
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
        name="Case 4 (Global Search Benchmark)",
        project=ProjectInput(
            units="metric",
            geometry=GeometryInput(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
            material=MaterialInput(gamma=16.0, c=9.0, phi_deg=32.0),
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
)
