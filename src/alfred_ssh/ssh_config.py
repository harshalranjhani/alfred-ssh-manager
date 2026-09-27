"""Discover literal Host declarations; OpenSSH remains the config resolver."""

from __future__ import annotations

import glob
import os
import shlex
from pathlib import Path

from .models import HostEntry
from .utils import valid_target


def _tokens(line: str) -> list[str]:
    try:
        return shlex.split(line, comments=True, posix=True)
    except ValueError:
        return []


def discover_ssh_config(path: Path, errors: list[str] | None = None) -> list[HostEntry]:
    errors = errors if errors is not None else []
    entries: list[HostEntry] = []
    seen: set[Path] = set()

    def visit(file: Path) -> None:
        real = file.expanduser().resolve()
        if real in seen:
            return
        seen.add(real)
        try:
            lines = real.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            return
        except OSError as exc:
            errors.append(f"Unable to read {file}: {exc.strerror or exc}")
            return
        active: list[HostEntry] = []
        in_match = False
        for line in lines:
            parts = _tokens(line)
            if not parts:
                continue
            # OpenSSH permits both `Key value` and `Key=value`.
            if "=" in parts[0]:
                key, first = parts[0].split("=", 1)
                parts = [key, first, *parts[1:]]
            key, values = parts[0].lower(), parts[1:]
            if values and values[0] == "=":
                values = values[1:]
            if key == "include":
                for pattern in values:
                    expanded = os.path.expandvars(os.path.expanduser(pattern))
                    if not os.path.isabs(expanded):
                        expanded = str(real.parent / expanded)
                    for included in sorted(glob.glob(expanded)):
                        visit(Path(included))
            elif key == "match":
                active = []
                in_match = True
            elif key == "host":
                in_match = False
                active = []
                for name in values:
                    if valid_target(name) and not any(c in name for c in "*?!"):
                        entry = HostEntry(name=name, target=name, source="sshconfig", source_path=str(real))
                        entries.append(entry)
                        active.append(entry)
            elif not in_match and active and values:
                for entry in active:
                    if key == "hostname" and entry.hostname is None:
                        entry.hostname = values[0]
                    elif key == "user" and entry.user is None:
                        entry.user = values[0]
                    elif key == "port" and entry.port is None:
                        try:
                            entry.port = int(values[0])
                        except ValueError:
                            pass

    visit(path)
    return entries
