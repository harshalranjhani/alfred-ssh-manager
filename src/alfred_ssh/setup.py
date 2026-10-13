"""Interactive key setup using the installed OpenSSH tools."""
from __future__ import annotations

import base64
import shlex
import subprocess
from pathlib import Path

from .search import info_item, select
from .utils import valid_target

# Run on the key's owner, so a remote private key never leaves that machine.
ENSURE_KEY = r'''set -eu
umask 077
mkdir -p "$HOME/.ssh"
key="$HOME/.ssh/id_ed25519"
if [ -e "$key" ] || [ -L "$key" ] || [ -e "$key.pub" ] || [ -L "$key.pub" ]; then
    if [ ! -f "$key" ] || [ ! -f "$key.pub" ]; then
        echo 'Incomplete ~/.ssh/id_ed25519 key pair. Repair it manually; no files were overwritten.' >&2
        exit 1
    fi
    ssh-keygen -lf "$key.pub"
else
    ssh-keygen -t ed25519 -f "$key" -C 'alfred-ssh'
fi
'''


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def validate_public_key(value: str) -> str:
    parts = value.strip().split()
    if len(value.strip().splitlines()) != 1 or len(parts) < 2 or parts[0] != "ssh-ed25519":
        raise ValueError("Expected one Ed25519 public key")
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except ValueError as exc:
        raise ValueError("Invalid public key encoding") from exc
    if len(blob) != 51 or blob[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
        raise ValueError("Invalid Ed25519 public key")
    return " ".join(parts[:2])


def install_script(public_key: str) -> str:
    key = validate_public_key(public_key)
    blob = key.split()[1]
    return '''set -eu
umask 077
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
file="$HOME/.ssh/authorized_keys"
touch "$file"
chmod 600 "$file"
''' + f'''if awk -v key={shlex.quote(blob)} '{{for (i=1; i<NF; i++) if ($i == "ssh-ed25519" && $(i+1) == key) found=1}} END {{exit !found}}' "$file"; then
    echo 'Public key already present; existing restrictions preserved.'
else
    printf '\\n%s\\n' {shlex.quote(key)} >> "$file"
    echo 'Public key installed.'
fi
'''


def check_target(target: str) -> None:
    if not valid_target(target):
        raise ValueError("Invalid SSH destination")


def test_command(destination: str) -> list[str]:
    check_target(destination)
    # Disable connection multiplexing so a previous session cannot fake success.
    return ["ssh", "-o", "ControlPath=none", "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
            "-o", "ConnectTimeout=10", "-o", "IdentitiesOnly=yes", "-i", str(Path.home() / ".ssh/id_ed25519"),
            destination, "true"]


def perform(action: str, destination: str = "", source: str = "") -> None:
    if action not in {"install", "generate", "copy", "fingerprint", "test"}:
        raise ValueError("Unknown setup action")
    if destination:
        check_target(destination)
    if source:
        check_target(source)
    if action in {"install", "test"} and not destination:
        raise ValueError("Choose a destination")
    if action == "test":
        run(test_command(destination))
        print("Public-key connection succeeded.")
        return
    if action in {"install", "generate"}:
        print(f"Preparing ~/.ssh/id_ed25519 on {source or 'this Mac'}. Existing keys are kept.", flush=True)
        if source:
            run(["ssh", "-a", "-t", source, "sh -c " + shlex.quote(ENSURE_KEY)])
        else:
            run(["sh", "-c", ENSURE_KEY])
    if action == "generate":
        return
    if source:
        public = run(["ssh", "-a", source, 'cat "$HOME/.ssh/id_ed25519.pub"'], stdout=subprocess.PIPE).stdout
    else:
        public = (Path.home() / ".ssh/id_ed25519.pub").read_text(encoding="utf-8")
    public = validate_public_key(public)
    if action == "copy":
        run(["pbcopy"], input=public + "\n")
        print("Public key copied.")
    elif action == "fingerprint":
        run(["ssh-keygen", "-lf", "-"], input=public + "\n")
    else:
        print(f"Installing public key on {destination}. Authenticate when prompted.", flush=True)
        run(["ssh", "-a", destination, "sh -c " + shlex.quote(install_script(public))])
        if source:
            # Destination aliases on this Mac may not exist on the source server.
            config = run(["ssh", "-G", destination], stdout=subprocess.PIPE).stdout
            fields = dict(line.split(" ", 1) for line in config.splitlines() if " " in line)
            if not all(fields.get(name) for name in ("hostname", "user", "port")):
                raise ValueError("Could not resolve destination hostname, user, and port")
            check_target(fields["hostname"])
            command = ["ssh", "-o", "ControlPath=none", "-o", "PreferredAuthentications=publickey",
                       "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
                       "-o", "ConnectTimeout=10", "-o", "IdentitiesOnly=yes", "-i", ".ssh/id_ed25519",
                       "-p", fields["port"], "-l", fields["user"], fields["hostname"], "true"]
            print("Testing from the source server (it must reach the destination directly).", flush=True)
            run(["ssh", "-a", "-t", source, "cd ~ && " + shlex.join(command)])
        else:
            run(test_command(destination))
        print("Public-key connection succeeded. Setup complete.")


def setup_output(entries, errors, query: str, runner: Path) -> dict:
    def row(title, detail, action, destination="", source=""):
        command = shlex.join(["/usr/bin/python3", str(runner), action, destination, source])
        return info_item(title, detail, arg=command, action="setup", valid=True)

    query = query.strip()
    items = []
    source = ""
    if ">" in query:
        source, query = [part.strip() for part in query.split(">", 1)]
        exact = [entry for entry in entries if entry.name == source]
        if exact:
            source = exact[0].target
        if not valid_target(source) or ">" in query:
            return {"items": [info_item("Choose a source and destination", "sshsetup source > destination (SSH names or user@host)")]}
    if not query and not source:
        items = [row("Generate or reuse this Mac’s SSH key", "Ed25519 · prompts for a passphrase · keeps existing keys", "generate"),
                 row("Copy this Mac’s public key", "Copy ~/.ssh/id_ed25519.pub", "copy"),
                 row("Show this Mac’s key fingerprint", "Display the fingerprint in Terminal", "fingerprint"),
                 info_item("Set up access between two servers", "Type sshsetup source > destination; only the public key passes through this Mac")]
    for entry in select(entries, query):
        item = row(f"Set up {source or 'this Mac'} → {entry.name}",
                   f"Generate/reuse Ed25519 key, install on {entry.target}, then test", "install", entry.target, source)
        if not source:
            test = row("", "", "test", entry.target)
            item["mods"] = {"cmd": {"subtitle": "Test existing public-key access only", "arg": test["arg"]}}
        items.append(item)
    if not items:
        items.append(info_item("Choose a destination", "Type sshsetup user@host, or sshsetup source > destination"))
    items.extend(info_item("SSH Manager warning", error) for error in errors[:3])
    return {"items": items}
