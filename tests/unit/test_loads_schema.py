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
        "material": {"gamma": 20.0, "c": 20.0, "phi_deg": 20.0},
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

    def test_parse_rejects_active_seismic_in_v1(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"seismic": {"model": "pseudo_static"}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)

    def test_parse_rejects_active_groundwater_in_v1(self) -> None:
        payload = _base_payload()
        payload["loads"] = {"groundwater": {"model": "ru"}}
        with self.assertRaises(InputValidationError):
            parse_project_input(payload)


if __name__ == "__main__":
    unittest.main()
