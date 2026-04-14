from __future__ import annotations

import math
import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.analysis import run_analysis
from slope_stab.exceptions import InputValidationError
from slope_stab.geometry.profile import UniformSlopeProfile
from slope_stab.io.json_io import parse_project_input
from slope_stab.models import AutoRefineSearchInput, PrescribedCircleInput, SearchLimitsInput
from slope_stab.search.auto_refine import (
    _build_ground_polyline,
    _build_next_retained_path,
    _clip_construction_circle_to_ground_intercepts,
    _close_small_retained_index_gaps,
    _division_boundaries_and_midpoints_for_retained_path,
    _division_boundaries_and_midpoints,
    _generate_pre_polish_pair_candidates,
    _generate_slide2_betas,
    _pad_retained_index_runs,
    _surface_has_reverse_curvature,
    RetainedPathSegment,
)


def _base_payload() -> dict:
    return {
        "units": "metric",
        "geometry": {"h": 10.0, "l": 20.0, "x_toe": 30.0, "y_toe": 25.0},
        "soils": {
            "materials": [{"id": "soil_1", "gamma": 20.0, "c": 3.0, "phi_deg": 19.6}],
            "external_boundary": [[-1000.0, -1000.0], [1000.0, -1000.0], [1000.0, 1000.0], [-1000.0, 1000.0]],
            "material_boundaries": [],
            "region_assignments": [{"material_id": "soil_1", "seed_x": 0.0, "seed_y": 0.0}],
        },
        "analysis": {
            "method": "bishop_simplified",
            "n_slices": 25,
            "tolerance": 0.0001,
            "max_iter": 100,
            "f_init": 1.0,
        },
    }


