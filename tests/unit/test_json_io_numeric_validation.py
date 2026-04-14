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


class JsonIoNumericValidationTests(unittest.TestCase):
    def test_rejects_bool_for_integer_field(self) -> None:
        payload = _base_payload()
        payload["analysis"]["n_slices"] = True

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.n_slices' must be an integer.")

    def test_rejects_overflow_for_integer_field_with_validation_error(self) -> None:
        payload = _base_payload()
        payload["analysis"]["n_slices"] = float("inf")

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.n_slices' must be an integer.")

    def test_rejects_nonfinite_string_nan_for_float_field(self) -> None:
        payload = _base_payload()
        payload["analysis"]["tolerance"] = "nan"

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.tolerance' must be finite numeric.")

    def test_rejects_nonfinite_string_inf_for_float_field(self) -> None:
        payload = _base_payload()
        payload["analysis"]["tolerance"] = "inf"

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.tolerance' must be finite numeric.")

    def test_rejects_nonfinite_positive_inf_float_for_float_field(self) -> None:
        payload = _base_payload()
        payload["analysis"]["tolerance"] = float("inf")

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.tolerance' must be finite numeric.")

    def test_rejects_nonfinite_negative_inf_float_for_float_field(self) -> None:
        payload = _base_payload()
        payload["analysis"]["tolerance"] = float("-inf")

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.tolerance' must be finite numeric.")

    def test_rejects_bool_for_nested_float_field(self) -> None:
        payload = _base_payload()
        payload["loads"] = {
            "uniform_surcharge": {
                "magnitude_kpa": False,
                "placement": "crest_infinite",
            }
        }

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(
            str(ctx.exception),
            "Key 'loads.uniform_surcharge.magnitude_kpa' must be numeric.",
        )

    def test_accepts_valid_integer_and_float_values(self) -> None:
        payload = _base_payload()
        payload["analysis"]["n_slices"] = 25
        payload["analysis"]["tolerance"] = 1e-4

        project = parse_project_input(payload)
        self.assertEqual(project.analysis.n_slices, 25)
        self.assertAlmostEqual(project.analysis.tolerance, 1e-4)

    def test_accepts_finite_float_numeric_string(self) -> None:
        payload = _base_payload()
        payload["analysis"]["tolerance"] = "0.005"

        project = parse_project_input(payload)
        self.assertAlmostEqual(project.analysis.tolerance, 0.005)

    def test_preserves_integer_string_compatibility(self) -> None:
        payload = _base_payload()
        payload["analysis"]["n_slices"] = "3"

        project = parse_project_input(payload)
        self.assertEqual(project.analysis.n_slices, 3)

    def test_rejects_decimal_like_integer_string(self) -> None:
        payload = _base_payload()
        payload["analysis"]["n_slices"] = "3.0"

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "Key 'analysis.n_slices' must be an integer.")

    def test_accepts_phi_deg_at_lower_bound(self) -> None:
        payload = _base_payload()
        payload["soils"]["materials"][0]["phi_deg"] = 0.0

        project = parse_project_input(payload)
        self.assertAlmostEqual(project.soils.materials[0].phi_deg, 0.0)

    def test_accepts_phi_deg_just_below_upper_bound(self) -> None:
        payload = _base_payload()
        payload["soils"]["materials"][0]["phi_deg"] = 89.999

        project = parse_project_input(payload)
        self.assertAlmostEqual(project.soils.materials[0].phi_deg, 89.999)

    def test_rejects_negative_phi_deg(self) -> None:
        payload = _base_payload()
        payload["soils"]["materials"][0]["phi_deg"] = -1.0

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "soils.materials[soil_1].phi_deg must be in [0, 90).")

    def test_rejects_phi_deg_at_upper_bound(self) -> None:
        payload = _base_payload()
        payload["soils"]["materials"][0]["phi_deg"] = 90.0

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "soils.materials[soil_1].phi_deg must be in [0, 90).")

    def test_rejects_phi_deg_above_upper_bound(self) -> None:
        payload = _base_payload()
        payload["soils"]["materials"][0]["phi_deg"] = 95.0

        with self.assertRaises(InputValidationError) as ctx:
            parse_project_input(payload)
        self.assertEqual(str(ctx.exception), "soils.materials[soil_1].phi_deg must be in [0, 90).")


if __name__ == "__main__":
    unittest.main()
