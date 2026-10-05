#!/usr/bin/env python3
"""Plain-assert tests for `wiki flow-draft` (run: py tools/test_wiki_flowdraft.py).
No pytest -- matches tools/smoke.py.

draft_to_flow is pure, so these pass in-memory concepts and write nothing.
What matters most is what it REFUSES: a drawing is a proposal and must never
become, or replace, an asserted flow."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki_flowdraft import Refusal, builder_model, draft_to_flow

STORY = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "status": "aligned",
         "acceptance_criteria": [{"id": "AC-1", "text": "a"}, {"id": "AC-2", "text": "b"}]}


def _concepts(flow_status=None):
    c = {"stories/US-T": (STORY, "", None)}
    if flow_status:
        c["flows/FLOW-T"] = ({"type": "Flow", "id": "FLOW-T", "title": "old",
                              "description": "d", "status": flow_status}, "", None)
    return c


def _draft(**kw):
    d = {"kind": "flow-draft", "id": "FLOW-T", "title": "Login journey",
         "entry_condition": "Logged out",
         "journey": [
             {"id": "J01", "ref": "US-T#AC-1", "end_state": "Home shown",
              "note": None, "branch": None},
             {"id": "J02", "ref": "US-T#AC-2", "end_state": "Error shown",
              "note": "leaves the main path after J01", "branch": "B01"}],
         "branches": [{"id": "B01", "title": "Wrong password", "text": "Leaves after J01."}],
         "paths": [["J01"], ["J01", "J02"]]}
    d.update(kw)
    return d


def _refused(draft, concepts=None):
    try:
        draft_to_flow(draft, concepts or _concepts())
    except Refusal as e:
        return str(e)
    raise AssertionError("expected a Refusal")


def test_builder_model_lists_sections_with_their_sit_test_cases_and_flows():
    def tc(tid, kind, status="active"):
        return ({"type": "Test Case", "id": tid, "title": "t " + tid, "kind": kind,
                 "status": status, "covers": ["/stories/US-T.md#AC-1"]},
                "\n# Steps\n\n1. x\n\n# Postconditions\n\nHome shown.\n", None)
    c = _concepts("aligned")
    c["flows/FLOW-T"][0].update(
        entry_condition="Logged out",
        journey=[{"id": "J01", "ref": "/stories/US-T.md#AC-1", "end_state": "Home"},
                 {"id": "J02", "ref": "/stories/US-T.md#AC-2", "end_state": "Error",
                  "note": "alt", "branch": "/flows/FLOW-T.md#B01",
                  "source_tc": "/testcases/sit/m/1.1-AC01-01.md"}],
        branches=[{"id": "B01", "title": "Wrong password", "text": "x"}])
    c["testcases/sit/m/1.1-AC01-01"] = tc("1.1-AC01-01", "sit")
    c["testcases/sit/m/1.1-AC01-02"] = tc("1.1-AC01-02", "sit", "retired")
    c["testcases/uat/UAT-1.1-AC01-01"] = tc("UAT-1.1-AC01-01", "uat")
    m = builder_model(c, {"project": {"name": "Demo", "code": "DMO"}})
    assert m["project"] == "Demo" and m["code"] == "DMO"
    ac1, ac2 = m["stories"][0]["acs"]
    # only live SIT test cases stand behind a section: no UAT, no retired
    assert ac1["tcs"] == ["1.1-AC01-01"] and ac2["tcs"] == []
    # each test case names the criteria it covers, so a step can carry its ref
    assert m["tcs"] == {"1.1-AC01-01": {"id": "1.1-AC01-01", "title": "t 1.1-AC01-01",
                                        "acs": ["US-T#AC-1"],
                                        "sections": {"Postconditions": "Home shown."}}}
    f = m["flows"][0]
    assert f["entry_condition"] == "Logged out" and f["status"] == "aligned"
    assert f["journey"] == [
        {"id": "J01", "end_state": "Home", "note": None, "ac_ref": "US-T#AC-1",
         "source_tc": None, "branch": None},
        {"id": "J02", "end_state": "Error", "note": "alt", "ac_ref": "US-T#AC-2",
         "source_tc": "1.1-AC01-01", "branch": {"id": "B01", "title": "Wrong password"}}]


def test_draft_becomes_a_draft_flow_with_wiki_refs():
    rel, fm, body = draft_to_flow(_draft(), _concepts())
    assert rel == "flows/FLOW-T"
    assert fm["status"] == "draft" and fm["origin"] == "human-drafted"
    # the human has asserted nothing yet: no assertion fields, no test model
    assert not {"asserted_by", "asserted_at", "test_model"} & set(fm)
    assert fm["stories"] == ["/stories/US-T.md"]
    assert fm["journey"] == [
        {"id": "J01", "ref": "/stories/US-T.md#AC-1", "end_state": "Home shown"},
        {"id": "J02", "ref": "/stories/US-T.md#AC-2", "end_state": "Error shown",
         "note": "leaves the main path after J01", "branch": "/flows/FLOW-T.md#B01"}]
    assert fm["branches"] == [{"id": "B01", "title": "Wrong password",
                               "text": "Leaves after J01."}]
    assert "- alt 1: J01 > J02" in body
    # an open question keeps `assert flow` shut until alignment has happened
    assert "# Open Questions\n\n- " in body


def _with_tcs():
    c = _concepts()
    for tid, kind, status, ac in (("1.1-AC01-01", "sit", "active", "AC-1"),
                                  ("1.1-AC01-09", "sit", "retired", "AC-1"),
                                  ("UAT-1.1-AC01-01", "uat", "active", "AC-1")):
        c[f"testcases/{kind}/m/{tid}"] = (
            {"type": "Test Case", "id": tid, "title": "t", "kind": kind,
             "status": status, "covers": [f"/stories/US-T.md#{ac}"]}, "", None)
    return c


def _stitched(tc_id, entry=0):
    j = _draft()["journey"]
    j[entry]["source_tc"] = tc_id
    return _draft(journey=j)


def test_a_stitched_test_case_is_recorded_as_source_tc():
    _rel, fm, body = draft_to_flow(_stitched("1.1-AC01-01"), _with_tcs())
    assert fm["journey"][0] == {"id": "J01", "ref": "/stories/US-T.md#AC-1",
                                "end_state": "Home shown",
                                "source_tc": "/testcases/sit/m/1.1-AC01-01.md"}
    assert "source_tc" not in fm["journey"][1]      # a step may still be criterion-only
    assert "1 stitched from a SIT test case" in body


def test_refuses_a_test_case_that_cannot_be_stitched():
    c = _with_tcs()
    assert "does not exist" in _refused(_stitched("1.1-AC99-01"), c)
    assert "does not exist" in _refused(_stitched("1.1-AC01-09"), c)      # retired
    assert "does not exist" in _refused(_stitched("UAT-1.1-AC01-01"), c)  # not SIT
    # J02 is on AC-2; this test case covers AC-1 only
    assert "does not cover US-T#AC-2" in _refused(_stitched("1.1-AC01-01", entry=1), c)


def test_redrawing_an_unasserted_draft_is_allowed():
    for status in ("draft", "in-alignment"):
        _rel, fm, _b = draft_to_flow(_draft(), _concepts(status))
        assert fm["title"] == "Login journey"


def test_never_replaces_an_asserted_flow():
    msg = _refused(_draft(), _concepts("aligned"))
    assert "already exists" in msg and "aligned" in msg, msg


def test_refuses_sections_that_do_not_exist():
    j = _draft()["journey"]
    j[1]["ref"] = "US-T#AC-9"
    assert "does not exist" in _refused(_draft(journey=j))
    j[1]["ref"] = "US-NOPE#AC-1"
    assert "does not exist" in _refused(_draft(journey=j))


def test_refuses_incomplete_drawings():
    j = _draft()["journey"]
    j[0]["end_state"] = "  "
    assert "no end state" in _refused(_draft(journey=j))
    assert "empty" in _refused(_draft(journey=[]))
    assert "no title" in _refused(_draft(title=""))
    assert "letters, digits" in _refused(_draft(id="../evil"))
    assert "not defined" in _refused(_draft(branches=[]))
    assert "Flow Builder drawing" in _refused(_draft(kind="findings"))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_flowdraft OK")
