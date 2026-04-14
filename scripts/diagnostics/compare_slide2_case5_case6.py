from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import statistics
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from slope_stab.analysis import run_analysis
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.slicing.slice_generator import generate_vertical_slices
from slope_stab.surfaces.circular import CircularSlipSurface
from slope_stab.verification.cases import PrescribedVerificationCase, VERIFICATION_CASES


@dataclass(frozen=True)
class Scenario:
    label: str
    case_name: str
    s01_relpath: str
    method_label: str
    series_column_index: int


@dataclass(frozen=True)
class MetricStats:
    count: int
    max_abs: float
    mean_abs: float
    worst_index_1_based: int
    worst_expected: float
    worst_actual: float
    worst_abs: float


@dataclass(frozen=True)
class S01Data:
    series: dict[str, list[tuple[float, ...]]]
    min_slice_info: dict[str, list[tuple[float, ...]]]
    global_minimum_fos: dict[str, float]


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="Case 5 Hu=1 Bishop",
        case_name="Case 5 (Water Surfaces Hu=1 Benchmark)",
        s01_relpath="Verification/Bishop/Case 5/Hu=1/Case5_Hu=1.s01",
        method_label="bishop simplified",
        series_column_index=0,
    ),
    Scenario(
        label="Case 5 Hu=1 Spencer",
        case_name="Case 5 (Spencer Water Surfaces Hu=1 Benchmark)",
        s01_relpath="Verification/Bishop/Case 5/Hu=1/Case5_Hu=1.s01",
        method_label="spencer",
        series_column_index=1,
    ),
    Scenario(
        label="Case 5 Hu=Auto Bishop",
        case_name="Case 5 (Water Surfaces Hu=Auto Benchmark)",
        s01_relpath="Verification/Bishop/Case 5/Hu=Auto/Case5_Hu=Auto.s01",
        method_label="bishop simplified",
        series_column_index=0,
    ),
    Scenario(
        label="Case 5 Hu=Auto Spencer",
        case_name="Case 5 (Spencer Water Surfaces Hu=Auto Benchmark)",
        s01_relpath="Verification/Bishop/Case 5/Hu=Auto/Case5_Hu=Auto.s01",
        method_label="spencer",
        series_column_index=1,
    ),
    Scenario(
        label="Case 6 Ru Bishop",
        case_name="Case 6 (Ru Coefficient Benchmark)",
        s01_relpath="Verification/Bishop/Case 6/Case6.s01",
        method_label="bishop simplified",
        series_column_index=0,
    ),
    Scenario(
        label="Case 6 Ru Spencer",
        case_name="Case 6 (Spencer Ru Coefficient Benchmark)",
        s01_relpath="Verification/Bishop/Case 6/Case6.s01",
        method_label="spencer",
        series_column_index=1,
    ),
)


def _iter_numeric_rows(lines: list[str], start_index: int) -> tuple[list[tuple[float, ...]], int]:
    rows: list[tuple[float, ...]] = []
    idx = start_index
    while idx < len(lines) and not lines[idx].startswith("* "):
        line = lines[idx].strip()
        if line:
            parts = line.split()
            try:
                numeric = tuple(float(token) for token in parts)
                if numeric:
                    rows.append(numeric)
            except ValueError:
                pass
        idx += 1
    return rows, idx


def _parse_s01(path: Path) -> S01Data:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    series: dict[str, list[tuple[float, ...]]] = {}
    min_slice_info: dict[str, list[tuple[float, ...]]] = {}
    global_minimum_fos: dict[str, float] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line == "* name" and idx + 1 < len(lines):
            name = lines[idx + 1]
            seek = idx + 2
            while seek < len(lines) and lines[seek] != "* data":
                seek += 1
            if seek < len(lines) and lines[seek] == "* data":
                rows, new_idx = _iter_numeric_rows(lines, seek + 1)
                series[name] = rows
                idx = new_idx
                continue

        if line.startswith("* minimum slice info("):
            method_label = line.split("method=", maxsplit=1)[1].strip()
            rows, new_idx = _iter_numeric_rows(lines, idx + 1)
            min_slice_info[method_label] = rows
            idx = new_idx
            continue

        if line == "* Global Minimum FS (xc,yc,r,x1,y1,x2,y2,fs,name)":
            seek = idx + 1
            while seek < len(lines) and not lines[seek].startswith("* "):
                row = lines[seek].strip()
                if row:
                    parts = row.split()
                    if len(parts) >= 9:
                        try:
                            fs = float(parts[7])
                            method_label = " ".join(parts[8:]).strip()
                            if method_label:
                                global_minimum_fos[method_label] = fs
                        except ValueError:
                            pass
                seek += 1
            idx = seek
            continue

        idx += 1

    return S01Data(series=series, min_slice_info=min_slice_info, global_minimum_fos=global_minimum_fos)


def _select_column(rows: list[tuple[float, ...]], column_index: int) -> list[float]:
    return [float(row[column_index]) for row in rows if len(row) > column_index]


def _metric_stats(expected: Iterable[float], actual: Iterable[float]) -> MetricStats:
    expected_list = list(expected)
    actual_list = list(actual)
    count = min(len(expected_list), len(actual_list))
    if count == 0:
        return MetricStats(
            count=0,
            max_abs=0.0,
            mean_abs=0.0,
            worst_index_1_based=0,
            worst_expected=0.0,
            worst_actual=0.0,
            worst_abs=0.0,
        )

    abs_deltas = [abs(actual_list[i] - expected_list[i]) for i in range(count)]
    worst_idx = max(range(count), key=lambda i: abs_deltas[i])
    return MetricStats(
        count=count,
        max_abs=max(abs_deltas),
        mean_abs=statistics.fmean(abs_deltas),
        worst_index_1_based=worst_idx + 1,
        worst_expected=expected_list[worst_idx],
        worst_actual=actual_list[worst_idx],
        worst_abs=abs_deltas[worst_idx],
    )


