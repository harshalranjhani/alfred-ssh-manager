#!/usr/bin/env python3
"""Runs in Terminal so OpenSSH can prompt normally."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from alfred_ssh.setup import perform

if __name__ == "__main__":
    try:
        perform(*sys.argv[1:])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SSH setup failed: {exc}", file=sys.stderr)
        print("Any completed key generation or installation is kept. Fix the error and retry safely.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSSH setup cancelled. Any completed steps are kept.", file=sys.stderr)
        sys.exit(130)
