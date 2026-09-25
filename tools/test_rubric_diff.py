#!/usr/bin/env python3
"""Plain-assert tests for the draft -> final diff
(run: py tools/test_rubric_diff.py). No pytest - matches tools/smoke.py."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
from wiki_rubric import tc_record  # noqa: E402

CFG = {"ids": {"tc_format": "{story_num}-AC{ac_num:02d}-{seq:02d}",
               "story_prefix": "US-"}}


def _rec(tid, body, status="active", reason=None, **fm):
    f = {"id": tid, "status": status, "title": "t", "technique": "UC",
         "priority": "P1", "coverage_items": ["SC-01"], "covers": [],
         "retirement": {"reason": reason} if reason else None}
    f.update(fm)
    return tc_record(f"testcases/sit/S/{tid}", f, body, {f"testcases/sit/S/{tid}": "sha256:" + str(hash(body + status))})


B1 = "# Test Data\n\n**A** = 1\n\n# Expected Results\n\n1. Ok.\n"
B2 = "# Test Data\n\n**A** = 2\n\n# Expected Results\n\n1. Ok.\n"


def test_patch_tc_index_maps_story_ops_to_ids_and_flow_ops_by_tc():
    patch = {"patches": [
        {"op": "set", "ac": "AC6", "seq": 1, "field": "data", "closes": "G3.1"},
        {"op": "add", "closes": "G1.19, G2.2",
         "test_case": {"ac": "AC20", "seq": 3, "title": "x"}}]}
    idx = rj.patch_tc_index("US-1.2.3.4", "story", patch, CFG)
    assert set(idx) == {"1.2.3.4-AC06-01", "1.2.3.4-AC20-03"}, idx
    assert idx["1.2.3.4-AC06-01"] == [{"op": "set", "field": "data", "closes": "G3.1"}]
    fidx = rj.patch_tc_index("f-e2e", "flow",
                             {"patches": [{"op": "set", "tc": "UAT-1-AC01-01",
                                           "field": "steps", "closes": "G3.2"}]}, CFG)
    assert fidx == {"UAT-1-AC01-01": [{"op": "set", "field": "steps", "closes": "G3.2"}]}
    assert rj.patch_tc_index("US-1", "story", None, CFG) == {}


def test_diff_classifies_added_changed_removed_and_unchanged():
    old = {"1-AC01-01": _rec("1-AC01-01", B1), "1-AC01-02": _rec("1-AC01-02", B1),
           "1-AC01-03": _rec("1-AC01-03", B1)}
    new = {"1-AC01-01": _rec("1-AC01-01", B1),                      # unchanged
           "1-AC01-02": _rec("1-AC01-02", B2, priority="P2"),       # changed
           "1-AC01-04": _rec("1-AC01-04", B1, title="new one")}     # added; 03 gone
    cause = {"1-AC01-02": [{"op": "set", "field": "data", "closes": "G3.1"}],
             "1-AC01-04": [{"op": "add", "field": None, "closes": "G1.2"}]}
    changes, counts = rj.diff_records(old, new, cause)
    assert counts == {"added": 1, "changed": 1, "removed": 1, "unchanged": 1}, counts
    kinds = {(c["tc"], c["kind"], c.get("field")) for c in changes}
    assert ("1-AC01-04", "added", None) in kinds
    assert ("1-AC01-03", "removed", None) in kinds
    assert ("1-AC01-02", "changed", "priority") in kinds
    assert ("1-AC01-02", "changed", "Test Data") in kinds, kinds
    td = next(c for c in changes if c["tc"] == "1-AC01-02" and c["field"] == "Test Data")
    assert td["old"] == "**A** = 1" and td["new"] == "**A** = 2" and td["closes"] == "G3.1", td
    pr = next(c for c in changes if c["tc"] == "1-AC01-02" and c["field"] == "priority")
    assert pr["closes"] == "G3.1" and pr["op"] is None, "no op names priority; scope-level closes"
    added = next(c for c in changes if c["kind"] == "added")
    assert added["title"] == "new one" and added["closes"] == "G1.2"


def test_a_retired_case_is_removed_with_its_reason():
    old = {"1-AC01-01": _rec("1-AC01-01", B1)}
    new = {"1-AC01-01": _rec("1-AC01-01", B1, status="retired", reason="superseded")}
    changes, counts = rj.diff_records(old, new)
    assert counts["removed"] == 1 and counts["changed"] == 0, counts
    assert changes == [{"tc": "1-AC01-01", "kind": "removed", "reason": "superseded"}], changes


def test_a_case_added_after_the_draft_but_not_active_now_is_removed():
    """M8: status is checked before 'added' - a case the draft never had and
    the current set no longer holds as active is not an addition."""
    new = {"1-AC01-05": _rec("1-AC01-05", B1, status="retired", reason="voided AC")}
    changes, counts = rj.diff_records({}, new)
    assert counts == {"added": 0, "changed": 0, "removed": 1, "unchanged": 0}, counts
    assert changes == [{"tc": "1-AC01-05", "kind": "removed", "reason": "voided AC"}], changes


def test_write_changes_emits_json_and_markdown_with_the_score_header():
    old_b = rj.RUBRIC_BUILD
    d = Path(tempfile.mkdtemp(prefix="diff-"))
    try:
        rj.RUBRIC_BUILD = d
        snapshot = {"sealed_digest": "sha256:d0", "score": None,
                    "exported_at": "2026-09-25T10:00:00+08:00",
                    "test_cases": {"1-AC01-01": _rec("1-AC01-01", B1)}}
        current = {"1-AC01-01": _rec("1-AC01-01", B2)}
        state = {"rounds": {1: {"score": 70.77}, 2: {"score": 93.44}},
                 "highest": 2, "improve_round_ran": True,
                 "current": {"round": 2, "score": 93.44}}
        jp, mp = rj.write_changes("US-1", "story", snapshot, current, state,
                                  {}, "sha256:d2", 70, "v1")
        doc = json.loads(jp.read_text(encoding="utf-8"))
        assert doc["to_digest"] == "sha256:d2" and doc["to"]["round"] == 2
        assert doc["delta"] == 22.67 and doc["regression_restored"] is False, doc
        assert doc["counts"]["changed"] == 1 and doc["from"]["label"] == "draft r0"
        md = mp.read_text(encoding="utf-8")
        assert "70.77" in md and "93.44" in md and "## Changed" in md and "Test Data" in md, md
        assert "-**A** = 1" in md and "+**A** = 2" in md, "section diffs are unified lines"
        # regression restore: current round below the highest
        state2 = dict(state, current={"round": 1, "score": 70.77},
                      rounds={1: {"score": 70.77}, 2: {"score": 60.0}})
        doc2 = json.loads(rj.write_changes("US-1", "story", snapshot, current, state2,
                                           {}, "sha256:d1", 70, "v1")[0].read_text(encoding="utf-8"))
        assert doc2["regression_restored"] is True and doc2["to"]["round"] == 1, doc2
    finally:
        rj.RUBRIC_BUILD = old_b
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric_diff OK")
