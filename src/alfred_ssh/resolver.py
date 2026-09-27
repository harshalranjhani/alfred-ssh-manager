from __future__ import annotations

import subprocess

from .utils import valid_target

FIELDS = ("host", "hostname", "user", "port", "identityfile", "proxyjump", "proxycommand", "forwardagent", "serveraliveinterval", "controlmaster", "controlpath")


def resolve_host(target: str) -> dict[str, list[str]]:
    if not valid_target(target):
        raise ValueError("Invalid SSH destination")
    try:
        result = subprocess.run(["ssh", "-G", "--", target], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Unable to run ssh -G: {exc}") from exc
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"ssh -G failed ({result.returncode})")
    details: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(" ")
        if separator and key.lower() in FIELDS:
            details.setdefault(key.lower(), []).append(value)
    return details


def format_resolved(target: str) -> str:
    details = resolve_host(target)
    lines = [f"SSH configuration for {target}", ""]
    labels = {"host": "Host", "hostname": "HostName", "user": "User", "port": "Port", "identityfile": "IdentityFile", "proxyjump": "ProxyJump", "proxycommand": "ProxyCommand", "forwardagent": "ForwardAgent", "serveraliveinterval": "ServerAliveInterval", "controlmaster": "ControlMaster", "controlpath": "ControlPath"}
    for field in FIELDS:
        for value in details.get(field, []):
            lines.append(f"{labels[field]}: {value}")
    return "\n".join(lines)
