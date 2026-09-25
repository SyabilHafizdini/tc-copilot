#!/usr/bin/env python3
"""Plain-assert tests for the test-model artifact (run: py tools/test_wiki_rubric.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Synthetic frontmatter dicts only; no real story is ever read or mutated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_rubric import (KINDS, load_test_model, model_warnings,
                         validate_test_model)


def _item(iid="BVA-01", technique="BVA", kind="boundary", basis=None,
          feasible=True, justification=None, role=None):
    d = {"id": iid, "technique": technique, "kind": kind,
         "basis": basis if basis is not None else ["AC01"],
         "feasible": feasible}
    if justification is not None:
        d["justification"] = justification
    if role is not None:
        d["role"] = role
    return d


def _fm(items, status="confirmed", acs=("AC01",), rules=("BR01",)):
    return {"id": "US-FAKE",
            "acceptance_criteria": [{"id": a} for a in acs],
            "business_rules": [{"id": r} for r in rules],
            "test_model": {"status": status, "items": list(items)}}


def test_valid_model_has_no_errors():
    assert validate_test_model(_fm([_item()]), "US-FAKE") == []


def test_absent_test_model_is_not_an_error_here():
    """Absence is a refusal at the engine boundary, not a validation error -
    lint must not fail every story that has not been migrated yet."""
    assert validate_test_model({"id": "US-FAKE"}, "US-FAKE") == []


def test_status_must_be_proposed_or_confirmed():
    errs = validate_test_model(_fm([_item()], status="asserted"), "US-FAKE")
    assert any("status 'asserted'" in e for e in errs), errs


def test_duplicate_item_ids_are_rejected():
    errs = validate_test_model(_fm([_item(), _item()]), "US-FAKE")
    assert any("duplicate test_model item id 'BVA-01'" in e for e in errs), errs


def test_two_items_missing_their_id_do_not_report_a_duplicate_none():
    """Keying duplicate detection on a missing id emitted a spurious
    "duplicate test_model item id 'None'" beside the real missing-key error."""
    a, b = _item(), _item()
    del a["id"]
    del b["id"]
    errs = validate_test_model(_fm([a, b]), "US-FAKE")
    assert not any("None" in e for e in errs), errs
    assert sum("missing required key 'id'" in e for e in errs) == 2, errs


def test_unknown_kind_is_rejected():
    errs = validate_test_model(_fm([_item(kind="vibe")]), "US-FAKE")
    assert any("kind 'vibe'" in e for e in errs), errs


def test_unknown_technique_is_rejected():
    errs = validate_test_model(_fm([_item(technique="ZZ")]), "US-FAKE")
    assert any("technique 'ZZ'" in e for e in errs), errs


def test_basis_must_resolve_to_a_real_ac_or_rule():
    errs = validate_test_model(_fm([_item(basis=["AC99"])]), "US-FAKE")
    assert any("basis 'AC99' is neither an AC nor a business rule" in e
               for e in errs), errs


def test_basis_may_be_a_business_rule():
    assert validate_test_model(_fm([_item(basis=["BR01"])]), "US-FAKE") == []


def test_basis_may_be_a_journey_entry_of_a_flow():
    """A flow carries neither acceptance_criteria nor business_rules. Building
    the known set from those two alone left it EMPTY for every flow, so the
    validator rejected every legal journey ref."""
    fm = {"id": "FL-FAKE",
          "journey": [{"id": "J01"}, {"id": "J02"}, {"id": "J03"}],
          "test_model": {"status": "confirmed",
                         "items": [_item("SC-MAIN", "UC", "scenario",
                                         basis=["J01", "J02"], role="main")]}}
    assert validate_test_model(fm, "FL-FAKE") == []


def test_the_spec_uat_flow_model_validates():
    """The canonical scenario model from spec 5.1. The branch's own validator
    used to reject the design's own example, once per journey ref."""
    fm = {"id": "FL-FAKE",
          "journey": [{"id": "J01"}, {"id": "J02"}, {"id": "J03"}],
          "test_model": {"status": "confirmed", "items": [
              {"id": "SC-MAIN", "technique": "UC", "kind": "scenario",
               "role": "main", "basis": ["J01", "J02", "J03"],
               "feasible": True},
              {"id": "SC-ALT-01", "technique": "UC", "kind": "scenario",
               "role": "alternative",
               "desc": "Approver rejects at step 3; requester is notified",
               "basis": ["J03"], "feasible": True}]}}
    assert validate_test_model(fm, "FL-FAKE") == []


