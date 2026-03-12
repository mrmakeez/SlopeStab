from __future__ import annotations

from dataclasses import dataclass

from slope_stab.models import AnalysisInput, GeometryInput, MaterialInput, PrescribedCircleInput, ProjectInput


@dataclass(frozen=True)
class VerificationCase:
    name: str
    project: ProjectInput
    expected_fos: float
    fos_tolerance: float
    expected_driving_moment: float
    expected_resisting_moment: float
    moment_rel_tolerance: float


VERIFICATION_CASES: tuple[VerificationCase, ...] = (
    VerificationCase(
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
    VerificationCase(
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
)
