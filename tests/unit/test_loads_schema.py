from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.exceptions import InputValidationError
from slope_stab.io.json_io import parse_project_input


def _base_payload() -> dict:
    return {
        "units": "metric",
        "geometry": {"h": 7.5, "l": 15.0, "x_toe": 10.0, "y_toe": 10.0},
        "soils": {
            "materials": [{"id": "soil_1", "gamma": 20.0, "c": 20.0, "phi_deg": 20.0}],
            "external_boundary": [[-1000.0, -1000.0], [1000.0, -1000.0], [1000.0, 1000.0], [-1000.0, 1000.0]],
            "material_boundaries": [],
            "region_assignments": [{"material_id": "soil_1", "seed_x": 0.0, "seed_y": 0.0}],
        },
        "analysis": {
            "method": "bishop_simplified",
            "n_slices": 7,
            "tolerance": 0.005,
            "max_iter": 50,
            "f_init": 1.0,
        },
        "prescribed_surface": {
            "xc": 13.689,
            "yc": 25.558,
            "r": 15.989,
            "x_left": 10.0005216402222,
            "y_left": 10.0002608201111,
            "x_right": 27.4990237870903,
            "y_right": 17.5,
        },
    }


class LoadsSchemaTests(unittest.TestCase):
    def test_parse_without_loads_preserves_backward_compatibility(self) -> None:
        project = parse_project_input(_base_payload())
        self.assertIsNone(project.loads)

    def test_parse_uniform_surcharge_crest_infinite(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "uniform_surcharge": {
                "magnitude_kpa": 10.0,
                "placement": "crest_infinite",
            },
            "seismic": {"model": "none"},
            "groundwater": {"model": "none"},
        }
        project = parse_project_input(payload)
        self.assertIsNotNone(project.loads)
        assert project.loads is not None
        self.assertIsNotNone(project.loads.uniform_surcharge)
        assert project.loads.uniform_surcharge is not None
        self.assertEqual(project.loads.uniform_surcharge.placement, "crest_infinite")
        self.assertEqual(project.loads.uniform_surcharge.magnitude_kpa, 10.0)
        self.assertIsNone(project.loads.uniform_surcharge.x_start)
        self.assertIsNone(project.loads.uniform_surcharge.x_end)

    def test_parse_uniform_surcharge_crest_range(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "uniform_surcharge": {
                "magnitude_kpa": 12.5,
                "placement": "crest_range",
                "x_start": 25.0,
                "x_end": 27.5,
            }
        }
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.uniform_surcharge is not None
        self.assertEqual(project.loads.uniform_surcharge.placement, "crest_range")
        self.assertEqual(project.loads.uniform_surcharge.x_start, 25.0)
        self.assertEqual(project.loads.uniform_surcharge.x_end, 27.5)

    def test_parse_rejects_crest_range_below_crest(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "uniform_surcharge": {
                "magnitude_kpa": 8.0,
                "placement": "crest_range",
                "x_start": 24.0,
                "x_end": 28.0,
            }
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_accepts_pseudo_static_seismic_with_zero_kv(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static", "kh": 0.132, "kv": 0.0}}
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.seismic is not None
        self.assertEqual(project.loads.seismic.model, "pseudo_static")
        self.assertAlmostEqual(project.loads.seismic.kh, 0.132)
        self.assertAlmostEqual(project.loads.seismic.kv, 0.0)

    def test_parse_accepts_pseudo_static_seismic_without_kv(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static", "kh": 0.25}}
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.seismic is not None
        self.assertAlmostEqual(project.loads.seismic.kv, 0.0)

    def test_parse_rejects_pseudo_static_seismic_without_kh(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static"}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_nonzero_kv_in_v1(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static", "kh": 0.132, "kv": 0.05}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_kh_out_of_range(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static", "kh": 1.2}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_groundwater_water_surfaces_custom(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "groundwater": {
                "model": "water_surfaces",
                "surface": [[0.0, 15.0], [18.0, 15.0], [30.0, 23.0], [48.0, 29.0], [66.0, 32.0]],
                "hu": {"mode": "custom", "value": 1.0},
                "gamma_w": 9.81,
            }
        }
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.groundwater is not None
        self.assertEqual(project.loads.groundwater.model, "water_surfaces")
        self.assertEqual(project.loads.groundwater.hu.mode, "custom")
        self.assertEqual(project.loads.groundwater.hu.value, 1.0)
        self.assertEqual(len(project.loads.groundwater.surface), 5)

    def test_parse_groundwater_water_surfaces_auto(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "groundwater": {
                "model": "water_surfaces",
                "surface": [[0.0, 15.0], [18.0, 15.0], [30.0, 23.0], [48.0, 29.0], [66.0, 32.0]],
                "hu": {"mode": "auto"},
            }
        }
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.groundwater is not None
        self.assertEqual(project.loads.groundwater.model, "water_surfaces")
        self.assertEqual(project.loads.groundwater.hu.mode, "auto")
        self.assertIsNone(project.loads.groundwater.hu.value)
        self.assertEqual(project.loads.groundwater.gamma_w, 9.81)

    def test_parse_groundwater_ru_coefficient(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"groundwater": {"model": "ru_coefficient", "ru": 0.5}}
        project = parse_project_input(payload)
        assert project.loads is not None
        assert project.loads.groundwater is not None
        self.assertEqual(project.loads.groundwater.model, "ru_coefficient")
        self.assertEqual(project.loads.groundwater.ru, 0.5)

    def test_parse_rejects_water_surface_non_increasing_x(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "groundwater": {
                "model": "water_surfaces",
                "surface": [[0.0, 15.0], [18.0, 15.0], [18.0, 23.0]],
                "hu": {"mode": "custom", "value": 1.0},
            }
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_hu_custom_without_value(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "groundwater": {
                "model": "water_surfaces",
                "surface": [[0.0, 15.0], [18.0, 15.0]],
                "hu": {"mode": "custom"},
            }
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_hu_auto_with_value(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "groundwater": {
                "model": "water_surfaces",
                "surface": [[0.0, 15.0], [18.0, 15.0]],
                "hu": {"mode": "auto", "value": 0.9},
            }
        }
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_ru_out_of_range(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"groundwater": {"model": "ru_coefficient", "ru": 1.1}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)


if __name__ == "__main__":
    unittest.main()