def test_empty_basis_is_rejected():
    errs = validate_test_model(_fm([_item(basis=[])]), "US-FAKE")
    assert any("basis must be a non-empty list" in e for e in errs), errs


def test_infeasible_without_justification_is_rejected():
    """29119-4 6.1 requires the justification for an infeasible coverage item
    to be recorded. Discounting one silently is the defect this catches."""
    errs = validate_test_model(_fm([_item(feasible=False)]), "US-FAKE")
    assert any("feasible: false requires a non-empty justification" in e
               for e in errs), errs


def test_infeasible_with_justification_is_accepted():
    m = _fm([_item(feasible=False, justification="Hardware cannot reach it.")])
    assert validate_test_model(m, "US-FAKE") == []


def test_infeasible_with_blank_justification_is_rejected():
    m = _fm([_item(feasible=False, justification="   ")])
    errs = validate_test_model(m, "US-FAKE")
    assert any("non-empty justification" in e for e in errs), errs


def test_two_main_scenarios_are_rejected():
    """29119-4 5.2.9.1: the model identifies THE main scenario, singular."""
    m = _fm([_item("SC-A", "UC", "scenario", role="main"),
             _item("SC-B", "UC", "scenario", role="main")])
    errs = validate_test_model(m, "US-FAKE")
    assert any("more than one item with role: main" in e for e in errs), errs


def test_unknown_role_is_rejected():
    m = _fm([_item("SC-A", "UC", "scenario", role="primary")])
    errs = validate_test_model(m, "US-FAKE")
    assert any("role 'primary'" in e for e in errs), errs


def test_load_test_model_returns_items_and_status():
    items, status = load_test_model(_fm([_item()]))
    assert status == "confirmed"
    assert [i["id"] for i in items] == ["BVA-01"]


def test_load_test_model_on_absent_model():
    assert load_test_model({"id": "US-FAKE"}) == ([], None)


def test_scenario_model_without_alternatives_warns():
    """A flow whose model is the main scenario only would otherwise score a
    misleading C = 1/1 = 100%."""
    items = [_item("SC-MAIN", "UC", "scenario", role="main")]
    assert any("main scenario only" in w for w in model_warnings(items))


def test_scenario_model_with_an_alternative_does_not_warn():
    items = [_item("SC-MAIN", "UC", "scenario", role="main"),
             _item("SC-ALT-01", "UC", "scenario", role="alternative")]
    assert model_warnings(items) == []


def test_non_scenario_model_does_not_warn_about_scenarios():
    assert model_warnings([_item()]) == []


def test_kinds_are_the_documented_set():
    assert KINDS == {"partition", "boundary", "transition", "rule", "pair",
                     "scenario"}


# ------------------------------------------------- coverage arithmetic (Task 3)
from wiki_rubric import coverage_by_technique, unknown_item_refs


def test_full_coverage_is_100():
    items = [_item("BVA-01"), _item("BVA-02")]
    cov = coverage_by_technique(items, {"BVA-01", "BVA-02"})
    assert cov["BVA"]["N"] == 2 and cov["BVA"]["T"] == 2
    assert cov["BVA"]["C"] == 100.0


def test_partial_coverage_uses_the_standard_formula():
    """C = (N / T) x 100, 29119-4 6.1."""
    items = [_item(f"BVA-0{n}") for n in (1, 2, 3, 4)]
    cov = coverage_by_technique(items, {"BVA-01", "BVA-03", "BVA-04"})
    assert cov["BVA"]["C"] == 75.0
    assert cov["BVA"]["uncovered"] == ["BVA-02"]


def test_infeasible_items_are_discounted_from_T_by_default():
    """29119-4 6.1 allows discounting infeasible items, which is what makes
    100% an achievable goal (Annex F)."""
    items = [_item("BVA-01"),
             _item("BVA-02", feasible=False, justification="unreachable")]
    cov = coverage_by_technique(items, {"BVA-01"})
    assert cov["BVA"]["T"] == 1, "infeasible item must not inflate T"
    assert cov["BVA"]["C"] == 100.0
    assert cov["BVA"]["discounted"] == ["BVA-02"]


def test_infeasible_items_can_be_counted_instead():
    """6.1 requires the choice be DEFINED, not that it be one way."""
    items = [_item("BVA-01"),
             _item("BVA-02", feasible=False, justification="unreachable")]
    cov = coverage_by_technique(items, {"BVA-01"}, count_infeasible=True)
    assert cov["BVA"]["T"] == 2 and cov["BVA"]["C"] == 50.0


