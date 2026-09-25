#!/usr/bin/env python3
"""Change detection for the app's live views.

Cheap by design: a fingerprint over git HEAD plus, per watched directory, the
file count, newest mtime, and total size of the directories whose contents
the app renders. Size is folded in because count+mtime alone can miss a
content change that preserves (or backdates) a file's mtime -- it answers
"has anything changed?", not "what changed" -- the client re-fetches state on
any change, which is fast because reads are in-process. File contents are
never hashed: this runs about once a second and reads only stat(), not the
files themselves.

Stdlib only, so it is testable without FastAPI.
"""
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Wiki content the app renders, plus the emitted cards it must surface the
# moment the agent writes one. build/ is gitignored, so git HEAD alone would
# never notice a new card.
WATCHED = ("stories", "glossary", "modules", "resolutions", "flows",
           "testcases", "suites", "sources", "changereports", "build/cards")


def _head():
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "no-head"


def snapshot():
    """Opaque fingerprint of everything the app renders."""
    h = hashlib.sha256()
    h.update(_head().encode())
    for rel in WATCHED:
        d = ROOT / rel
        if not d.exists():
            continue
        newest, count, total_size = 0.0, 0, 0
        for p in d.rglob("*"):
            if p.is_file():
                st = p.stat()
                count += 1
                total_size += st.st_size
                if st.st_mtime > newest:
                    newest = st.st_mtime
        h.update(f"{rel}:{count}:{newest:.6f}:{total_size}".encode())
    return h.hexdigest()


def changed(prev):
    """(fired, latest) -- fired is True when the fingerprint moved."""
    latest = snapshot()
    return (latest != prev, latest)
