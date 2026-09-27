from __future__ import annotations

from .aliases import alias_entries
from .config import Settings
from .history import load_history
from .hosts_file import discover_hosts_file
from .known_hosts import discover_known_hosts
from .models import HostEntry
from .ssh_config import discover_ssh_config
from .utils import valid_target


def discover(settings: Settings) -> tuple[list[HostEntry], list[str]]:
    errors: list[str] = []
    entries: list[HostEntry] = []
    try:
        entries.extend(alias_entries(settings.data_dir / "aliases.json"))
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"Invalid aliases.json: {exc}")
    entries.extend(discover_ssh_config(settings.ssh_config, errors))
    entries.extend(discover_hosts_file(settings.custom_hosts, "customhosts", errors))
    if settings.read_etc_hosts:
        entries.extend(discover_hosts_file(settings.etc_hosts, "hosts", errors))
    if settings.read_known_hosts:
        entries.extend(discover_known_hosts(settings.known_hosts, errors))
    seen = set()
    unique = []
    for entry in entries:
        # An alias keeps its own row when the alias name differs from its target.
        if entry.name in seen:
            continue
        seen.add(entry.name)
        unique.append(entry)
    if settings.enable_history:
        try:
            history = load_history(settings.data_dir / "history.json")
            known_targets = {entry.target for entry in unique}
            for target in history:
                if target not in known_targets and target not in seen and valid_target(target):
                    unique.append(HostEntry(name=target, target=target, source="history"))
                    seen.add(target)
            for entry in unique:
                data = history.get(entry.target, {})
                if isinstance(data, dict):
                    entry.last_used = data.get("last_used")
                    entry.usage_count = int(data.get("usage_count", 0))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"Invalid history.json: {exc}")
    return unique, errors
