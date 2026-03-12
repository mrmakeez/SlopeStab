from __future__ import annotations

import pathlib
import sys


def ensure_src_on_path() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
