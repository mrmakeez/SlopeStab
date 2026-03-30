from __future__ import annotations

import errno
import sys
import unittest
from unittest.mock import patch

from tests.path_setup import ensure_src_on_path

ensure_src_on_path()

from slope_stab.cli import _emit_stdout_text, _is_closed_stdout_error


class _ErrnoFailureStream:
    def __init__(self, err: int) -> None:
        self._err = err

    def write(self, text: str) -> int:
        _ = text
        raise OSError(self._err, "write failed")

    def flush(self) -> None:
        return None


class CliOutputContractTests(unittest.TestCase):
    def test_closed_stdout_error_helper_contract(self) -> None:
        self.assertTrue(_is_closed_stdout_error(BrokenPipeError(errno.EPIPE, "broken pipe")))
        self.assertTrue(_is_closed_stdout_error(OSError(errno.EPIPE, "broken pipe")))
        self.assertTrue(_is_closed_stdout_error(OSError(errno.EINVAL, "invalid argument")))
        self.assertTrue(_is_closed_stdout_error(OSError(errno.EBADF, "bad file descriptor")))
        self.assertFalse(_is_closed_stdout_error(OSError(errno.EIO, "io error")))

    def test_emit_stdout_returns_false_for_closed_stream(self) -> None:
        broken_stream = _ErrnoFailureStream(errno.EINVAL)
        with patch.object(sys, "stdout", broken_stream):
            emitted = _emit_stdout_text("payload")
            self.assertFalse(emitted)
            self.assertIsNot(sys.stdout, broken_stream)
            sys.stdout.close()

    def test_emit_stdout_reraises_non_pipe_oserror(self) -> None:
        io_failure_stream = _ErrnoFailureStream(errno.EIO)
        with patch.object(sys, "stdout", io_failure_stream):
            with self.assertRaises(OSError):
                _emit_stdout_text("payload")


if __name__ == "__main__":
    unittest.main()
