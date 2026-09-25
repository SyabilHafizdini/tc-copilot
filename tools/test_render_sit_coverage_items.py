#!/usr/bin/env python3
"""Plain-assert tests for coverage_items on the SIT spec
(run: py tools/test_render_sit_coverage_items.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Synthetic spec and story dicts; nothing on disk is read or written.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sit


def _spec(tcs):
    return {"story": "/stories/US-FAKE.md", "module": "/modules/m.md",
            "figma": None, "out": "testcases/sit/m", "ac_prefix": "1.1",
            "scenario_id": "SC-{ac}-{seq:02d}", "generator_version": "1.0.0",
            "pre_common": "1. Logged in.", "post_default": "No change.",
            "test_cases": tcs}


def _tc(**kw):
    d = {"ac": "AC1", "seq": 1, "technique": "BVA", "priority": "P1",
         "area": "Area", "title": "t", "objective": "o",
         "steps": "1. Do it.", "expected": "1. It happened."}
    d.update(kw)
    return d


def _story():
    return {"id": "US-FAKE",
            "acceptance_criteria": [{"id": "1.1-AC1"}],
            "business_rules": [{"id": "BR01"}],
            "test_model": {"status": "confirmed", "items": [
                {"id": "BVA-01", "technique": "BVA", "kind": "boundary",
                 "basis": ["1.1-AC1"], "feasible": True},
                {"id": "BVA-02", "technique": "BVA", "kind": "boundary",
                 "basis": ["1.1-AC1"], "feasible": True}]}}


def test_coverage_items_is_an_accepted_key():
    assert "coverage_items" in render_sit.TC_OPTIONAL


def test_covers_is_not_repurposed():
    """`covers` stays the AC-refs key on TC frontmatter. If it ever appears in
    the spec schema, traceability and coverage linkage have been conflated."""
    assert "covers" not in render_sit.TC_OPTIONAL
    assert "covers" not in render_sit.TC_REQUIRED


def test_non_list_coverage_items_is_rejected():
    errs = render_sit.coverage_item_errors(
        _spec([_tc(coverage_items="BVA-01")]), _story(), "US-FAKE")
    assert any("coverage_items must be a list" in e for e in errs), errs


def test_unknown_coverage_item_is_rejected():
    errs = render_sit.coverage_item_errors(
        _spec([_tc(coverage_items=["GHOST-01"])]), _story(), "US-FAKE")
    assert any("'GHOST-01' is not in the test_model" in e for e in errs), errs


def test_known_coverage_items_pass():
    errs = render_sit.coverage_item_errors(
        _spec([_tc(coverage_items=["BVA-01", "BVA-02"])]), _story(), "US-FAKE")
    assert errs == [], errs


def test_absent_coverage_items_is_not_an_error():
    """coverage_items is TC_OPTIONAL in this plan - an unmigrated spec still
    renders, it just scores 0 on T1.1."""
    errs = render_sit.coverage_item_errors(
        _spec([_tc()]), _story(), "US-FAKE")
    assert errs == [], errs


def test_an_empty_test_model_still_rejects_a_coverage_item_ref():
    """`if not known: continue` conflated "not migrated yet" with "the model
    identifies nothing", so a spec naming BVA-01 against
    `test_model: {items: []}` rendered silently. The PRESENCE of the block,
    not the size of the list, is what says the refs are checkable."""
    story = dict(_story())
    story["test_model"] = {"status": "confirmed", "items": []}
    errs = render_sit.coverage_item_errors(
        _spec([_tc(coverage_items=["BVA-01"])]), story, "US-FAKE")
    assert any("'BVA-01' is not in the test_model" in e for e in errs), errs


def test_no_test_model_means_no_coverage_item_checking():
    """A story that has not been migrated cannot have its refs checked; that is
    a refusal at the engine, not a render-time error."""
    story = {"id": "US-FAKE", "acceptance_criteria": [{"id": "1.1-AC1"}]}
    errs = render_sit.coverage_item_errors(
        _spec([_tc(coverage_items=["BVA-01"])]), story, "US-FAKE")
    assert errs == [], errs


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_render_sit_coverage_items OK")
