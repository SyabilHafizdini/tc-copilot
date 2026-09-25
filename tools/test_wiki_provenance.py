#!/usr/bin/env python3
"""Plain-assert tests for `wiki migrate-provenance`
(run: py tools/test_wiki_provenance.py). No pytest -- matches tools/smoke.py.

plan_backfill is pure, so these pass in-memory concepts and write nothing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki_provenance import plan_backfill

def _story(**kw):
    base = {"type": "User Story", "id": "US-T", "title": "t", "description": "d"}
    base.update(kw)
    return base


def test_story_with_derived_from_and_no_provenance_is_stamped_verbatim():
    to_stamp, unresolved = plan_backfill(
        {"stories/US-T": (_story(derived_from=["/sources/prd/1-1.md"]), "")})
    assert to_stamp == {"stories/US-T": "prd-verbatim"}, to_stamp
    assert unresolved == [], unresolved


def test_story_with_neither_is_reported_not_guessed():
    to_stamp, unresolved = plan_backfill({"stories/US-T": (_story(), "")})
    assert to_stamp == {}, to_stamp
    assert unresolved == ["stories/US-T"], unresolved


def test_story_that_already_declares_is_untouched():
    s = _story(derived_from=["/sources/prd/1-1.md"], provenance="prd-interpreted")
    to_stamp, unresolved = plan_backfill({"stories/US-T": (s, "")})
    assert to_stamp == {} and unresolved == [], (to_stamp, unresolved)


def test_non_story_concepts_are_ignored():
    res = {"type": "Resolution", "id": "R-T", "title": "t", "description": "d"}
    to_stamp, unresolved = plan_backfill({"resolutions/R-T": (res, "")})
    assert to_stamp == {} and unresolved == [], (to_stamp, unresolved)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_provenance OK")
