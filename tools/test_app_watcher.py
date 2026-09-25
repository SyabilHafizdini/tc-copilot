#!/usr/bin/env python3
"""Plain-assert tests for the app's change watcher
(run: py tools/test_app_watcher.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

The one test that needs a file change writes ONLY under build/, which is
gitignored, and removes it afterwards -- the tracked tree is never touched.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
import watcher


def test_snapshot_is_a_stable_string():
    a = watcher.snapshot()
    assert isinstance(a, str) and a, a
    assert a == watcher.snapshot(), "snapshot must be stable when nothing changed"


def test_changed_reports_false_against_current():
    now = watcher.snapshot()
    fired, latest = watcher.changed(now)
    assert fired is False, "no change expected"
    assert latest == now


def test_changed_reports_true_against_a_stale_token():
    fired, latest = watcher.changed("definitely-not-a-real-snapshot")
    assert fired is True
    assert latest == watcher.snapshot()


def test_a_new_card_is_noticed():
    """Cards land in build/cards/ -- the event the operator most needs."""
    cards = ROOT / "build/cards"
    cards.mkdir(parents=True, exist_ok=True)
    probe = cards / "zz-watcher-probe.json"
    before = watcher.snapshot()
    probe.write_text("{}", encoding="utf-8")
    try:
        fired, _ = watcher.changed(before)
        assert fired is True, "a new card must change the snapshot"
    finally:
        probe.unlink()


def test_a_same_size_content_change_is_still_missed_but_size_change_is_caught():
    """Count+mtime alone can miss a content change that preserves mtime -- size
    must be folded in too. Rewrite the probe with different-length content but
    restore the original mtime exactly, and assert the snapshot still moves.
    """
    cards = ROOT / "build/cards"
    cards.mkdir(parents=True, exist_ok=True)
    probe = cards / "zz-watcher-probe.json"
    probe.write_text("{}", encoding="utf-8")
    try:
        st = probe.stat()
        atime, mtime = st.st_atime, st.st_mtime
        before = watcher.snapshot()

        probe.write_text('{"changed": true, "padding": "xxxxxxxxxx"}', encoding="utf-8")
        os.utime(probe, (atime, mtime))

        fired, _ = watcher.changed(before)
        assert fired is True, "a same-mtime, different-size rewrite must change the snapshot"
    finally:
        probe.unlink()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_watcher OK")
