#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.aliases import parse_add_spec, remove_alias, save_alias
from alfred_ssh.config import Settings


def main() -> None:
    operation = sys.argv[1]
    value = " ".join(sys.argv[2:])
    path = Settings.from_env().data_dir / "aliases.json"
    try:
        if operation == "add":
            name, details = parse_add_spec(value)
            save_alias(path, name, details)
            print(f"Alias saved: {name} → {details['target']}")
        elif operation == "remove":
            print(f"Alias removed: {value}" if remove_alias(path, value) else f"Alias not found: {value}")
    except (OSError, ValueError) as exc:
        print(f"SSH Manager error: {exc}")


if __name__ == "__main__":
    main()
