#!/usr/bin/env python3
"""Search setup destinations without making any SSH connections."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.config import Settings
from alfred_ssh.discovery import discover
from alfred_ssh.setup import setup_output

entries, errors = discover(Settings.from_env())
print(json.dumps(setup_output(entries, errors, " ".join(sys.argv[1:]), Path(__file__).resolve().with_name("setup_action.py"))))
