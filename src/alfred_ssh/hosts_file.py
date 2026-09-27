from __future__ import annotations

import ipaddress
from pathlib import Path

from .models import HostEntry
from .utils import valid_target

LOCAL_NAMES = {"localhost", "localhost.localdomain", "broadcasthost", "ip6-localhost", "ip6-loopback"}


def discover_hosts_file(path: Path, source: str, errors: list[str] | None = None) -> list[HostEntry]:
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
        parts = line.partition("#")[0].split()
        if len(parts) < 2:
            continue
        try:
            address = ipaddress.ip_address(parts[0])
        except ValueError:
            continue
        for name in parts[1:]:
            if name.lower() in LOCAL_NAMES or (address.is_loopback and source == "hosts"):
                continue
            if valid_target(name):
                entries.append(HostEntry(name=name, target=name, hostname=str(address), source=source, source_path=str(path)))
    return entries