def _case_by_name(name: str) -> PrescribedVerificationCase:
    for case in VERIFICATION_CASES:
        if isinstance(case, PrescribedVerificationCase) and case.name == name:
            return case
    raise KeyError(f"Could not locate prescribed verification case: {name}")


def main() -> int:
    print("Slide2 Comparison: Cases 5/6 Prescribed Surface Parity")
    print("Base Normal Force comparison uses derived N_total = normal + pore_force.")
    print("Pore Pressure comparison uses U/base_length from current implementation output.")
    print("")

    cache: dict[Path, S01Data] = {}

    for scenario in SCENARIOS:
        case = _case_by_name(scenario.case_name)
        result = run_analysis(case.project)
        project = case.project
        assert project.prescribed_surface is not None
        profile = UniformSlopeProfile(
            h=project.geometry.h,
            l=project.geometry.l,
            x_toe=project.geometry.x_toe,
            y_toe=project.geometry.y_toe,
        )
        surface = CircularSlipSurface(
            xc=project.prescribed_surface.xc,
            yc=project.prescribed_surface.yc,
            r=project.prescribed_surface.r,
        )
        slice_geometry = generate_vertical_slices(
            profile=profile,
            surface=surface,
            n_slices=project.analysis.n_slices,
            x_left=project.prescribed_surface.x_left,
            x_right=project.prescribed_surface.x_right,
            gamma=project.soils.materials[0].gamma,
            loads=project.loads,
        )
        s01_path = REPO_ROOT / scenario.s01_relpath
        s01 = cache.setdefault(s01_path, _parse_s01(s01_path))

        x_edges = [slice_geometry[0].x_left] + [slc.x_right for slc in slice_geometry]
        y_top_edges = [slice_geometry[0].y_top_left] + [slc.y_top_right for slc in slice_geometry]
        y_base_edges = [slice_geometry[0].y_base_left] + [slc.y_base_right for slc in slice_geometry]

        min_info_rows = s01.min_slice_info.get(scenario.method_label, [])
        s01_x_edges = [row[0] for row in min_info_rows if len(row) >= 4]
        s01_y_top_edges = [row[2] for row in min_info_rows if len(row) >= 4]
        s01_y_base_edges = [row[3] for row in min_info_rows if len(row) >= 4]

        s01_weights = _select_column(s01.series.get("Slice Weight", []), scenario.series_column_index)
        s01_pore_pressures = _select_column(s01.series.get("Pore Pressure", []), scenario.series_column_index)
        s01_base_normal = _select_column(s01.series.get("Base Normal Force", []), scenario.series_column_index)
        s01_fos = s01.global_minimum_fos.get(scenario.method_label)

        ours_weights = [slc.weight for slc in slice_geometry]
        ours_pore_pressures = [
            (slc.pore_force / slc.base_length) if slc.base_length > 0.0 else 0.0 for slc in slice_geometry
        ]
        ours_base_normal_total = [slc.normal + slc.pore_force for slc in result.slice_results]

        x_stats = _metric_stats(s01_x_edges, x_edges)
        y_top_stats = _metric_stats(s01_y_top_edges, y_top_edges)
        y_base_stats = _metric_stats(s01_y_base_edges, y_base_edges)
        weight_stats = _metric_stats(s01_weights, ours_weights)
        pore_stats = _metric_stats(s01_pore_pressures, ours_pore_pressures)
        base_normal_stats = _metric_stats(s01_base_normal, ours_base_normal_total)

        print(f"=== {scenario.label} ===")
        print(
            f"FOS: ours={result.fos:.8f}"
            + (f", slide2={s01_fos:.8f}, abs_delta={abs(result.fos - s01_fos):.8f}" if s01_fos is not None else "")
        )
        print(
            "Layout deltas: "
            f"x(max={x_stats.max_abs:.6g}, mean={x_stats.mean_abs:.6g}), "
            f"y_top(max={y_top_stats.max_abs:.6g}, mean={y_top_stats.mean_abs:.6g}), "
            f"y_base(max={y_base_stats.max_abs:.6g}, mean={y_base_stats.mean_abs:.6g})"
        )
        print(
            f"Slice Weight: max={weight_stats.max_abs:.6g}, mean={weight_stats.mean_abs:.6g}, "
            f"worst_slice={weight_stats.worst_index_1_based}"
        )
        print(
            f"Pore Pressure (U/L): max={pore_stats.max_abs:.6g}, mean={pore_stats.mean_abs:.6g}, "
            f"worst_slice={pore_stats.worst_index_1_based}, "
            f"slide2={pore_stats.worst_expected:.6g}, ours={pore_stats.worst_actual:.6g}"
        )
        print(
            "Base Normal Force (N_total = normal + pore_force): "
            f"max={base_normal_stats.max_abs:.6g}, mean={base_normal_stats.mean_abs:.6g}, "
            f"worst_slice={base_normal_stats.worst_index_1_based}, "
            f"slide2={base_normal_stats.worst_expected:.6g}, ours={base_normal_stats.worst_actual:.6g}"
        )
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
