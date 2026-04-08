from __future__ import annotations

from typing import Final


STAGE_DISCOVERY: Final[str] = "discovery"
STAGE_STARTUP: Final[str] = "startup"
STAGE_RUNTIME: Final[str] = "runtime"
STAGE_VALIDATION: Final[str] = "validation"

ERROR_CODE_DISCOVERY_IMPORT: Final[str] = "discovery_import_error"
ERROR_CODE_DISCOVERY_UNEXPECTED: Final[str] = "discovery_unexpected_error"
ERROR_CODE_STARTUP_BACKEND: Final[str] = "startup_backend_error"
ERROR_CODE_RUNTIME_WORKER: Final[str] = "runtime_worker_error"
ERROR_CODE_VALIDATION: Final[str] = "validation_error"

_ALLOWED_STAGES: Final[set[str]] = {
    STAGE_DISCOVERY,
    STAGE_STARTUP,
    STAGE_RUNTIME,
    STAGE_VALIDATION,
}
_ALLOWED_CODES: Final[set[str]] = {
    ERROR_CODE_DISCOVERY_IMPORT,
    ERROR_CODE_DISCOVERY_UNEXPECTED,
    ERROR_CODE_STARTUP_BACKEND,
    ERROR_CODE_RUNTIME_WORKER,
    ERROR_CODE_VALIDATION,
}


def error_payload(*, code: str, message: str, stage: str) -> dict[str, str]:
    if code not in _ALLOWED_CODES:
        raise ValueError(f"Unsupported error code: {code!r}")
    if stage not in _ALLOWED_STAGES:
        raise ValueError(f"Unsupported error stage: {stage!r}")
    return {
        "code": code,
        "message": message,
        "stage": stage,
    }
