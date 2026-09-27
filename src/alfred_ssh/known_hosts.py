from __future__ import annotations

from pathlib import Path

from .models import HostEntry
from .utils import valid_target


def discover_known_hosts(path: Path, errors: list[str] | None = None) -> list[HostEntry]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    except OSError as exc:
        if errors is not None:
            errors.append(f"Unable to read {path}: {exc.strerror or exc}")
        return []
    entries = []
    for line in lines:
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        if parts[0].startswith("@"):
            parts = parts[1:]
        if len(parts) < 3:
            continue
        for name in parts[0].split(","):
            if name.startswith("|") or name.startswith("[") or not valid_target(name):
                continue
            entries.append(HostEntry(name=name, target=name, source="knownhosts", source_path=str(path)))
    return entries
