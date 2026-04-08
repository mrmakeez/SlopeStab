from __future__ import annotations

import unittest

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.errors.contracts import (
    ERROR_CODE_DISCOVERY_IMPORT,
    ERROR_CODE_DISCOVERY_UNEXPECTED,
    ERROR_CODE_RUNTIME_WORKER,
    ERROR_CODE_STARTUP_BACKEND,
    ERROR_CODE_VALIDATION,
    STAGE_DISCOVERY,
    STAGE_RUNTIME,
    STAGE_STARTUP,
    STAGE_VALIDATION,
    error_payload,
)


class ErrorContractsTests(unittest.TestCase):
    def test_error_payload_shape_and_known_codes(self) -> None:
        pairs = [
            (ERROR_CODE_DISCOVERY_IMPORT, STAGE_DISCOVERY),
            (ERROR_CODE_DISCOVERY_UNEXPECTED, STAGE_DISCOVERY),
            (ERROR_CODE_STARTUP_BACKEND, STAGE_STARTUP),
            (ERROR_CODE_RUNTIME_WORKER, STAGE_RUNTIME),
            (ERROR_CODE_VALIDATION, STAGE_VALIDATION),
        ]
        for code, stage in pairs:
            payload = error_payload(code=code, message="message", stage=stage)
            self.assertEqual(payload, {"code": code, "message": "message", "stage": stage})

    def test_rejects_unknown_code(self) -> None:
        with self.assertRaises(ValueError):
            error_payload(code="unknown_code", message="message", stage=STAGE_VALIDATION)

    def test_rejects_unknown_stage(self) -> None:
        with self.assertRaises(ValueError):
            error_payload(code=ERROR_CODE_VALIDATION, message="message", stage="unknown")


if __name__ == "__main__":
    unittest.main()
