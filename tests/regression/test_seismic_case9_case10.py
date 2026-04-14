from __future__ import annotations

import unittest
from pathlib import Path

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.materials.uniform_soils import build_uniform_soils_for_geometry
from slope_stab.models import (
    AnalysisInput,
    GeometryInput,
    GroundwaterHuInput,
    GroundwaterInput,
    LoadsInput,
    PrescribedCircleInput,
    ProjectInput,
    SeismicLoadInput,
    UniformSurchargeInput,
)
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface

_CASE9_S01 = Path("Verification/Bishop/Case 9/Case9.s01")
_CASE10_S01 = Path("Verification/Bishop/Case 10/Case10/{9A4A67C1-D070-4ede-B3E6-99981501482B}.s01")


def _parse_s01_series(path: Path, name: str) -> tuple[list[float], list[float]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != "* name":
            continue
        if idx + 1 >= len(lines) or lines[idx + 1].strip() != name:
            continue
        j = idx + 2
        while j < len(lines) and lines[j].strip() != "* data":
            j += 1
        if j >= len(lines):
            break
        j += 1
        first: list[float] = []
        second: list[float] = []
        while j < len(lines):
            row = lines[j].strip()
            if not row:
                j += 1
                continue
            if row.startswith("* name"):
                return first, second
            parts = row.split()
            if len(parts) < 2:
                raise AssertionError(f"Malformed row in {path} for '{name}': {row}")
            first.append(float(parts[0]))
            second.append(float(parts[1]))
            j += 1
        return first, second
    raise AssertionError(f"Series '{name}' not found in {path}")


def _mape_percent(observed: list[float], predicted: list[float]) -> float:
    if len(observed) != len(predicted):
        raise AssertionError("Observed/predicted lengths do not match.")
    if not observed:
        return 0.0
    total = 0.0
    for obs, pred in zip(observed, predicted):
        denom = abs(obs) if abs(obs) > 1e-12 else 1.0
        total += abs(pred - obs) / denom
    return 100.0 * (total / len(observed))


def _max_abs_pct_error(observed: list[float], predicted: list[float], indices: list[int]) -> float:
    if not indices:
        return 0.0
    worst = 0.0
    for i in indices:
        obs = observed[i]
        pred = predicted[i]
        denom = abs(obs) if abs(obs) > 1e-12 else 1.0
        worst = max(worst, 100.0 * abs(pred - obs) / denom)
    return worst


def _toe_region_indices(observed_h: list[float], observed_w: list[float], kh: float) -> list[int]:
    indices = [i for i, (h, w) in enumerate(zip(observed_h, observed_w)) if w > 1e-12 and (h / w) < (0.9 * kh)]
    if indices:
        return indices
    return list(range(min(5, len(observed_h))))


def _case9_profile() -> UniformSlopeProfile:
    return UniformSlopeProfile(h=25.0, l=75.0, x_toe=0.0, y_toe=0.0)


def _case10_profile() -> UniformSlopeProfile:
    return UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)


def _case9_loads(*, seismic: bool) -> LoadsInput:
    return LoadsInput(
        seismic=(SeismicLoadInput(model="pseudo_static", kh=0.132, kv=0.0) if seismic else None),
        groundwater=GroundwaterInput(model="ru_coefficient", ru=0.5),
    )


def _case10_loads(*, seismic: bool) -> LoadsInput:
    # Slide2 Case 10 artifact reports Hu Type = Custom and Hu = 1.
    return LoadsInput(
        seismic=(SeismicLoadInput(model="pseudo_static", kh=0.25, kv=0.0) if seismic else None),
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
    )


def _case9_project(method: str) -> ProjectInput:
    geometry = GeometryInput(h=25.0, l=75.0, x_toe=0.0, y_toe=0.0)
    if method == "bishop_simplified":
        surface = PrescribedCircleInput(
            xc=20.9283536406624,
            yc=88.4703184347808,
            r=90.9140128025877,
            x_left=-0.00870632289452189,
            y_left=0.0,
            x_right=86.0196464658676,
            y_right=25.0,
        )
    elif method == "spencer":
        surface = PrescribedCircleInput(
            xc=20.7350565491191,
            yc=88.2435394440438,
            r=90.6489158881829,
            x_left=-0.00870632289469242,
            y_left=0.0,
            x_right=85.6771897932044,
            y_right=25.0,
        )
    else:
        raise AssertionError(f"Unsupported method: {method}")

    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=20.0, cohesion=25.0, phi_deg=30.0),
        analysis=AnalysisInput(method=method, n_slices=30, tolerance=1e-5, max_iter=50, f_init=1.0),
        prescribed_surface=surface,
        loads=_case9_loads(seismic=True),
    )


