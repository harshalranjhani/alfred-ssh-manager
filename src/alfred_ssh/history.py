from __future__ import annotations

import time
from pathlib import Path

from .utils import read_json, write_json


def load_history(path: Path) -> dict:
    return read_json(path)


def record(path: Path, target: str) -> None:
    data = load_history(path)
    old = data.get(target, {})
    data[target] = {"last_used": time.time(), "usage_count": int(old.get("usage_count", 0)) + 1}
    write_json(path, data)
