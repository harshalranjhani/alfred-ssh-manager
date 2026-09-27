#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.aliases import parse_add_spec


def main() -> None:
    spec = " ".join(sys.argv[1:]).strip()
    if not spec:
        item = {"title": "Create an SSH alias", "subtitle": "Type name=target, e.g. prod=production-api", "valid": False}
    else:
        try:
            name, details = parse_add_spec(spec)
            item = {"title": f"Save alias {name} → {details['target']}", "subtitle": "Press Enter to create or update", "arg": spec, "valid": True}
        except ValueError as exc:
            item = {"title": "Invalid alias", "subtitle": str(exc), "valid": False}
    print(json.dumps({"items": [item]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
