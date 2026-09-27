#!/usr/bin/env python3
"""Alfred action dispatcher. Emits text for the next Alfred workflow object."""
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings
from alfred_ssh.history import record
from alfred_ssh.resolver import format_resolved
from alfred_ssh.utils import valid_target

HOSTS_HEADER = "# Alfred SSH Manager custom hosts\n# IP_ADDRESS hostname [aliases...]\n# 10.10.0.10 nas nas.home\n"


def main() -> None:
    action = os.environ.get("ssh_action", "ssh")
    value = " ".join(sys.argv[1:])
    settings = Settings.from_env()
    try:
        if action == "edit":
            path = Path(value).expanduser()
            allowed = {settings.ssh_config, settings.custom_hosts, settings.data_dir / "aliases.json"}
            if path not in allowed and not path.is_file():
                raise ValueError("File does not exist")
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(HOSTS_HEADER if path == settings.custom_hosts else ("{}\n" if path.name == "aliases.json" else ""), encoding="utf-8")
            subprocess.run(["open", str(path)], check=True)
            print(f"Opened {path}")
            return
        if not valid_target(value):
            raise ValueError("Invalid SSH destination")
        if action in {"ssh", "sftp"}:
            if settings.enable_history:
                try:
                    record(settings.data_dir / "history.json", value)
                except (OSError, ValueError):
                    pass  # A storage problem must not prevent a connection.
            print(shlex.quote(value))
        elif action == "copy":
            print("ssh " + shlex.quote(value))
        elif action == "inspect":
            print(format_resolved(value))
        else:
            raise ValueError(f"Unknown action: {action}")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SSH Manager error: {exc}")


if __name__ == "__main__":
    main()
