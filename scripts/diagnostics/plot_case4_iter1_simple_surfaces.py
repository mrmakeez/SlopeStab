from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib
from matplotlib.lines import Line2D

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.models import PrescribedCircleInput
from slope_stab.search.auto_refine import (
    _build_retained_path,
    _circle_lower_y,
    _division_boundaries_and_midpoints_for_retained_path,
    _generate_pre_polish_pair_candidates,
    _surface_has_reverse_curvature,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PLOT_DIR = REPO_ROOT / "tmp" / "plots"
ROUND_DIGITS = 6


SurfaceKey = tuple[float, float, float, float, float, float, float]


class PlotScenario:
    def __init__(
        self,
        *,
        key: str,
        title: str,
        output_prefix: str,
        profile: UniformSlopeProfile,
        search_x_min: float,
        search_x_max: float,
        divisions_along_slope: int,
        circles_per_division: int,
        model_boundary_floor_y: float,
        s01_relpath: str,
    ) -> None:
        self.key = key
        self.title = title
        self.output_prefix = output_prefix
        self.profile = profile
        self.search_x_min = search_x_min
        self.search_x_max = search_x_max
        self.divisions_along_slope = divisions_along_slope
        self.circles_per_division = circles_per_division
        self.model_boundary_floor_y = model_boundary_floor_y
        self.s01_relpath = s01_relpath


SCENARIOS: dict[str, PlotScenario] = {
    "case4_iter1_simple": PlotScenario(
        key="case4_iter1_simple",
        title="Case4 Iter1 Simple",
        output_prefix="case4_iter1_simple",
        profile=UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=5,
        circles_per_division=5,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1_Simple/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
    "case4_iter1": PlotScenario(
        key="case4_iter1",
        title="Case4 Iter1",
        output_prefix="case4_iter1",
        profile=UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0),
        search_x_min=10.0,
        search_x_max=95.0,
        divisions_along_slope=30,
        circles_per_division=15,
        model_boundary_floor_y=20.0,
        s01_relpath="Verification/Bishop/Case 4/Case4_Iter1/{3A58A471-B82B-4b73-9E28-0A0D91A19FDE}.s01",
    ),
}


def _parse_slide2_s01_surfaces(path: Path) -> set[SurfaceKey]:
    lines = path.read_text().splitlines()
    surfaces: set[SurfaceKey] = set()
    center: tuple[float, float] | None = None
    line_idx = 0
    while line_idx < len(lines):
        line = lines[line_idx].strip()
        if line == "* surface center":
            center = tuple(map(float, lines[line_idx + 1].split()))
            line_idx += 2
            continue
        if line.startswith("* surface ") and "data" in line:
            if center is None:
                raise ValueError(f"Encountered surface data before a center in {path}.")
            radius, x_left, y_left, x_right, y_right = map(float, lines[line_idx + 1].split()[:5])
            surfaces.add(
                (
                    round(center[0], ROUND_DIGITS),
                    round(center[1], ROUND_DIGITS),
                    round(radius, ROUND_DIGITS),
                    round(x_left, ROUND_DIGITS),
                    round(y_left, ROUND_DIGITS),
                    round(x_right, ROUND_DIGITS),
                    round(y_right, ROUND_DIGITS),
                )
            )
            line_idx += 2
            continue
        line_idx += 1
    return surfaces


def _enumerate_ours(scenario: PlotScenario) -> set[SurfaceKey]:
    profile = scenario.profile
    retained_path = _build_retained_path(profile, scenario.search_x_min, scenario.search_x_max)
    _, midpoints = _division_boundaries_and_midpoints_for_retained_path(
        retained_path,
        scenario.divisions_along_slope,
    )

    surfaces: set[SurfaceKey] = set()
    for left_idx in range(scenario.divisions_along_slope):
        for right_idx in range(left_idx + 1, scenario.divisions_along_slope):
            candidates = _generate_pre_polish_pair_candidates(
                profile=profile,
                search_x_min=scenario.search_x_min,
                search_x_max=scenario.search_x_max,
                p_left=midpoints[left_idx],
                p_right=midpoints[right_idx],
                circles_per_division=scenario.circles_per_division,
                model_boundary_floor_y=scenario.model_boundary_floor_y,
            )
            for surface in candidates:
                if surface is None:
                    continue
                surfaces.add(
                    (
                        round(surface.xc, ROUND_DIGITS),
                        round(surface.yc, ROUND_DIGITS),
                        round(surface.r, ROUND_DIGITS),
                        round(surface.x_left, ROUND_DIGITS),
                        round(surface.y_left, ROUND_DIGITS),
                        round(surface.x_right, ROUND_DIGITS),
                        round(surface.y_right, ROUND_DIGITS),
                    )
                )
    return surfaces


def _surface_points(surface: SurfaceKey, samples: int = 240) -> tuple[list[float], list[float]]:
    xc, yc, radius, x_left, _, x_right, _ = surface
    xs = [x_left + (x_right - x_left) * idx / (samples - 1) for idx in range(samples)]
    ys = []
    for x in xs:
        inside = radius * radius - (x - xc) ** 2
        ys.append(yc - math.sqrt(max(inside, 0.0)))
    return xs, ys


def _surface_from_key(surface: SurfaceKey) -> PrescribedCircleInput:
    return PrescribedCircleInput(
        xc=surface[0],
        yc=surface[1],
        r=surface[2],
        x_left=surface[3],
        y_left=surface[4],
        x_right=surface[5],
        y_right=surface[6],
    )


def _reverse_curvature_count(surfaces: set[SurfaceKey]) -> int:
    return sum(1 for surface in surfaces if _surface_has_reverse_curvature(_surface_from_key(surface)))


def _surface_bounds(surfaces: set[SurfaceKey]) -> tuple[float, float, float, float]:
    if not surfaces:
        raise ValueError("At least one surface is required to compute bounds.")

    x_min = min(surface[3] for surface in surfaces)
    x_max = max(surface[5] for surface in surfaces)
    y_min = float("inf")
    y_max = float("-inf")
    for surface in surfaces:
        _, ys = _surface_points(surface)
        y_min = min(y_min, min(ys))
        y_max = max(y_max, max(ys))
    return x_min, x_max, y_min, y_max


def _plot_ground(
    ax,
    profile: UniformSlopeProfile,
    x_min: float,
    x_max: float,
    floor_y: float,
) -> None:
    xs = [x_min + (x_max - x_min) * idx / 400 for idx in range(401)]
    ys = [profile.y_ground(x) for x in xs]
    ax.plot(xs, ys, color="black", linewidth=2.2, label="Slope")
    ax.fill_between(xs, [floor_y] * len(xs), ys, color="#efe7d4", alpha=0.55)


def _plot_surface_set(ax, surfaces: set[SurfaceKey], color: str, alpha: float, linewidth: float) -> None:
    for surface in sorted(surfaces):
        xs, ys = _surface_points(surface)
        ax.plot(xs, ys, color=color, alpha=alpha, linewidth=linewidth)


def _plot_limits(profile: UniformSlopeProfile, surfaces: set[SurfaceKey]) -> tuple[tuple[float, float], tuple[float, float]]:
    x_min, x_max, y_min, y_max = _surface_bounds(surfaces)
    x_pad = max(2.0, 0.05 * (x_max - x_min))
    y_ground_min = min(profile.y_ground(x_min), profile.y_ground(x_max), profile.y_toe, profile.crest_y)
    y_ground_max = max(profile.y_ground(x_min), profile.y_ground(x_max), profile.y_toe, profile.crest_y)
    y_min = min(y_min, y_ground_min)
    y_max = max(y_max, y_ground_max)
    y_pad = max(1.0, 0.08 * (y_max - y_min))
    return (x_min - x_pad, x_max + x_pad), (y_min - y_pad, y_max + y_pad)


def _finish_plot(
    ax,
    title: str,
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
    legend_handles: list[Line2D],
    note_lines: list[str],
) -> None:
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_xlim(*x_limits)
    ax.set_ylim(*y_limits)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(handles=legend_handles, loc="best", frameon=True, framealpha=0.95)
    ax.text(
        0.015,
        0.015,
        "\n".join(note_lines),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        bbox={"facecolor": "white", "alpha": 0.92, "edgecolor": "#c8c8c8", "boxstyle": "round,pad=0.3"},
    )


def _save_plot(
    path: Path,
    title: str,
    plotter,
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
    legend_handles: list[Line2D],
    note_lines: list[str],
) -> None:
    x_span = x_limits[1] - x_limits[0]
    y_span = y_limits[1] - y_limits[0]
    width = 12.0
    height = max(4.8, width * (y_span / x_span) + 1.0)
    fig, ax = plt.subplots(figsize=(width, height), dpi=150)
    plotter(fig, ax)
    _finish_plot(
        ax,
        title,
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=legend_handles,
        note_lines=note_lines,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def _render_scenario(scenario: PlotScenario) -> None:
    profile = scenario.profile
    slide2 = _parse_slide2_s01_surfaces(REPO_ROOT / scenario.s01_relpath)
    ours = _enumerate_ours(scenario)

    shared = slide2 & ours
    slide2_only = slide2 - ours
    ours_only = ours - slide2
    slide2_reverse = _reverse_curvature_count(slide2)
    ours_reverse = _reverse_curvature_count(ours)
    shared_reverse = _reverse_curvature_count(shared)
    slide2_only_reverse = _reverse_curvature_count(slide2_only)
    ours_only_reverse = _reverse_curvature_count(ours_only)
    all_surfaces = slide2 | ours
    x_limits, y_limits = _plot_limits(profile, all_surfaces)
    note_lines = [
        f"Reverse curvature: Slide2 {slide2_reverse}, Ours {ours_reverse}, Shared {shared_reverse}",
        f"Mismatch reverse curvature: Slide2-only {slide2_only_reverse}, Ours-only {ours_only_reverse}",
    ]

    slope_handle = Line2D([0], [0], color="black", linewidth=2.2, label="Slope")
    current_handle = Line2D([0], [0], color="#0b5fff", linewidth=1.4, alpha=0.75, label=f"Ours ({len(ours)})")
    slide2_handle = Line2D([0], [0], color="#ca3c25", linewidth=1.4, alpha=0.75, label=f"Slide2 ({len(slide2)})")
    shared_handle = Line2D([0], [0], color="#7a7a7a", linewidth=1.4, alpha=0.85, label=f"Shared ({len(shared)})")
    slide2_only_handle = Line2D([0], [0], color="#ca3c25", linewidth=1.8, alpha=0.95, label=f"Slide2-only ({len(slide2_only)})")
    ours_only_handle = Line2D([0], [0], color="#0b5fff", linewidth=1.8, alpha=0.95, label=f"Ours-only ({len(ours_only)})")

    _save_plot(
        PLOT_DIR / f"{scenario.output_prefix}_current_auto_refine_surfaces.png",
        f"{scenario.title} Current Auto-Refine Surfaces ({len(ours)})",
        lambda _fig, ax: (
            _plot_ground(ax, profile, scenario.search_x_min, scenario.search_x_max, scenario.model_boundary_floor_y),
            _plot_surface_set(ax, ours, color="#0b5fff", alpha=0.25, linewidth=1.0),
        ),
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=[slope_handle, current_handle],
        note_lines=note_lines,
    )

    _save_plot(
        PLOT_DIR / f"{scenario.output_prefix}_slide2_surfaces.png",
        f"{scenario.title} Slide2 Stored Surfaces ({len(slide2)})",
        lambda _fig, ax: (
            _plot_ground(ax, profile, scenario.search_x_min, scenario.search_x_max, scenario.model_boundary_floor_y),
            _plot_surface_set(ax, slide2, color="#ca3c25", alpha=0.25, linewidth=1.0),
        ),
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=[slope_handle, slide2_handle],
        note_lines=note_lines,
    )

    def _overlay_plot(_fig, ax) -> None:
        _plot_ground(ax, profile, scenario.search_x_min, scenario.search_x_max, scenario.model_boundary_floor_y)
        _plot_surface_set(ax, slide2, color="#ca3c25", alpha=0.22, linewidth=1.0)
        _plot_surface_set(ax, ours, color="#0b5fff", alpha=0.22, linewidth=1.0)

    _save_plot(
        PLOT_DIR / f"{scenario.output_prefix}_slide2_vs_current_overlay.png",
        f"{scenario.title} Slide2 vs Current Overlay ({len(slide2)} vs {len(ours)})",
        _overlay_plot,
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=[slope_handle, slide2_handle, current_handle],
        note_lines=note_lines,
    )

    def _mismatch_plot(_fig, ax) -> None:
        _plot_ground(ax, profile, scenario.search_x_min, scenario.search_x_max, scenario.model_boundary_floor_y)
        _plot_surface_set(ax, slide2_only, color="#ca3c25", alpha=0.85, linewidth=1.6)
        _plot_surface_set(ax, ours_only, color="#0b5fff", alpha=0.85, linewidth=1.6)

    _save_plot(
        PLOT_DIR / f"{scenario.output_prefix}_mismatch_only_overlay.png",
        f"{scenario.title} Mismatch Only (Slide2-only {len(slide2_only)}, Ours-only {len(ours_only)})",
        _mismatch_plot,
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=[slope_handle, slide2_only_handle, ours_only_handle],
        note_lines=note_lines,
    )

    def _match_and_mismatch_plot(_fig, ax) -> None:
        _plot_ground(ax, profile, scenario.search_x_min, scenario.search_x_max, scenario.model_boundary_floor_y)
        _plot_surface_set(ax, shared, color="#7a7a7a", alpha=0.40, linewidth=1.0)
        _plot_surface_set(ax, slide2_only, color="#ca3c25", alpha=0.90, linewidth=1.5)
        _plot_surface_set(ax, ours_only, color="#0b5fff", alpha=0.90, linewidth=1.5)

    _save_plot(
        PLOT_DIR / f"{scenario.output_prefix}_match_and_mismatch_overlay.png",
        (
            f"{scenario.title} Shared and Mismatched Surfaces "
            f"(Shared {len(shared)}, Slide2-only {len(slide2_only)}, Ours-only {len(ours_only)})"
        ),
        _match_and_mismatch_plot,
        x_limits=x_limits,
        y_limits=y_limits,
        legend_handles=[slope_handle, shared_handle, slide2_only_handle, ours_only_handle],
        note_lines=note_lines,
    )

    print(f"{scenario.key}: Slide2 count={len(slide2)} Ours count={len(ours)} Shared={len(shared)} Slide2-only={len(slide2_only)} Ours-only={len(ours_only)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot Slide2 vs current auto-refine surface sets for Case 4 iteration-1 scenarios.")
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        default="case4_iter1_simple",
        help="Which scenario to render.",
    )
    args = parser.parse_args()

    _render_scenario(SCENARIOS[args.scenario])
    print(f"Wrote plots to {PLOT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
