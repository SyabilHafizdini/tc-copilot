#!/usr/bin/env python3
"""Plain-assert tests for tools/rubric_judge.py (run: py
tools/test_rubric_judge.py). No pytest - matches tools/smoke.py.

Verdict files, packs and gap reports live in gitignored build/; these write
under a throwaway directory and delete it. No tracked state is touched.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
from eval_rubric import NOT_ASSESSED, combine, score_scope  # noqa: E402

HASH = "sha256:test"
JUDGE_DIMS = {"T1.4", "T1.5", "T1.7", "T1.8", "T2.5", "T2.6"}


def _tmpdir():
    return Path(tempfile.mkdtemp(prefix="rj-"))


def _write(jdir, scope, rnd, lens, verdicts, **over):
    d = {"rubric_hash": HASH, "scope": scope, "round": rnd, "lens": lens,
         "verdicts": verdicts}
    d.update(over)
    p = jdir / f"{scope}-r{rnd}-{lens}.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def _v(tc, dim, band, rationale="because", gap=""):
    return {"tc": tc, "dimension": dim, "band": band,
            "rationale": rationale, "gap": gap}


def _load(jdir, scope="US-J", rnd=1, tcs=("TC-1", "TC-2")):
    return rj.load_judgments(scope, rnd, HASH, tcs, JUDGE_DIMS,
                             judgment_dir=jdir)


def _refused(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


# ------------------------------------------------------------ loading
def test_missing_files_are_not_an_error():
    d = _tmpdir()
    try:
        per_tc, per_scope, notes, present = _load(d)
        assert per_tc == {} and per_scope == {} and present == set()
    finally:
        shutil.rmtree(d)


def test_a_valid_tier1_verdict_lands_on_its_test_case():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-1", "T1.5", 3, gap="say the state")])
        per_tc, per_scope, notes, present = _load(d)
        assert per_tc == {"TC-1": {"T1.5": 3}}, per_tc
        assert notes[("TC-1", "T1.5")]["gap"] == "say the state"
        assert present == {"A"}
    finally:
        shutil.rmtree(d)


def test_a_tier2_verdict_applies_to_the_scope():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "D", [_v("scope", "T2.5", 2), _v(None, "T2.6", 1)])
        _per_tc, per_scope, _n, _p = _load(d)
        assert per_scope == {"T2.5": 2, "T2.6": 1}, per_scope
    finally:
        shutil.rmtree(d)


def test_wrong_rubric_hash_is_rejected_not_dropped():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-1", "T1.5", 3)], rubric_hash="sha256:old")
        msg = _refused(lambda: _load(d))
        assert msg and "rubric_hash" in msg, msg
    finally:
        shutil.rmtree(d)


def test_unknown_test_case_is_rejected():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-GHOST", "T1.5", 3)])
        msg = _refused(lambda: _load(d))
        assert msg and "TC-GHOST" in msg, msg
    finally:
        shutil.rmtree(d)


def test_a_lens_may_only_judge_its_own_dimensions():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-1", "T1.8", 3)])  # T1.8 is lens C
        msg = _refused(lambda: _load(d))
        assert msg and "not judged by lens A" in msg, msg
    finally:
        shutil.rmtree(d)


def test_mech_only_dimension_is_rejected_even_from_the_right_lens():
    """T1.3 is mechanical. Lens B SEES its evidence but must not band it;
    a verdict on it would let a judge overwrite objective evidence."""
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "B", [_v("TC-1", "T1.3", 4)])
        msg = _refused(lambda: _load(d))
        assert msg and "T1.3" in msg, msg
    finally:
        shutil.rmtree(d)


def test_band_out_of_range_and_missing_rationale_are_rejected():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-1", "T1.5", 5),
                                   _v("TC-2", "T1.5", 2, rationale="")])
        msg = _refused(lambda: _load(d))
        assert msg and "0-4" in msg and "rationale" in msg, msg
    finally:
        shutil.rmtree(d)


def test_duplicate_verdict_is_rejected():
    d = _tmpdir()
    try:
        _write(d, "US-J", 1, "A", [_v("TC-1", "T1.5", 3), _v("TC-1", "T1.5", 4)])
        msg = _refused(lambda: _load(d))
        assert msg and "duplicate" in msg, msg
    finally:
        shutil.rmtree(d)


# ------------------------------------------------------- T2.5 ceiling
def _tc(technique="UC", title="Do the thing", data="**A** = 1",
        objective="Verify it works"):
    return {"id": "TC-x", "technique": technique, "title": title,
            "body": (f"# Objective\n\n{objective}\n\n# Test Data\n\n{data}\n\n"
                     f"# Steps\n\n1. Go.\n\n# Expected Results\n\n1. Done.\n")}


def test_t25_ceiling_is_zero_with_no_negative_case():
    assert rj.t25_ceiling([_tc(), _tc()]) == 0


def test_t25_ceiling_is_four_with_an_err_case():
    assert rj.t25_ceiling([_tc(), _tc(technique="ERR")]) == 4


def test_t25_ceiling_recognises_an_invalid_input():
    assert rj.t25_ceiling([_tc(data="**Amount** = -1 (invalid)")]) == 4


def test_t25_ceiling_recognises_a_rejection_title():
    assert rj.t25_ceiling([_tc(title="Save is rejected for a duplicate ship")]) == 4


def test_a_set_with_no_negative_case_scores_strictly_less():
    """The invariant from spec 4: a detected defect must cost something.
    T2.5 ceiling 0 is a measurement, so the all-valid set scores lower than
    the same set plus one negative case even without a lens-D verdict."""
    assert combine(0, None) == 0
    assert combine(4, None) == NOT_ASSESSED


# ------------------------------------------------------- apply_patch
def _spec():
    return {"story": "/stories/US-J.md", "module": "/modules/M.md",
            "figma": None, "out": "testcases/sit/US-J", "ac_prefix": "J",
            "scenario_id": "SIT-{ac_id}-{seq:02d}", "generator_version": "sit-1.0",
            "pre_common": "signed in", "post_default": "none",
            "test_cases": [
                {"ac": "AC1", "seq": 1, "technique": "UC", "priority": "P1",
                 "area": "A", "title": "t", "objective": "o",
                 "data": "**A** = 1", "steps": "1. go", "expected": "1. ok"}]}


def test_apply_patch_sets_a_field_and_adds_a_case():
    import yaml
    d = _tmpdir()
    try:
        sp = d / "US-J.yaml"
        sp.write_text(yaml.safe_dump(_spec(), sort_keys=False), encoding="utf-8")
        pf = d / "patch.json"
        pf.write_text(json.dumps({"patches": [
            {"op": "set", "ac": "AC1", "seq": 1, "field": "expected",
             "value": "1. The record shows status Saved.", "closes": "G3.1"},
            {"op": "add", "closes": "G1.1", "test_case": {
                "ac": "AC1", "seq": 2, "technique": "BVA", "priority": "P2",
                "area": "A", "title": "b", "objective": "o", "data": "**A** = 0",
                "steps": "1. go", "expected": "1. rejected",
                "coverage_items": ["BVA-01"]}}]}), encoding="utf-8")
        n, errs = rj.apply_patch(sp, pf)
        assert errs == [] and n == 2, (n, errs)
        out = yaml.safe_load(sp.read_text(encoding="utf-8"))
        assert out["test_cases"][0]["expected"].startswith("1. The record")
        assert out["test_cases"][1]["coverage_items"] == ["BVA-01"]
    finally:
        shutil.rmtree(d)


def test_apply_patch_writes_nothing_when_any_patch_is_bad():
    import yaml
    d = _tmpdir()
    try:
        sp = d / "US-J.yaml"
        before = yaml.safe_dump(_spec(), sort_keys=False)
        sp.write_text(before, encoding="utf-8")
        pf = d / "patch.json"
        pf.write_text(json.dumps({"patches": [
            {"op": "set", "ac": "AC1", "seq": 1, "field": "expected", "value": "x"},
            {"op": "set", "ac": "AC9", "seq": 1, "field": "expected", "value": "y"},
            {"op": "set", "ac": "AC1", "seq": 1, "field": "scenario_id", "value": "z"},
        ]}), encoding="utf-8")
        n, errs = rj.apply_patch(sp, pf)
        assert n == 0 and len(errs) == 2, (n, errs)
        assert sp.read_text(encoding="utf-8") == before, "spec must be untouched"
    finally:
        shutil.rmtree(d)


# ------------------------------------------------ score_scope with judges
def _story_fm(items):
    return {"type": "User Story", "id": "US-S",
            "acceptance_criteria": [{"id": "S-AC1"}], "business_rules": [],
            "test_model": {"status": "confirmed", "items": items}}


def _tc_fm(tc_id, technique="BVA", items=("BVA-01",), title="t"):
    return {"type": "Test Case", "id": tc_id, "status": "active",
            "technique": technique, "title": title,
            "covers": ["/stories/US-S.md#S-AC1"], "verifies_rules": [],
            "coverage_items": list(items)}


BODY = ("# Objective\n\no\n\n# Preconditions\n\n1. p\n\n# Test Data\n\n"
        "**Amount** = 100\n\n# Steps\n\n1. Enter.\n\n# Expected Results\n\n"
        "1. Accepted.\n")


def _load_all():
    items = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary",
              "basis": ["S-AC1"], "feasible": True}]
    return ({"stories/US-S": (_story_fm(items), "", None),
             "testcases/sit/US-S/TC-1": (_tc_fm("TC-1"), BODY, None)}, {})


def test_scope_judgments_reach_tier2():
    a = score_scope("story", "US-S", load_all=_load_all)
    assert a["tier2_bands"]["T2.6"] == NOT_ASSESSED
    hi = score_scope("story", "US-S", load_all=_load_all,
                     scope_judgments={"T2.6": 4})
    lo = score_scope("story", "US-S", load_all=_load_all,
                     scope_judgments={"T2.6": 0})
    assert hi["tier2_bands"]["T2.6"] == 4 and lo["tier2_bands"]["T2.6"] == 0
    # A measured 4 never lowers the tier; a measured 0 must cost something.
    assert hi["tier2"] >= a["tier2"] > lo["tier2"], (a["tier2"], hi["tier2"], lo["tier2"])


def test_t25_is_measured_zero_for_an_all_valid_set_without_a_judge():
    a = score_scope("story", "US-S", load_all=_load_all)
    assert a["tier2_bands"]["T2.5"] == 0, a["tier2_bands"]
    assert a["t25_ceiling"] == 0


def test_result_carries_private_material_for_packs_and_gaps():
    a = score_scope("story", "US-S", load_all=_load_all)
    assert a["_tcs"][0]["id"] == "TC-1"
    assert "T1.1" in a["_mech_by_tc"]["TC-1"]


# ------------------------------------------------------ packs + gaps
def test_packs_and_gap_report_are_written_for_every_lens():
    res = score_scope("story", "US-S", load_all=_load_all)
    res["round"] = 1
    old_pack, old_build = rj.PACK_DIR, rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.PACK_DIR = d / "packs"
        rj.RUBRIC_BUILD = d
        paths = rj.write_packs(res, res["_tcs"], res["_fm"], res["_rub"], 1,
                               res["_mech_by_tc"])
        assert len(paths) == 4, paths
        a_pack = (d / "packs" / "US-S-r1-A.md").read_text(encoding="utf-8")
        assert "T1.5" in a_pack and "TC-1" in a_pack and res["rubric_hash"] in a_pack
        assert "Expected Results" in a_pack
        d_pack = (d / "packs" / "US-S-r1-D.md").read_text(encoding="utf-8")
        assert "T2.5" in d_pack and "| TC-1 |" in d_pack
        gp = rj.write_gaps(res, res["_tcs"], res["_fm"], {}, 1, res["_mech_by_tc"])
        txt = gp.read_text(encoding="utf-8")
        assert "G1" in txt and "T2.5" in txt, txt
    finally:
        rj.PACK_DIR, rj.RUBRIC_BUILD = old_pack, old_build
        shutil.rmtree(d)


def test_gap_report_lists_an_uncovered_feasible_item():
    def load_all():
        items = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary",
                  "basis": ["S-AC1"], "feasible": True},
                 {"id": "BVA-02", "technique": "BVA", "kind": "boundary",
                  "subject": "Amount", "desc": "upper bound",
                  "basis": ["S-AC1"], "feasible": True},
                 {"id": "EP-09", "technique": "EP", "kind": "partition",
                  "basis": ["S-AC1"], "feasible": False,
                  "justification": "needs prod data"}]
        return ({"stories/US-S": (_story_fm(items), "", None),
                 "testcases/sit/US-S/TC-1": (_tc_fm("TC-1"), BODY, None)}, {})
    res = score_scope("story", "US-S", load_all=load_all)
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        txt = rj.write_gaps(res, res["_tcs"], res["_fm"], {}, 1,
                            res["_mech_by_tc"]).read_text(encoding="utf-8")
        assert "BVA-02" in txt and "upper bound" in txt, txt
        assert "EP-09" not in txt.split("## G2")[0], "infeasible items are not gaps"
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


# ---------------------------------------------------------- round delta
def test_round_delta_flags_a_regression():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        (d / "US-S-r1-score.json").write_text(
            json.dumps({"score": 80.0, "rubric_hash": HASH}), encoding="utf-8")
        (d / "US-S-r2-score.json").write_text(
            json.dumps({"score": 75.5, "rubric_hash": HASH}), encoding="utf-8")
        dl = rj.round_delta("US-S", 2)
        assert dl["regression"] is True and dl["delta"] == -4.5, dl
        assert rj.round_delta("US-S", 1) is None
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_round_delta_is_not_comparable_across_rubric_hashes():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        (d / "US-S-r1-score.json").write_text(
            json.dumps({"score": 80.0, "rubric_hash": "sha256:a"}), encoding="utf-8")
        (d / "US-S-r2-score.json").write_text(
            json.dumps({"score": 90.0, "rubric_hash": "sha256:b"}), encoding="utf-8")
        assert rj.round_delta("US-S", 2)["same_rubric"] is False
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


# ------------------------------------------------ sealed hash + digest
from wiki_rubric import sealed_digest  # noqa: E402


def _load_all_hashed():
    items = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary",
              "basis": ["S-AC1"], "feasible": True}]
    stale = dict(_tc_fm("TC-2"), status="stale")
    return ({"stories/US-S": (_story_fm(items), "", None),
             "testcases/sit/US-S/TC-1": (_tc_fm("TC-1"), BODY, None),
             "testcases/sit/US-S/TC-2": (stale, BODY, None)},
            {"tc_hashes": {"testcases/sit/US-S/TC-1": "sha256:aaa",
                           "testcases/sit/US-S/TC-2": "sha256:bbb"}})


def test_score_records_carry_the_sealed_hash_and_rel():
    res = score_scope("story", "US-S", load_all=_load_all_hashed)
    by = {r["id"]: r for r in res["test_cases"]}
    assert by["TC-1"]["sealed_hash"] == "sha256:aaa", by
    assert by["TC-2"]["sealed_hash"] == "sha256:bbb", by
    assert all(t.get("rel") for t in res["_tcs"]), "records need rel"
    assert res["_tc_hashes"] == _load_all_hashed()[1]["tc_hashes"]


def test_sealed_digest_covers_active_cases_only():
    """A stale case is still SCORED (it exists), but the digest identifies the
    active set an export would ship - otherwise every correction that stales
    one case would make the final export refuse on a digest mismatch."""
    res = score_scope("story", "US-S", load_all=_load_all_hashed)
    h = _load_all_hashed()[1]["tc_hashes"]
    assert res["sealed_digest"] == sealed_digest(h, ["testcases/sit/US-S/TC-1"]), res["sealed_digest"]
    assert {r["id"] for r in res["test_cases"]} == {"TC-1", "TC-2"}


# ------------------------------------------------ rubric_state
def _score_file(d, scope, n, score, digest, partial=False, version="v1"):
    (d / f"{scope}-r{n}-score.json").write_text(json.dumps(
        {"score": score, "partial": partial, "sealed_digest": digest,
         "rubric_version": version, "rubric_hash": HASH}), encoding="utf-8")


def test_rubric_state_picks_the_highest_current_round_at_threshold():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 70.77, "sha256:old")
        _score_file(d, "US-S", 2, 93.44, "sha256:cur")
        st = rj.rubric_state("US-S", "sha256:cur", 70, "v1")
        assert st["highest"] == 2 and st["improve_round_ran"] is True, st
        assert st["current"] == {"round": 2, "score": 93.44}, st
        assert set(st["rounds"]) == {1, 2}
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_rubric_state_regression_restore_falls_back_to_round_one():
    """Round 2 regressed and round 1's spec was restored: the sealed set is
    round 1's content again, so round 1 is the current score."""
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 80.0, "sha256:r1")
        _score_file(d, "US-S", 2, 75.0, "sha256:r2")
        st = rj.rubric_state("US-S", "sha256:r1", 70, "v1")
        assert st["current"] == {"round": 1, "score": 80.0}, st
        assert st["improve_round_ran"] is True
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_rubric_state_has_no_current_when_partial_below_threshold_or_other_rubric():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 95.0, "sha256:cur", partial=True)
        _score_file(d, "US-S", 2, 60.0, "sha256:cur")
        _score_file(d, "US-S", 3, 99.0, "sha256:cur", version="v0")
        st = rj.rubric_state("US-S", "sha256:cur", 70, "v1")
        assert st["current"] is None and st["highest"] == 3, st
        assert rj.rubric_state("US-NONE", "x", 70, "v1")["rounds"] == {}
        assert rj.draft_path("US-S") == d / "US-S-draft.json"
        assert rj.changes_path("US-S", "md") == d / "US-S-changes.md"
        assert rj.carried_path("US-S", 2, "A").name == "US-S-r2-A.carried.json"
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric_judge OK")
