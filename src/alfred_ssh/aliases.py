from __future__ import annotations

import shlex
from pathlib import Path

from .models import HostEntry
from .utils import read_json, valid_target, write_json


def load_aliases(path: Path) -> dict:
    data = read_json(path)
    for name, details in data.items():
        if not valid_target(name) or not isinstance(details, dict) or not valid_target(str(details.get("target", ""))):
            raise ValueError(f"Invalid alias entry: {name}")
        if not isinstance(details.get("tags", []), list) or not all(isinstance(tag, str) for tag in details.get("tags", [])):
            raise ValueError(f"Invalid tags for alias: {name}")
    return data


def resolve_alias(name: str, data: dict) -> str:
    seen = set()
    while name in data:
        if name in seen:
            raise ValueError("Alias cycle detected")
        seen.add(name)
        name = data[name]["target"]
    return name


def alias_entries(path: Path) -> list[HostEntry]:
    data = load_aliases(path)
    entries = []
    for name, details in data.items():
        try:
            target = resolve_alias(name, data)
        except ValueError:
            continue
        entries.append(HostEntry(
            name=name, target=target, source="alias", source_path=str(path), alias=True,
            description=details.get("description"), tags=details.get("tags", []),
            favorite=bool(details.get("favorite", False)),
        ))
    return entries


def parse_add_spec(spec: str) -> tuple[str, dict]:
    tokens = shlex.split(spec)
    favorite = False
    tags = []
    description = None
    assignment = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in {"--fav", "--favorite"}:
            favorite = True
        elif token in {"--tag", "--description"}:
            i += 1
            if i >= len(tokens):
                raise ValueError(f"{token} needs a value")
            if token == "--tag":
                tags.append(tokens[i])
            else:
                description = tokens[i]
        elif assignment is None and "=" in token:
            assignment = token
        else:
            raise ValueError("Use: name=target [--fav] [--tag tag] [--description text]")
        i += 1
    if not assignment:
        raise ValueError("Use: name=target [--fav] [--tag tag] [--description text]")
    name, target = assignment.split("=", 1)
    if not valid_target(name) or not valid_target(target) or any(c in name for c in "*?!"):
        raise ValueError("Alias name and target must be single SSH destination tokens")
    result = {"target": target}
    if favorite:
        result["favorite"] = True
    if tags:
        result["tags"] = tags
    if description:
        result["description"] = description
    return name, result


def save_alias(path: Path, name: str, details: dict) -> None:
    data = load_aliases(path)
    merged = {**data.get(name, {}), **details}
    data[name] = merged
    resolve_alias(name, data)
    write_json(path, data)


def remove_alias(path: Path, name: str) -> bool:
    data = load_aliases(path)
    if name not in data:
        return False
    del data[name]
    write_json(path, data)
    return True
