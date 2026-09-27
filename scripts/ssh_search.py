#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings
from alfred_ssh.discovery import discover
from alfred_ssh.search import search_output


def main() -> None:
    settings = Settings.from_env()
    entries, errors = discover(settings)
    query = " ".join(sys.argv[1:])
    print(json.dumps(search_output(entries, errors, query, settings), ensure_ascii=False))


if __name__ == "__main__":
    main()
