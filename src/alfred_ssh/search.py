from __future__ import annotations

import shlex
from pathlib import Path

from .config import Settings
from .models import HostEntry
from .utils import valid_target

SOURCE_ORDER = {"alias": 0, "sshconfig": 1, "customhosts": 2, "hosts": 3, "knownhosts": 4, "history": 5, "direct": 6}


def searchable_text(entry: HostEntry) -> str:
    return " ".join(str(value) for value in [entry.name, entry.target, entry.hostname or "", entry.user or "", entry.description or "", *entry.tags, entry.source] if value)


def _matches(query: str, entry: HostEntry) -> bool:
    haystack = searchable_text(entry).lower()
    words = haystack.replace("-", " ").replace("_", " ").replace(".", " ").split()
    return all(any(token in word or _subsequence(token, word) for word in words) for token in query.lower().split())


def _subsequence(needle: str, word: str) -> bool:
    if len(needle) < 3:
        return False
    letters = iter(word)
    return all(char in letters for char in needle)


def select(entries: list[HostEntry], query: str) -> list[HostEntry]:
    query = query.strip()
    if query == ":recent":
        return sorted((e for e in entries if e.last_used), key=lambda e: -(e.last_used or 0))
    if query == ":fav":
        return sorted((e for e in entries if e.favorite), key=lambda e: (SOURCE_ORDER.get(e.source, 9), e.name.lower()))
    if query == ":aliases":
        return sorted((e for e in entries if e.alias), key=lambda e: e.name.lower())
    if query.startswith(":"):
        return []
    if query:
        matched = [e for e in entries if _matches(query, e)]
        matched.sort(key=lambda e: (not e.favorite, not e.name.lower().startswith(query.lower()), SOURCE_ORDER.get(e.source, 9), -e.usage_count, e.name.lower()))
        if not matched and valid_target(query) and not any(c in query for c in "*?!"):
            matched = [HostEntry(name=query, target=query, source="direct")]
        return matched
    return sorted(entries, key=lambda e: (not e.favorite, not bool(e.last_used), -(e.last_used or 0), -e.usage_count, SOURCE_ORDER.get(e.source, 9), e.name.lower()))


def subtitle(entry: HostEntry, settings: Settings) -> str:
    if entry.alias:
        pieces = [entry.target]
        if entry.description:
            pieces.append(entry.description)
        return " — ".join(pieces) + " · Alias"
    if entry.source == "sshconfig":
        host = entry.hostname or entry.name
        return f"{entry.user}@{host} · SSH Config" if entry.user and settings.show_usernames else f"{host} · SSH Config"
    if entry.source == "customhosts":
        return f"{entry.hostname} · ~/.ssh/etc_hosts"
    if entry.source == "hosts":
        return f"{entry.hostname} · /etc/hosts"
    if entry.source == "knownhosts":
        return "Known Host"
    if entry.source == "history":
        return "Recent direct SSH connection"
    return "Direct SSH connection"


def _edit_path(entry: HostEntry, settings: Settings) -> Path:
    if entry.alias:
        return settings.data_dir / "aliases.json"
    if entry.source_path:
        return Path(entry.source_path)
    return settings.ssh_config


def item(entry: HostEntry, settings: Settings) -> dict:
    command = "ssh " + shlex.quote(entry.target)
    edit_path = str(_edit_path(entry, settings))
    return {
        "uid": entry.uid,
        "title": ("★ " if entry.favorite else "") + entry.name,
        "subtitle": subtitle(entry, settings),
        "arg": entry.target,
        "autocomplete": entry.name,
        "match": searchable_text(entry),
        "text": {"copy": command, "largetype": command},
        "variables": {"ssh_action": "ssh"},
        "mods": {
            "cmd": {"subtitle": f"Copy: {command}", "variables": {"ssh_action": "copy"}},
            "alt": {"subtitle": f"SFTP to {entry.target}", "variables": {"ssh_action": "sftp"}},
            "ctrl": {"subtitle": f"Inspect resolved SSH configuration for {entry.target}", "variables": {"ssh_action": "inspect"}},
            "shift": {"subtitle": f"Open {edit_path}", "arg": edit_path, "variables": {"ssh_action": "edit"}},
        },
    }


def info_item(title: str, subtitle_text: str, *, arg: str = "", action: str = "noop", valid: bool = False) -> dict:
    return {"title": title, "subtitle": subtitle_text, "arg": arg, "valid": valid, "variables": {"ssh_action": action}}


def search_output(entries: list[HostEntry], errors: list[str], query: str, settings: Settings) -> dict:
    query = query.strip()
    if query == ":config":
        items = [info_item("Open SSH config", str(settings.ssh_config), arg=str(settings.ssh_config), action="edit", valid=True)]
    elif query == ":refresh":
        items = [info_item("Host list refreshed", "Sources are read fresh on every search")]
    elif query == ":help":
        items = [info_item("SSH Manager", "Enter: SSH · ⌘: Copy · ⌥: SFTP · ⌃: Inspect · ⇧: Edit"), info_item("Commands", ":recent · :fav · :aliases · :config · :refresh · :help")]
    else:
        items = [item(entry, settings) for entry in select(entries, query)]
        if not items and query == ":fav":
            items = [info_item("No favorite SSH hosts yet", "Create one with: ssha --fav name=target")]
        elif not items and query == ":recent":
            items = [info_item("No recent SSH sessions yet", "Connect to a host to start history")]
        elif not items and query == ":aliases":
            items = [info_item("No Alfred aliases yet", "Create one with: ssha name=target")]
        elif not items and query.startswith(":"):
            items = [info_item("Unknown command", "Try ssh :help")]
        elif not items:
            items = [info_item("No SSH hosts found", "Add a Host to ~/.ssh/config or use ssha name=target")]
    for error in errors[:3]:
        items.append(info_item("SSH Manager warning", error))
    return {"items": items}
