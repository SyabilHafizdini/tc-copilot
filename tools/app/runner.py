#!/usr/bin/env python3
"""The app's only subprocess call site.

Executes the real tools/wiki.py so every fence, refusal and auto-commit
applies unchanged. Takes an argv LIST -- never a string, never shell=True --
and returns the exit code and output verbatim so the UI can render a refusal
exactly as the terminal would.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WIKI = ROOT / "tools/wiki.py"


def run(argv):
    """Run `py tools/wiki.py <argv...>`. Returns rc/stdout/stderr verbatim.

    argv must already have been built by actions.build(); this function does
    no validation of its own, and callers must never pass user input here
    directly.
    """
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise TypeError(f"argv must be a list of str, got {argv!r}")
    full = [sys.executable, str(WIKI), *argv]
    r = subprocess.run(full, cwd=ROOT, capture_output=True, text=True)
    return {"argv": argv, "rc": r.returncode,
            "stdout": r.stdout, "stderr": r.stderr}
