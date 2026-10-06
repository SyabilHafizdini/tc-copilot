#!/usr/bin/env python3
"""Smoke fence: the raise ratchet refuses a hand-raised confidence level.

Builds a throwaway renderable project, raises Low/Medium parts to High in its
SIT spec with no Resolution, and runs that copy's real render_sit.py: it must
exit non-zero with the ratchet message and write nothing. Content-free, so it
runs in every bundle. Prints `raise ratchet fence OK` (exit 0) or the reason
(exit 1)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doubts_scratch  # noqa: E402
import test_render_lift as lift  # noqa: E402


def main():
    d = doubts_scratch.render_project()
    try:
        assert lift._rendered(lift._sit(d)[1]) == 0, "scratch baseline re-renders"
        lift.refuse_sit_raise(d, lift._bytes(d))
    except Exception as e:  # noqa: BLE001
        print(f"raise ratchet fence FAILED: {type(e).__name__}: {e}")
        return 1
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("raise ratchet fence OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
