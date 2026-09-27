#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.aliases import load_aliases
from alfred_ssh.config import Settings


def main() -> None:
    try:
        aliases = load_aliases(Settings.from_env().data_dir / "aliases.json")
        query = " ".join(sys.argv[1:]).strip().lower()
        items = [{"uid": f"remove:{name}", "title": name, "subtitle": f"Remove Alfred alias → {details['target']}", "arg": name} for name, details in aliases.items() if query in name.lower()]
        if not items:
            items = [{"title": "No matching Alfred aliases", "subtitle": "Only Alfred aliases can be removed here", "valid": False}]
    except (OSError, ValueError) as exc:
        items = [{"title": "Unable to read aliases", "subtitle": str(exc), "valid": False}]
    print(json.dumps({"items": items}, ensure_ascii=False))


if __name__ == "__main__":
    main()