def test_techniques_are_measured_separately():
    items = [_item("BVA-01"), _item("EP-01", technique="EP", kind="partition")]
    cov = coverage_by_technique(items, {"BVA-01"})
    assert cov["BVA"]["C"] == 100.0
    assert cov["EP"]["C"] == 0.0


def test_empty_denominator_gives_C_none_not_zero_or_100():
    """A technique whose every item is discounted has UNDEFINED coverage.
    Reporting 100% there would be a lie; reporting 0% would be a different one."""
    items = [_item("BVA-01", feasible=False, justification="unreachable")]
    cov = coverage_by_technique(items, set())
    assert cov["BVA"]["T"] == 0
    assert cov["BVA"]["C"] is None


def test_covering_an_item_twice_does_not_inflate_N():
    """The covered ids arrive as a LIST here, not a set literal: Python
    collapses {"BVA-01", "BVA-01"} at parse time, so a set literal made this
    test incapable of failing."""
    items = [_item("BVA-01"), _item("BVA-02")]
    cov = coverage_by_technique(items, ["BVA-01", "BVA-01", "BVA-02"])
    assert cov["BVA"]["N"] == 2


def test_covering_a_discounted_item_does_not_inflate_N():
    items = [_item("BVA-01"),
             _item("BVA-02", feasible=False, justification="unreachable")]
    cov = coverage_by_technique(items, {"BVA-01", "BVA-02"})
    assert cov["BVA"]["N"] == 1, "a discounted item is outside the measurement"
    assert cov["BVA"]["C"] == 100.0


def test_unknown_item_refs_are_reported():
    items = [_item("BVA-01")]
    assert unknown_item_refs(items, {"BVA-01", "GHOST-01"}) == ["GHOST-01"]


def test_unknown_item_refs_empty_when_all_resolve():
    assert unknown_item_refs([_item("BVA-01")], {"BVA-01"}) == []


# ------------------------------------------------ sealed digest + records
from wiki_rubric import (DIFF_FIELDS, active_rels_from_manifest,  # noqa: E402
                         sealed_digest, tc_record)


def test_sealed_digest_is_order_independent_and_content_sensitive():
    h = {"testcases/sit/S/A": "sha256:1", "testcases/sit/S/B": "sha256:2"}
    d1 = sealed_digest(h, ["testcases/sit/S/A", "testcases/sit/S/B"])
    d2 = sealed_digest(h, ["testcases/sit/S/B", "testcases/sit/S/A"])
    assert d1 == d2 and d1.startswith("sha256:"), (d1, d2)
    h2 = dict(h, **{"testcases/sit/S/B": "sha256:3"})
    assert sealed_digest(h2, h) != d1, "a changed hash must change the digest"
    assert sealed_digest(h, ["testcases/sit/S/A"]) != d1, \
        "a different active set must change the digest"


def test_tc_record_captures_every_body_section_by_heading():
    body = ("# Objective\n\nSee it.\n\n# Steps\n\n1. Open.\n2. Look.\n\n"
            "# Expected Results\n\n1. Shown.\n")
    fm = {"id": "1-AC01-01", "status": "active", "title": "t",
          "technique": "UC", "priority": "P1", "coverage_items": ["SC-01"],
          "covers": ["/stories/US-1.md#AC01"],
          "retirement": {"reason": "superseded"}}
    rec = tc_record("testcases/sit/S/1-AC01-01", fm, body,
                    {"testcases/sit/S/1-AC01-01": "sha256:x"})
    assert rec["id"] == "1-AC01-01" and rec["hash"] == "sha256:x", rec
    assert rec["sections"] == {"Objective": "See it.",
                               "Steps": "1. Open.\n2. Look.",
                               "Expected Results": "1. Shown."}, rec["sections"]
    assert rec["retirement_reason"] == "superseded"
    assert rec["verifies_rules"] == [] and rec["covers"] == ["/stories/US-1.md#AC01"]
    for f in DIFF_FIELDS:
        assert f in rec, f


def test_active_rels_from_manifest_follows_covers_edges():
    m = {"concepts": {"testcases/sit/S/A": {"status": "active"},
                      "testcases/sit/S/B": {"status": "stale"},
                      "testcases/sit/S/C": {"status": "active"},
                      "stories/US-S": {"status": "aligned"}},
         "edges": [["testcases/sit/S/A", "covers", "stories/US-S#AC1"],
                   ["testcases/sit/S/B", "covers", "stories/US-S#AC1"],
                   ["testcases/sit/S/C", "covers", "stories/US-OTHER#AC1"]]}
    assert active_rels_from_manifest(m, "stories/US-S") == ["testcases/sit/S/A"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_rubric OK")
