#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings

HOSTS_HEADER = "# Alfred SSH Manager custom hosts\n# IP_ADDRESS hostname [aliases...]\n# 10.10.0.10 nas nas.home\n"


def main() -> None:
    settings = Settings.from_env()
    path = settings.ssh_config if sys.argv[1] == "config" else settings.custom_hosts
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("" if sys.argv[1] == "config" else HOSTS_HEADER, encoding="utf-8")
        subprocess.run(["open", str(path)], check=True)
        print(f"Opened {path}")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"SSH Manager error: {exc}")


if __name__ == "__main__":
    main()
