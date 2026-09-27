#!/usr/bin/env python3
"""Show recorded SSH targets that can be removed from Recent."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings
from alfred_ssh.history import load_history


def main() -> None:
    path = Settings.from_env().data_dir / "history.json"
    query = " ".join(sys.argv[1:]).strip().lower()
    try:
        history = load_history(path)
        matches = [(target, details) for target, details in history.items()
                   if query in target.lower() and isinstance(details, dict)]
        matches.sort(key=lambda pair: -float(pair[1].get("last_used") or 0))
        items = [{"uid": f"forget:{target}", "title": target,
                  "subtitle": "Forget this SSH session from Recent", "arg": target}
                 for target, _ in matches]
        if not items:
            items = [{"title": "No matching recent sessions", "subtitle": "Only recorded SSH history can be forgotten here", "valid": False}]
    except (OSError, ValueError, TypeError) as exc:
        items = [{"title": "Unable to read SSH history", "subtitle": str(exc), "valid": False}]
    print(json.dumps({"items": items}, ensure_ascii=False))


if __name__ == "__main__":
    main()
