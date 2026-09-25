#!/usr/bin/env python3
"""Plain-assert tests for the UAT coverage fence (run: py tools/test_wiki_coverage_fence.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Uses synthetic concept dicts, so no real story is ever mutated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_coverage import unconfirmed_members


def _story(status):
    return ({"id": "US-FAKE", "coverage_status": status,
             "coverage_map": [], "components": []}, "", None)


def test_all_confirmed_returns_empty():
    concepts = {"stories/US-FAKE": _story("confirmed")}
    journey = [{"id": "J01", "ref": "/stories/US-FAKE.md#AC1"}]
    assert unconfirmed_members(journey, concepts) == []


def test_proposed_member_is_reported_with_its_status():
    concepts = {"stories/US-FAKE": _story("proposed")}
    journey = [{"id": "J01", "ref": "/stories/US-FAKE.md#AC1"}]
    assert unconfirmed_members(journey, concepts) == ["US-FAKE (proposed)"]


def test_absent_status_is_reported_as_absent():
    concepts = {"stories/US-FAKE": _story(None)}
    journey = [{"id": "J01", "ref": "/stories/US-FAKE.md#AC1"}]
    assert unconfirmed_members(journey, concepts) == ["US-FAKE (absent)"]


def test_repeated_member_reported_once():
    concepts = {"stories/US-FAKE": _story("proposed")}
    journey = [{"id": "J01", "ref": "/stories/US-FAKE.md#AC1"},
               {"id": "J02", "ref": "/stories/US-FAKE.md#AC2"}]
    assert unconfirmed_members(journey, concepts) == ["US-FAKE (proposed)"], \
        "a story touched by several journey entries must be listed once"


def test_real_flow_is_clean():
    """Every aligned flow shipped in this bundle must pass the fence.

    Discovered from the wiki rather than naming one project's flow, so this
    holds for whatever flows a project actually has. A bundle with no aligned
    journey (the base branch, or a project before its first flow alignment)
    has nothing to assert and says so.
    """
    from wiki import load_all
    concepts, _m = load_all()
    flows = [(rel, fm) for rel, (fm, _b, _p) in concepts.items()
             if fm and fm.get("type") == "Flow" and fm.get("journey")
             and fm.get("status") == "aligned"]
    if not flows:
        print("      (no aligned flow with a journey in this bundle — "
              "nothing to check)")
        return
    for rel, fm in flows:
        assert unconfirmed_members(fm["journey"], concepts) == [], \
            f"{rel}: an aligned flow's member stories are confirmed; " \
            "fence must not fire"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_coverage_fence OK")