def _case10_project(method: str) -> ProjectInput:
    geometry = GeometryInput(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
    if method == "bishop_simplified":
        surface = PrescribedCircleInput(
            xc=16.6916223321657,
            yc=25.6398893956998,
            r=17.0901183698696,
            x_left=9.80206461149667,
            y_left=10.0,
            x_right=31.7187426990865,
            y_right=17.5,
        )
    elif method == "spencer":
        surface = PrescribedCircleInput(
            xc=16.5999008143235,
            yc=25.5847178540433,
            r=17.0027647055,
            x_left=9.80206461149666,
            y_left=10.0,
            x_right=31.5575525301214,
            y_right=17.5,
        )
    else:
        raise AssertionError(f"Unsupported method: {method}")

    return ProjectInput(
        units="metric",
        geometry=geometry,
        soils=build_uniform_soils_for_geometry(geometry=geometry, gamma=20.0, cohesion=20.0, phi_deg=20.0),
        analysis=AnalysisInput(method=method, n_slices=50, tolerance=0.001, max_iter=75, f_init=1.0),
        prescribed_surface=surface,
        loads=_case10_loads(seismic=True),
    )


class SeismicPrototypeGateTests(unittest.TestCase):
    def test_case9_case10_mass_basis_and_sign_gate(self) -> None:
        case9_weight_b, _ = _parse_s01_series(_CASE9_S01, "Slice Weight")
        case10_weight_b, _ = _parse_s01_series(_CASE10_S01, "Slice Weight")
        case9_h_b, _ = _parse_s01_series(_CASE9_S01, "Horizontal Seismic Force")
        case10_h_b, _ = _parse_s01_series(_CASE10_S01, "Horizontal Seismic Force")

        case9_slices = generate_vertical_slices(
            profile=_case9_profile(),
            surface=CircularSlipSurface(xc=20.9283536406624, yc=88.4703184347808, r=90.9140128025877),
            n_slices=30,
            x_left=-0.00870632289452189,
            x_right=86.0196464658676,
            gamma=20.0,
            loads=_case9_loads(seismic=False),
        )
        case10_slices = generate_vertical_slices(
            profile=_case10_profile(),
            surface=CircularSlipSurface(xc=16.6916223321657, yc=25.6398893956998, r=17.0901183698696),
            n_slices=50,
            x_left=9.80206461149667,
            x_right=31.7187426990865,
            gamma=20.0,
            loads=_case10_loads(seismic=False),
        )

        self.assertEqual(len(case9_h_b), len(case9_slices))
        self.assertEqual(len(case10_h_b), len(case10_slices))

        toe_indices = _toe_region_indices(case10_h_b, case10_weight_b, kh=0.25)

        passers: list[tuple[str, int, float, float, float]] = []
        for basis in ("soil_weight", "soil_plus_external_y"):
            for sign in (1, -1):
                pred9 = []
                for slc in case9_slices:
                    mass = slc.weight if basis == "soil_weight" else slc.weight + slc.external_force_y
                    pred9.append(sign * 0.132 * mass)

                pred10 = []
                for slc in case10_slices:
                    mass = slc.weight if basis == "soil_weight" else slc.weight + slc.external_force_y
                    pred10.append(sign * 0.25 * mass)

                case9_mape = _mape_percent(case9_h_b, pred9)
                case10_mape = _mape_percent(case10_h_b, pred10)
                case10_toe_max = _max_abs_pct_error(case10_h_b, pred10, toe_indices)
                if case9_mape <= 0.5 and case10_mape <= 2.0 and case10_toe_max <= 5.0:
                    passers.append((basis, sign, case9_mape, case10_mape, case10_toe_max))

        self.assertEqual(len(passers), 1, msg=f"Expected one passing candidate, got: {passers}")
        basis, sign, case9_mape, case10_mape, case10_toe_max = passers[0]
        self.assertEqual(basis, "soil_weight")
        self.assertEqual(sign, 1)
        self.assertLessEqual(case9_mape, 0.5)
        self.assertLessEqual(case10_mape, 2.0)
        self.assertLessEqual(case10_toe_max, 5.0)


class SeismicParityTests(unittest.TestCase):
    def _assert_case(
        self,
        *,
        project: ProjectInput,
        expected_fos: float,
        expected_horizontal_force: list[float],
        expected_weight: list[float],
        kh: float,
        mape_threshold: float,
        toe_threshold: float | None,
    ) -> None:
        result = run_analysis(project)
        self.assertLessEqual(abs(result.fos - expected_fos), 0.01)

        observed = [slc.seismic_force_x for slc in result.slice_results]
        self.assertEqual(len(observed), len(expected_horizontal_force))
        self.assertLessEqual(_mape_percent(expected_horizontal_force, observed), mape_threshold)
        if toe_threshold is not None:
            toe_indices = _toe_region_indices(expected_horizontal_force, expected_weight, kh=kh)
            self.assertLessEqual(
                _max_abs_pct_error(expected_horizontal_force, observed, toe_indices),
                toe_threshold,
            )

    def test_case9_bishop_and_spencer_parity(self) -> None:
        case9_weight_b, case9_weight_s = _parse_s01_series(_CASE9_S01, "Slice Weight")
        case9_h_b, case9_h_s = _parse_s01_series(_CASE9_S01, "Horizontal Seismic Force")

        self._assert_case(
            project=_case9_project("bishop_simplified"),
            expected_fos=0.987678,
            expected_horizontal_force=case9_h_b,
            expected_weight=case9_weight_b,
            kh=0.132,
            mape_threshold=0.5,
            toe_threshold=None,
        )
        self._assert_case(
            project=_case9_project("spencer"),
            expected_fos=1.00112,
            expected_horizontal_force=case9_h_s,
            expected_weight=case9_weight_s,
            kh=0.132,
            mape_threshold=0.5,
            toe_threshold=None,
        )

    def test_case10_bishop_and_spencer_parity(self) -> None:
        case10_weight_b, case10_weight_s = _parse_s01_series(_CASE10_S01, "Slice Weight")
        case10_h_b, case10_h_s = _parse_s01_series(_CASE10_S01, "Horizontal Seismic Force")

        self._assert_case(
            project=_case10_project("bishop_simplified"),
            expected_fos=0.907907,
            expected_horizontal_force=case10_h_b,
            expected_weight=case10_weight_b,
            kh=0.25,
            mape_threshold=2.0,
            toe_threshold=5.0,
        )
        self._assert_case(
            project=_case10_project("spencer"),
            expected_fos=0.918623,
            expected_horizontal_force=case10_h_s,
            expected_weight=case10_weight_s,
            kh=0.25,
            mape_threshold=2.0,
            toe_threshold=5.0,
        )


if __name__ == "__main__":
    unittest.main()
