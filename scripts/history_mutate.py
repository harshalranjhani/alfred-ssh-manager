#!/usr/bin/env python3
"""Remove a selected target from workflow history."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings
from alfred_ssh.history import forget


def main() -> None:
    target = " ".join(sys.argv[1:])
    path = Settings.from_env().data_dir / "history.json"
    try:
        if forget(path, target):
            print(f"Forgot SSH session: {target}")
        else:
            print(f"Session not in history: {target}")
    except (OSError, ValueError) as exc:
        print(f"SSH Manager error: {exc}")


if __name__ == "__main__":
    main()
