#!/usr/bin/env python3
"""The draft-first pipeline end to end over SYNTHETIC data
(run: py tools/test_pipeline_chain.py). Stands in for a smoke e2e that
cannot run against the tracked wiki without writing a real story's round
files (plan: Global Constraints). Every path is redirected to a temp dir."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
import wiki_export as wx  # noqa: E402
from eval_rubric import score_scope  # noqa: E402
from wiki_rubric import sealed_digest, tc_record  # noqa: E402
from wiki_suite import render_xlsx  # noqa: E402

BODY1 = ("# Objective\n\no\n\n# Preconditions\n\n1. p\n\n# Test Data\n\n**Amount** = 100\n\n"
         "# Steps\n\n1. Enter.\n\n# Expected Results\n\n1. Accepted.\n")
BODY2 = BODY1.replace("**Amount** = 100", "**Amount** = 1 (min)")
ITEMS = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary", "basis": ["S-AC1"], "feasible": True}]
STORY = {"type": "User Story", "id": "US-S", "title": "S",
         "acceptance_criteria": [{"id": "S-AC1", "text": "Accepted when 1 or more."}],
         "business_rules": [], "test_model": {"status": "confirmed", "items": ITEMS}}
MODULE = {"type": "Module", "id": "m", "title": "Mod"}


def _tc(tid, body, status="active"):
    fm = {"type": "Test Case", "id": tid, "status": status, "technique": "BVA",
          "title": tid, "priority": "P1", "module": "/modules/m.md", "kind": "sit",
          "covers": ["/stories/US-S.md#S-AC1"], "verifies_rules": [],
          "coverage_items": ["BVA-01"]}
    return f"testcases/sit/US-S/{tid}", fm, body


def _wiki(tcs):
    concepts = {"stories/US-S": (STORY, "", None), "modules/m": (MODULE, "", None)}
    hashes = {}
    for rel, fm, body in tcs:
        concepts[rel] = (fm, body, None)
        hashes[rel] = "sha256:" + str(abs(hash(body)))
    return concepts, {"tc_hashes": hashes}


def _judge(scope, rnd, lens, verdicts, h):
    rj.judgment_path(scope, rnd, lens).parent.mkdir(parents=True, exist_ok=True)
    rj.judgment_path(scope, rnd, lens).write_text(json.dumps(
        {"rubric_hash": h, "scope": scope, "round": rnd, "lens": lens,
         "verdicts": verdicts}), encoding="utf-8")


def _v(tc, dim, band):
    return {"tc": tc, "dimension": dim, "band": band, "rationale": "read it", "gap": ""}


def _hashes(base):
    return {t["id"]: base["_tc_hashes"].get(t["rel"]) for t in base["_tcs"]}


def _pack(load_all, rnd):
    """What `--round N --pack` records next to the packs (eval_rubric.main)."""
    base = score_scope("story", "US-S", load_all=load_all)
    return rj.write_packed("US-S", rnd, base["sealed_digest"], _hashes(base))


def _merge(load_all, rnd, judge_dims):
    base = score_scope("story", "US-S", load_all=load_all)
    cur = _hashes(base)
    # eval_rubric.main's merge path: refuse when the set moved since --pack
    rj.refuse_if_packed_changed("US-S", rnd, "--story", cur)
    per_tc, per_scope, notes, present = rj.load_judgments(
        "US-S", rnd, base["rubric_hash"], [t["id"] for t in base["_tcs"]],
        judge_dims, current_hashes=cur)
    res = score_scope("story", "US-S", load_all=load_all, judgments=per_tc,
                      scope_judgments=per_scope)
    res["round"] = rnd
    res["judges_present"] = sorted(present)
    res["judges_missing"] = sorted(set(rj.LENSES) - present)
    public = {k: v for k, v in res.items() if not k.startswith("_")}
    rj.score_path("US-S", rnd).write_text(json.dumps(public, indent=1), encoding="utf-8")
    return res, notes


def test_chain_draft_grade_carry_diff_final():
    d = Path(tempfile.mkdtemp(prefix="chain-"))
    old = (rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR)
    rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = d, d / "packs", d / "judgments"
    try:
        from rubric import dimensions
        # threshold 0: this test proves the CHAIN (draft -> carry -> diff ->
        # gated final), not the number a two-case synthetic set scores.
        cfg = {"rubric": {"threshold": 0, "version": "v1"},
               "ids": {"tc_format": "{story_num}-AC{ac_num:02d}-{seq:02d}", "story_prefix": "US-"}}
        # round 0: two cases rendered and sealed
        tcs0 = [_tc("S-AC01-01", BODY1), _tc("S-AC01-02", BODY1)]
        concepts0, manifest0 = _wiki(tcs0)
        export_tcs0 = [(r, f, b) for r, f, b in tcs0]
        digest0 = sealed_digest(manifest0["tc_hashes"], [r for r, _f, _b in tcs0])
        # 5 draft export
        render_xlsx(export_tcs0, "S", d / "draft.xlsx",
                    concepts={k: (v[0], v[1]) for k, v in concepts0.items()},
                    manifest=manifest0, draft=True)
        wx.write_draft_snapshot("US-S", "story", export_tcs0, manifest0, "draft.xlsx",
                                "sha", "v1", rj.draft_path("US-S"))
        assert wx.export_gate("US-S", "story", digest0, cfg)[1], "final refused before grading"
        # a flow's UAT case covering the story's AC is not part of the
        # story's set (I5): the rubric's digest must equal the export's
        uat_rel, uat_fm, uat_body = _tc("UAT-S-01", BODY1)
        uat_fm = dict(uat_fm, kind="uat")
        concepts0[uat_rel.replace("/sit/", "/uat/")] = (uat_fm, uat_body, None)
        # 6-7 round 1
        load0 = lambda: (concepts0, manifest0)
        assert rj.packed_path("US-S", 1).name == "US-S-r1-packed.json"
        _pack(load0, 1)
        base = score_scope("story", "US-S", load_all=load0)
        assert [t["id"] for t in base["_tcs"]] == ["S-AC01-01", "S-AC01-02"], base["_tcs"]
        judge_dims = {x["id"] for x in dimensions(base["_rub"]) if "judge" in x["scored"]}
        h = base["rubric_hash"]
        for lens, dims in (("A", ["T1.4", "T1.5"]), ("B", ["T1.7"]), ("C", ["T1.8"])):
            _judge("US-S", 1, lens, [_v(t, dm, 3) for t in ("S-AC01-01", "S-AC01-02") for dm in dims], h)
        _judge("US-S", 1, "D", [_v("scope", "T2.5", 3), _v("scope", "T2.6", 3)], h)
        r1, _notes1 = _merge(load0, 1, judge_dims)
        assert r1["partial"] is False and r1["sealed_digest"] == digest0
        # 8 the improver patched case 02 and added case 03
        tcs1 = [_tc("S-AC01-01", BODY1), _tc("S-AC01-02", BODY2), _tc("S-AC01-03", BODY2)]
        concepts1, manifest1 = _wiki(tcs1)
        load1 = lambda: (concepts1, manifest1)
        rj.patch_path("US-S", 1).write_text(json.dumps({"scope": "US-S", "round": 1, "patches": [
            {"op": "set", "ac": "AC1", "seq": 2, "field": "data", "value": "x", "closes": "G3.1"},
            {"op": "add", "closes": "G1.1", "test_case": {"ac": "AC1", "seq": 3}}]}), encoding="utf-8")
        # 9 round 2 pack with carry-forward
        base2 = score_scope("story", "US-S", load_all=load1)
        carried = rj.carry_forward("US-S", 2, base2["_tcs"], base2["_tc_hashes"], h, judge_dims)
        assert carried == {"A": ["S-AC01-01"], "B": ["S-AC01-01"], "C": ["S-AC01-01"]}, carried
        base2["round"] = 2
        rj.write_packs(base2, base2["_tcs"], base2["_fm"], base2["_rub"], 2, base2["_mech_by_tc"], exclude=carried)
        _pack(load1, 2)
        a = (d / "packs" / "US-S-r2-A.md").read_text(encoding="utf-8")
        assert "### S-AC01-01" not in a and "### S-AC01-02" in a and "### S-AC01-03" in a, a
        for lens, dims in (("A", ["T1.4", "T1.5"]), ("B", ["T1.7"]), ("C", ["T1.8"])):
            _judge("US-S", 2, lens, [_v(t, dm, 4) for t in ("S-AC01-02", "S-AC01-03") for dm in dims], h)
        _judge("US-S", 2, "D", [_v("scope", "T2.5", 4), _v("scope", "T2.6", 4)], h)
        # a set that moved after --pack (case 03 edited again) refuses the merge
        tcs_moved = tcs1[:2] + [_tc("S-AC01-03", BODY2 + "\n")]
        concepts_m, manifest_m = _wiki(tcs_moved)
        try:
            _merge(lambda: (concepts_m, manifest_m), 2, judge_dims)
        except SystemExit as e:
            assert "changed since the round 2 packs were written (1 test case(s))" in str(e), e
        else:
            raise AssertionError("a merge after the set moved since --pack must refuse")
        assert not rj.score_path("US-S", 2).exists(), "the refused merge wrote nothing"
        r2, notes2 = _merge(load1, 2, judge_dims)
        assert r2["partial"] is False, "carried verdicts complete lens A/B/C for case 01"
        assert rj.carried_counts(notes2) == {"A": 1, "B": 1, "C": 1}
        digest1 = r2["sealed_digest"]
        # 11 diff
        state = rj.rubric_state("US-S", digest1, 0, "v1")
        assert state["current"] == {"round": 2, "score": r2["score"]}, state
        current = {fm["id"]: tc_record(rel, fm, body, manifest1["tc_hashes"]) for rel, fm, body in tcs1}
        snapshot = json.loads(rj.draft_path("US-S").read_text(encoding="utf-8"))
        cause = rj.patch_tc_index("US-S", "story", json.loads(rj.patch_path("US-S", 1).read_text(encoding="utf-8")), cfg)
        jp, _mp = rj.write_changes("US-S", "story", snapshot, current, state, cause, digest1, 0, "v1")
        doc = json.loads(jp.read_text(encoding="utf-8"))
        assert doc["counts"] == {"added": 1, "changed": 1, "removed": 0, "unchanged": 1}, doc["counts"]
        td = next(c for c in doc["changes"] if c["kind"] == "changed" and c["field"] == "Test Data")
        assert td["closes"] == "G3.1", td
        # 12 final export gate + workbook
        cur, err = wx.export_gate("US-S", "story", digest1, cfg)
        assert cur == {"round": 2, "score": r2["score"]} and err is None, err
        render_xlsx([(r, f, b) for r, f, b in tcs1], "S", d / "final.xlsx",
                    concepts={k: (v[0], v[1]) for k, v in concepts1.items()}, manifest=manifest1,
                    grade={"round": 2, "score": r2["score"], "threshold": 0, "version": "v1"},
                    changes=wx.changes_for(digest1, doc))
        from openpyxl import load_workbook
        log = load_workbook(d / "final.xlsx")["Change Log"]
        assert log["C2"].value.startswith("Graded round 2:"), log["C2"].value
        assert log["C3"].value.startswith("Changed Test Data"), log["C3"].value
        assert "Added" in log["C4"].value, log["C4"].value
    finally:
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = old
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_pipeline_chain OK")