class SearchInputParsingTests(unittest.TestCase):
    def test_parse_accepts_spencer_method(self) -> None:
        payload = _base_payload()
        payload["analysis"]["method"] = "spencer"
        payload["prescribed_surface"] = {
            "xc": 13.689,
            "yc": 25.558,
            "r": 15.989,
            "x_left": 10.0005216402222,
            "y_left": 10.0002608201111,
            "x_right": 27.4990237870903,
            "y_right": 17.5,
        }

        project = parse_project_input(payload)
        self.assertEqual(project.analysis.method, "spencer")

    def test_search_limits_default_from_geometry(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        limits = project.search.auto_refine_circular.search_limits
        self.assertAlmostEqual(limits.x_min, 20.0)
        self.assertAlmostEqual(limits.x_max, 70.0)

    def test_parse_auto_refine_model_boundary_floor_y(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
                "model_boundary_floor_y": 22.5,
            },
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        assert project.search.auto_refine_circular is not None
        self.assertAlmostEqual(project.search.auto_refine_circular.model_boundary_floor_y, 22.5)

    def test_parse_rejects_missing_mode(self) -> None:
        payload = _base_payload()
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_both_modes(self) -> None:
        payload = _base_payload()
        payload["prescribed_surface"] = {
            "xc": 29.07,
            "yc": 55.495,
            "r": 30.4956368485163,
            "x_left": 30.02888427029,
            "y_left": 25.014442135145,
            "x_right": 51.6518254752929,
            "y_right": 35.0,
        }
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_direct_global_mode(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "direct_global_circular": {
                "max_iterations": 40,
                "max_evaluations": 500,
                "min_improvement": 1e-4,
                "stall_iterations": 8,
                "min_rectangle_half_size": 1e-3,
            },
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "direct_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNotNone(project.search.direct_global_circular)
        self.assertEqual(project.search.direct_global_circular.max_iterations, 40)
        self.assertEqual(project.search.direct_global_circular.max_evaluations, 500)
        self.assertEqual(project.search.direct_global_circular.stall_iterations, 8)
        limits = project.search.direct_global_circular.search_limits
        self.assertAlmostEqual(limits.x_min, 20.0)
        self.assertAlmostEqual(limits.x_max, 70.0)

    def test_parse_rejects_missing_direct_global_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }

        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_direct_global_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "direct_global_circular",
            "direct_global_circular": {
                "max_iterations": 0,
                "max_evaluations": 100,
                "min_improvement": -1e-4,
                "stall_iterations": 0,
                "min_rectangle_half_size": 0.0,
            },
        }

        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_cuckoo_global_mode_defaults(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
            "cuckoo_global_circular": {},
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "cuckoo_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNone(project.search.direct_global_circular)
        self.assertIsNotNone(project.search.cuckoo_global_circular)

        cfg = project.search.cuckoo_global_circular
        self.assertEqual(cfg.population_size, 40)
        self.assertEqual(cfg.max_iterations, 300)
        self.assertEqual(cfg.max_evaluations, 7000)
        self.assertAlmostEqual(cfg.discovery_rate, 0.25)
        self.assertAlmostEqual(cfg.levy_beta, 1.5)
        self.assertAlmostEqual(cfg.alpha_max, 0.5)
        self.assertAlmostEqual(cfg.alpha_min, 0.05)
        self.assertAlmostEqual(cfg.min_improvement, 1e-4)
        self.assertEqual(cfg.stall_iterations, 25)
        self.assertEqual(cfg.seed, 0)
        self.assertTrue(cfg.post_polish)
        self.assertAlmostEqual(cfg.search_limits.x_min, 20.0)
        self.assertAlmostEqual(cfg.search_limits.x_max, 70.0)

    def test_parse_rejects_missing_cuckoo_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_cuckoo_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cuckoo_global_circular",
            "cuckoo_global_circular": {
                "population_size": 1,
                "max_iterations": 0,
                "max_evaluations": 0,
                "discovery_rate": 1.0,
                "levy_beta": 2.1,
                "alpha_max": 0.0,
                "alpha_min": 0.0,
                "min_improvement": -1.0,
                "stall_iterations": 0,
                "seed": 0,
                "post_polish": True,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_cmaes_global_mode_defaults(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
            "cmaes_global_circular": {},
        }

        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertEqual(project.search.method, "cmaes_global_circular")
        self.assertIsNone(project.search.auto_refine_circular)
        self.assertIsNone(project.search.direct_global_circular)
        self.assertIsNone(project.search.cuckoo_global_circular)
        self.assertIsNotNone(project.search.cmaes_global_circular)

        cfg = project.search.cmaes_global_circular
        self.assertEqual(cfg.max_evaluations, 5000)
        self.assertEqual(cfg.direct_prescan_evaluations, 300)
        self.assertEqual(cfg.cmaes_population_size, 8)
        self.assertEqual(cfg.cmaes_max_iterations, 200)
        self.assertEqual(cfg.cmaes_restarts, 2)
        self.assertAlmostEqual(cfg.cmaes_sigma0, 0.15)
        self.assertEqual(cfg.polish_max_evaluations, 80)
        self.assertAlmostEqual(cfg.min_improvement, 1e-4)
        self.assertEqual(cfg.stall_iterations, 25)
        self.assertEqual(cfg.seed, 1)
        self.assertTrue(cfg.post_polish)
        self.assertAlmostEqual(cfg.invalid_penalty, 1e6)
        self.assertAlmostEqual(cfg.nonconverged_penalty, 1e5)
        self.assertAlmostEqual(cfg.search_limits.x_min, 20.0)
        self.assertAlmostEqual(cfg.search_limits.x_max, 70.0)

    def test_parse_rejects_missing_cmaes_payload(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_invalid_cmaes_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "cmaes_global_circular",
            "cmaes_global_circular": {
                "max_evaluations": 10,
                "direct_prescan_evaluations": 10,
                "cmaes_population_size": 1,
                "cmaes_max_iterations": 0,
                "cmaes_restarts": -1,
                "cmaes_sigma0": 0.0,
                "polish_max_evaluations": 0,
                "min_improvement": -1.0,
                "stall_iterations": 0,
                "seed": 0,
                "post_polish": True,
                "invalid_penalty": 1e4,
                "nonconverged_penalty": 1e5
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_parallel_defaults(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "auto")
        self.assertEqual(project.search.parallel.workers, 0)
        self.assertEqual(project.search.parallel.min_batch_size, 1)
        self.assertIsNone(project.search.parallel.timeout_seconds)

    def test_parse_parallel_custom_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "parallel",
                "workers": 2,
                "min_batch_size": 8,
                "timeout_seconds": 30.0,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.search)
        self.assertIsNotNone(project.search.parallel)
        self.assertEqual(project.search.parallel.mode, "parallel")
        self.assertEqual(project.search.parallel.workers, 2)
        self.assertEqual(project.search.parallel.min_batch_size, 8)
        self.assertAlmostEqual(project.search.parallel.timeout_seconds, 30.0)

    def test_parse_rejects_invalid_parallel_values(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "parallel",
                "workers": -1,
                "min_batch_size": 0,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_legacy_parallel_enabled_mapping(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": True,
                "workers": 3,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(
            str(ctx.exception),
            "search.parallel.enabled is no longer supported; use search.parallel.mode.",
        )

    def test_parse_rejects_legacy_parallel_enabled_false_mapping(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": False,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(
            str(ctx.exception),
            "search.parallel.enabled is no longer supported; use search.parallel.mode.",
        )

    def test_parse_rejects_parallel_enabled_mode_conflict(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "enabled": False,
                "mode": "parallel",
                "workers": 2,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(
            str(ctx.exception),
            "search.parallel.enabled is no longer supported; use search.parallel.mode.",
        )

    def test_parse_rejects_invalid_parallel_mode(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "parallel": {
                "mode": "turbo",
                "workers": 2,
            },
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)


class AutoRefineSearchTests(unittest.TestCase):
    def test_retained_path_sampling_excludes_discarded_gaps(self) -> None:
        retained_path = [
            RetainedPathSegment(start=(0.0, 0.0), end=(2.0, 0.0)),
            RetainedPathSegment(start=(8.0, 0.0), end=(10.0, 0.0)),
        ]

        boundaries, midpoints = _division_boundaries_and_midpoints_for_retained_path(retained_path, divisions=4)

        self.assertEqual(boundaries, [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (9.0, 0.0), (10.0, 0.0)])
        self.assertEqual(midpoints, [(0.5, 0.0), (1.5, 0.0), (8.5, 0.0), (9.5, 0.0)])

    def test_build_next_retained_path_preserves_noncontiguous_kept_intervals(self) -> None:
        retained_path = [RetainedPathSegment(start=(0.0, 0.0), end=(10.0, 0.0))]

        next_path = _build_next_retained_path(
            retained_path,
            divisions=10,
            retained_indices=[1, 2, 7],
        )

        self.assertEqual(
            next_path,
            [
                RetainedPathSegment(start=(1.0, 0.0), end=(3.0, 0.0)),
                RetainedPathSegment(start=(7.0, 0.0), end=(8.0, 0.0)),
            ],
        )

    def test_close_small_retained_index_gaps_fills_isolated_holes_only(self) -> None:
        self.assertEqual(
            _close_small_retained_index_gaps([4, 6, 7, 8, 9, 10, 11, 12, 13, 15]),
            list(range(4, 16)),
        )
        self.assertEqual(
            _close_small_retained_index_gaps([2, 3, 4, 10, 11]),
            [2, 3, 4, 10, 11],
        )

    def test_pad_retained_index_runs_expands_each_contiguous_run_by_one_neighbor(self) -> None:
        self.assertEqual(
            _pad_retained_index_runs([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], divisions=20),
            list(range(3, 17)),
        )
        self.assertEqual(
            _pad_retained_index_runs([0, 1, 2, 8, 9], divisions=10),
            [0, 1, 2, 3, 7, 8, 9],
        )

    def test_slide2_beta_schedule_is_linear_and_hits_upper_bound(self) -> None:
        theta_chord = math.radians(26.565051177078)
        count = 10
        betas = _generate_slide2_betas(theta_chord, count)

        self.assertEqual(len(betas), count)
        beta_max = 0.5 * math.pi - theta_chord
        for m, beta in enumerate(betas, start=1):
            self.assertAlmostEqual(beta, (m / count) * beta_max, places=12)
        self.assertAlmostEqual(betas[-1], beta_max, places=12)

    def test_pre_polish_pair_candidates_preserve_construction_radius_schedule(self) -> None:
        profile = UniformSlopeProfile(h=7.5, l=15.0, x_toe=10.0, y_toe=10.0)
        config = AutoRefineSearchInput(
            divisions_along_slope=20,
            circles_per_division=10,
            iterations=10,
            divisions_to_use_next_iteration_pct=50.0,
            search_limits=SearchLimitsInput(x_min=0.0, x_max=35.0),
        )
        polyline = _build_ground_polyline(profile, config.search_limits.x_min, config.search_limits.x_max)
        _, midpoints = _division_boundaries_and_midpoints(polyline, config.divisions_along_slope)
        i = 5
        j = 8
        p_left = midpoints[i]
        p_right = midpoints[j]

        candidates = _generate_pre_polish_pair_candidates(
            profile=profile,
            search_x_min=config.search_limits.x_min,
            search_x_max=config.search_limits.x_max,
            p_left=p_left,
            p_right=p_right,
            circles_per_division=config.circles_per_division,
        )
        self.assertEqual(len(candidates), config.circles_per_division)

        self.assertTrue(any(candidate is not None for candidate in candidates))
        for candidate in candidates:
            if candidate is None:
                continue
            self.assertGreaterEqual(candidate.x_left, config.search_limits.x_min)
            self.assertLessEqual(candidate.x_right, config.search_limits.x_max)
            self.assertLess(candidate.x_left, candidate.x_right)

        theta_chord = math.atan2(p_right[1] - p_left[1], p_right[0] - p_left[0])
        beta_max = 0.5 * math.pi - theta_chord
        chord = math.hypot(p_right[0] - p_left[0], p_right[1] - p_left[1])
        inferred_betas: list[float] = []
        for candidate in candidates:
            if candidate is None:
                continue
            ratio = chord / (2.0 * candidate.r)
            inferred_betas.append(math.asin(max(-1.0, min(1.0, ratio))))

        self.assertGreaterEqual(len(inferred_betas), 2)
        self.assertLessEqual(inferred_betas[-1], beta_max + 1e-12)
        for idx in range(1, len(inferred_betas)):
            self.assertAlmostEqual(
                inferred_betas[idx] - inferred_betas[idx - 1],
                inferred_betas[1] - inferred_betas[0],
                places=12,
            )

    def test_clip_construction_circle_to_ground_intercepts_matches_slide2_simple_case(self) -> None:
        profile = UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
        construction_surface = PrescribedCircleInput(
            xc=14.2649653082946,
            yc=162.316692757048,
            r=137.405400540889,
            x_left=19.2015621187164,
            y_left=25.0,
            x_right=85.7984378812836,
            y_right=45.0,
        )

        clipped = _clip_construction_circle_to_ground_intercepts(
            profile=profile,
            construction_surface=construction_surface,
            search_x_min=10.0,
            search_x_max=95.0,
            construction_mid_x=0.5 * (construction_surface.x_left + construction_surface.x_right),
        )

        self.assertIsNotNone(clipped)
        assert clipped is not None
        self.assertAlmostEqual(clipped.x_left, 31.1983666156608, places=6)
        self.assertAlmostEqual(clipped.y_left, 25.9586932925286, places=6)
        self.assertAlmostEqual(clipped.x_right, 85.7984378812835, places=6)
        self.assertAlmostEqual(clipped.y_right, 45.0, places=6)
        self.assertAlmostEqual(clipped.r, construction_surface.r, places=9)

    def test_clip_construction_circle_to_ground_intercepts_snaps_near_toe_boundary(self) -> None:
        profile = UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
        construction_surface = PrescribedCircleInput(
            xc=29.8233038746688,
            yc=57.3559704881194,
            r=32.3561683051798,
            x_left=29.9367179238856,
            y_left=25.0,
            x_right=59.7273452115870,
            y_right=45.0,
        )

        clipped = _clip_construction_circle_to_ground_intercepts(
            profile=profile,
            construction_surface=construction_surface,
            search_x_min=10.0,
            search_x_max=95.0,
            construction_mid_x=0.5 * (construction_surface.x_left + construction_surface.x_right),
            model_boundary_floor_y=20.0,
        )

        self.assertIsNotNone(clipped)
        assert clipped is not None
        self.assertAlmostEqual(clipped.x_left, 30.0, places=6)
        self.assertAlmostEqual(clipped.y_left, 25.0, places=6)
        self.assertAlmostEqual(clipped.x_right, 59.7273452115870, delta=2e-6)
        self.assertAlmostEqual(clipped.y_right, 45.0, places=6)

    def test_pre_polish_pair_candidates_keep_terminal_beta_for_nonflat_pair(self) -> None:
        profile = UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
        p_left = (35.93826238111394, 29.75060990489115)
        p_right = (50.3086880944303, 41.24695047554424)

        candidates = _generate_pre_polish_pair_candidates(
            profile=profile,
            search_x_min=10.0,
            search_x_max=95.0,
            p_left=p_left,
            p_right=p_right,
            circles_per_division=5,
            model_boundary_floor_y=20.0,
        )

        self.assertEqual(len(candidates), 5)
        self.assertIsNotNone(candidates[-1])
        assert candidates[-1] is not None
        self.assertAlmostEqual(candidates[-1].xc, 38.52493900951089, places=6)
        self.assertAlmostEqual(candidates[-1].yc, 41.24695047554424, places=6)
        self.assertAlmostEqual(candidates[-1].r, 11.783749084919418, places=6)
        self.assertAlmostEqual(candidates[-1].x_left, 35.93826238111394, places=6)
        self.assertAlmostEqual(candidates[-1].x_right, 50.3086880944303, places=6)

    def test_pre_polish_pair_candidates_reject_equal_elevation_clipped_surfaces(self) -> None:
        profile = UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
        p_left = (67.39531364385073, 45.0)
        p_right = (85.79843788128358, 45.0)

        candidates = _generate_pre_polish_pair_candidates(
            profile=profile,
            search_x_min=10.0,
            search_x_max=95.0,
            p_left=p_left,
            p_right=p_right,
            circles_per_division=5,
            model_boundary_floor_y=20.0,
        )

        self.assertEqual(candidates, [None, None, None, None, None])

    def test_surface_has_reverse_curvature_flags_endpoint_above_center(self) -> None:
        surface = PrescribedCircleInput(
            xc=10.0,
            yc=20.0,
            r=15.0,
            x_left=0.0,
            y_left=20.0002,
            x_right=20.0,
            y_right=19.0,
        )

        self.assertTrue(_surface_has_reverse_curvature(surface))

    def test_surface_has_reverse_curvature_is_false_for_slide2_style_clipped_surface(self) -> None:
        surface = PrescribedCircleInput(
            xc=14.2649652578779,
            yc=162.316692757048,
            r=137.405400540889,
            x_left=31.1983666156608,
            y_left=25.9586932925286,
            x_right=85.7984378812835,
            y_right=45.0,
        )

        self.assertFalse(_surface_has_reverse_curvature(surface))

    def test_clip_construction_circle_to_ground_intercepts_rejects_surface_below_model_floor(self) -> None:
        profile = UniformSlopeProfile(h=20.0, l=25.0, x_toe=30.0, y_toe=25.0)
        construction_surface = PrescribedCircleInput(
            xc=39.1485223077741,
            yc=45.0,
            r=28.2467913360766,
            x_left=19.2015621187164,
            y_left=25.0,
            x_right=67.3953136438507,
            y_right=45.0,
        )

        clipped = _clip_construction_circle_to_ground_intercepts(
            profile=profile,
            construction_surface=construction_surface,
            search_x_min=10.0,
            search_x_max=95.0,
            construction_mid_x=0.5 * (construction_surface.x_left + construction_surface.x_right),
            model_boundary_floor_y=20.0,
        )

        self.assertIsNone(clipped)

    def test_generated_surfaces_per_iteration_matches_formula(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 3,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)
        result = run_analysis(project)

        search_meta = result.metadata["search"]
        diagnostics = search_meta["iteration_diagnostics"]
        expected_generated = 3 * 6 * (6 - 1) // 2

        self.assertEqual(len(diagnostics), 3)
        for item in diagnostics:
            self.assertEqual(item["generated_surfaces"], expected_generated)

    def test_auto_refine_repeatable_for_same_input(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 6,
                "circles_per_division": 3,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
            },
        }
        project = parse_project_input(payload)

        result1 = run_analysis(project)
        result2 = run_analysis(project)

        self.assertAlmostEqual(result1.fos, result2.fos, places=12)
        self.assertEqual(result1.metadata["prescribed_surface"], result2.metadata["prescribed_surface"])
        self.assertEqual(result1.metadata["search"]["iteration_diagnostics"], result2.metadata["search"]["iteration_diagnostics"])
        self.assertTrue(math.isfinite(result1.fos))

    def test_iteration_diagnostics_expose_gap_closed_expanded_retained_indices(self) -> None:
        payload = _base_payload()
        payload["search"] = {
            "method": "auto_refine_circular",
            "auto_refine_circular": {
                "divisions_along_slope": 20,
                "circles_per_division": 10,
                "iterations": 2,
                "divisions_to_use_next_iteration_pct": 50.0,
                "search_limits": {"x_min": 0.0, "x_max": 35.0},
            },
        }
        payload["geometry"] = {"h": 7.5, "l": 15.0, "x_toe": 10.0, "y_toe": 10.0}
        payload["soils"] = {
            "materials": [{"id": "soil_1", "gamma": 20.0, "c": 20.0, "phi_deg": 20.0}],
            "external_boundary": [[-1000.0, -1000.0], [1000.0, -1000.0], [1000.0, 1000.0], [-1000.0, 1000.0]],
            "material_boundaries": [],
            "region_assignments": [{"material_id": "soil_1", "seed_x": 0.0, "seed_y": 0.0}],
        }
        payload["analysis"] = {
            "method": "bishop_simplified",
            "n_slices": 7,
            "tolerance": 0.001,
            "max_iter": 50,
            "f_init": 1.0,
        }
        project = parse_project_input(payload)

        result = run_analysis(project, forced_parallel_mode="serial", forced_parallel_workers=1)

        diagnostics = result.metadata["search"]["iteration_diagnostics"]
        self.assertEqual(len(diagnostics), 2)
        retained = diagnostics[0]["retained_division_indices"]
        expanded = diagnostics[0]["expanded_retained_division_indices"]
        self.assertEqual(len(retained), 10)
        self.assertTrue(set(retained).issubset(set(expanded)))
        self.assertEqual(expanded, sorted(set(expanded)))
        self.assertGreaterEqual(len(diagnostics[0]["next_active_path_segments"]), 2)


if __name__ == "__main__":
    unittest.main()
