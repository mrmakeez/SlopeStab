"""Shared exceptions for slope stability analysis."""


class InputValidationError(ValueError):
    """Raised when input payloads fail schema or sanity checks."""


class GeometryError(ValueError):
    """Raised when geometry or intersection assumptions are violated."""


class ConvergenceError(RuntimeError):
    """Raised when iterative FOS calculation fails to converge."""


class ParallelExecutionError(RuntimeError):
    """Raised when a parallel worker fails or returns invalid payloads."""
