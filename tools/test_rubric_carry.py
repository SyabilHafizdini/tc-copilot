#!/usr/bin/env python3
"""Plain-assert tests for round-N carry-forward of unchanged verdicts
(run: py tools/test_rubric_carry.py). No pytest - matches tools/smoke.py.
Everything under a throwaway build dir."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402

HASH = "sha256:test"
JUDGE_DIMS = {"T1.4", "T1.5", "T1.7", "T1.8", "T2.5", "T2.6"}


def _v(tc, dim, band, rationale="because", gap=""):
    return {"tc": tc, "dimension": dim, "band": band,
            "rationale": rationale, "gap": gap}


def _judgment(d, scope, rnd, lens, verdicts):
    (d / "judgments").mkdir(parents=True, exist_ok=True)
    (d / "judgments" / f"{scope}-r{rnd}-{lens}.json").write_text(json.dumps(
        {"rubric_hash": HASH, "scope": scope, "round": rnd, "lens": lens,
         "verdicts": verdicts}), encoding="utf-8")


def _score(d, scope, rnd, hashes):
    (d / f"{scope}-r{rnd}-score.json").write_text(json.dumps(
        {"score": 80.0, "rubric_hash": HASH, "partial": False,
         "test_cases": [{"id": t, "sealed_hash": h} for t, h in hashes.items()]}),
        encoding="utf-8")


def _tcs(hashes):
    return [{"id": t, "rel": f"testcases/sit/S/{t}", "status": "active",
             "title": t, "technique": "BVA", "coverage_items": ["BVA-01"],
             "covers": [], "verifies_rules": [], "body": ""}
            for t in hashes]


class _Redirect:
    def __enter__(self):
        self.d = Path(tempfile.mkdtemp(prefix="carry-"))
        self.old = (rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR)
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = \
            self.d, self.d / "packs", self.d / "judgments"
        return self.d

    def __exit__(self, *a):
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = self.old
        shutil.rmtree(self.d)


def test_carry_forward_copies_verdicts_only_for_unchanged_hashes():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-1", "T1.5", 4),
                                      _v("TC-2", "T1.4", 2), _v("TC-2", "T1.5", 2)])
        _judgment(d, "US-S", 1, "D", [_v("scope", "T2.5", 3), _v("scope", "T2.6", 3)])
        cur = {"testcases/sit/S/TC-1": "sha256:a",       # unchanged
               "testcases/sit/S/TC-2": "sha256:b2",      # patched
               "testcases/sit/S/TC-3": "sha256:c"}       # added by the patch
        carried = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0, "TC-3": 0}),
                                   cur, HASH, JUDGE_DIMS)
        assert carried == {"A": ["TC-1"]}, carried
        cf = json.loads(rj.carried_path("US-S", 2, "A").read_text(encoding="utf-8"))
        assert cf["round"] == 2 and cf["lens"] == "A"
        assert {(v["tc"], v["dimension"], v["carried_from"]) for v in cf["verdicts"]} \
            == {("TC-1", "T1.4", 1), ("TC-1", "T1.5", 1)}, cf
        assert not rj.carried_path("US-S", 2, "D").exists(), "lens D is never carried"
        assert not rj.carried_path("US-S", 2, "B").exists(), "no round-1 B file -> nothing"


def test_carry_forward_is_empty_when_round_one_has_no_hashes():
    """A round-1 score written before sealed_hash existed carries nothing and
    must not crash: full packs, as before."""
    with _Redirect() as d:
        (d / "US-S-r1-score.json").write_text(json.dumps(
            {"score": 80.0, "rubric_hash": HASH,
             "test_cases": [{"id": "TC-1"}]}), encoding="utf-8")
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3)])
        assert rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                                {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS) == {}
        assert rj.carry_forward("US-S", 1, [], {}, HASH, JUDGE_DIMS) == {}, "round 1 never carries"


def test_carry_forward_refuses_an_invalid_previous_verdict_file():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.7", 3)])   # T1.7 is lens B's
        try:
            rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                             {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS)
        except SystemExit as e:
            assert "REFUSED" in str(e), e
        else:
            raise AssertionError("an invalid round-1 verdict must never be carried")


def test_packs_exclude_carried_cases_and_say_so():
    with _Redirect() as d:
        result = {"scope": "US-S", "rubric_version": "v1", "rubric_hash": HASH,
                  "standard": "s", "coverage": {}, "t25_ceiling": 4,
                  "model_warnings": [], "unknown_item_refs": []}
        from rubric import load_rubric
        rub = load_rubric("v1")
        fm = {"acceptance_criteria": [], "business_rules": [],
              "test_model": {"items": [{"id": "BVA-01", "technique": "BVA",
                                        "kind": "boundary", "basis": []}]}}
        tcs = _tcs({"TC-1": 0, "TC-2": 0})
        rj.write_packs(result, tcs, fm, rub, 2, {}, exclude={"A": {"TC-1"}, "B": {"TC-1", "TC-2"}})
        a = (d / "packs" / "US-S-r2-A.md").read_text(encoding="utf-8")
        assert "Carried forward from round 1: 1 test case(s)" in a, a
        assert "### TC-2" in a and "### TC-1" not in a, a
        b = (d / "packs" / "US-S-r2-B.md").read_text(encoding="utf-8")
        assert "Nothing to judge for this lens this round" in b and "### TC-" not in b, b
        c = (d / "packs" / "US-S-r2-C.md").read_text(encoding="utf-8")
        assert "### TC-1" in c and "### TC-2" in c, "lens C had nothing excluded"
        dd = (d / "packs" / "US-S-r2-D.md").read_text(encoding="utf-8")
        assert "| TC-1 |" in dd and "| TC-2 |" in dd, "lens D always sees the whole set"


def test_load_judgments_merges_carried_verdicts_and_marks_the_lens_present():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-2", "T1.4", 2)])
        cur = {"testcases/sit/S/TC-1": "sha256:a", "testcases/sit/S/TC-2": "sha256:b2"}
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0}), cur, HASH, JUDGE_DIMS)
        _judgment(d, "US-S", 2, "A", [_v("TC-2", "T1.4", 4)])
        per_tc, _ps, notes, present = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1", "TC-2"], JUDGE_DIMS,
            current_hashes={"TC-1": "sha256:a", "TC-2": "sha256:b2"})
        assert per_tc == {"TC-1": {"T1.4": 3}, "TC-2": {"T1.4": 4}}, per_tc
        assert notes[("TC-1", "T1.4")].get("carried_from") == 1, notes
        assert "A" in present
        assert rj.carried_counts(notes) == {"A": 1}


def test_fresh_verdict_wins_over_a_carried_one():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        _judgment(d, "US-S", 2, "A", [_v("TC-1", "T1.4", 4, rationale="re-read")])
        per_tc, _ps, notes, _pr = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:a"})
        assert per_tc == {"TC-1": {"T1.4": 4}}, "a fresh read is always allowed and wins"
        assert "carried_from" not in notes[("TC-1", "T1.4")]


def test_carried_verdict_is_dropped_when_the_hash_moved_since():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        # the file changed AFTER the carry (e.g. a forced re-render): honest reading
        per_tc, _ps, _n, present = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:zzz"})
        assert per_tc == {}, per_tc
        assert "A" in present, "the lens ran; its verdict just no longer applies"


def test_carried_file_with_a_bad_verdict_is_a_hard_refusal():
    with _Redirect() as d:
        (d / "judgments").mkdir()
        rj.carried_path("US-S", 2, "A").write_text(json.dumps(
            {"rubric_hash": HASH, "scope": "US-S", "round": 2, "lens": "A",
             "verdicts": [dict(_v("TC-1", "T1.4", 3), carried_from="one")]}),
            encoding="utf-8")
        try:
            rj.load_judgments("US-S", 2, HASH, ["TC-1"], JUDGE_DIMS)
        except SystemExit as e:
            assert "carried_from" in str(e), e
        else:
            raise AssertionError("a malformed carried verdict must be refused")


def test_a_dropped_carried_verdict_is_not_recarried_next_round():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        # round 2's content moved on (a -> a2): the round 2 merge drops the
        # carried verdict, and round 2's own sealed score reflects a2.
        rj.load_judgments("US-S", 2, HASH, ["TC-1"], JUDGE_DIMS,
                          current_hashes={"TC-1": "sha256:a2"})
        _score(d, "US-S", 2, {"TC-1": "sha256:a2"})
        out = rj.carry_forward("US-S", 3, _tcs({"TC-1": 0}),
                               {"testcases/sit/S/TC-1": "sha256:a2"}, HASH, JUDGE_DIMS)
        assert out == {}, "a verdict dropped once must never be re-carried"
        assert not rj.carried_path("US-S", 3, "A").exists()


def test_carry_forward_removes_a_stale_carried_file():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2), _v("TC-1", "T1.5", 2)])
        first = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                                 {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS)
        assert first == {"A": ["TC-1"]}, first
        assert rj.carried_path("US-S", 2, "A").exists()
        # TC-1 retired: no longer in the active set at all
        second = rj.carry_forward("US-S", 2, [], {}, HASH, JUDGE_DIMS)
        assert second == {}, second
        assert not rj.carried_path("US-S", 2, "A").exists(), \
            "a stale carried file must not survive a carry that keeps nothing"


def test_carried_counts_excludes_dropped_verdicts():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        _pt, _ps, notes, _pr = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:zzz"})
        assert rj.carried_counts(notes) == {}, notes


def test_carry_forward_carries_nothing_across_a_rubric_change():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})   # sealed under HASH
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        out = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                               {"testcases/sit/S/TC-1": "sha256:a"},
                               "sha256:other-rubric", JUDGE_DIMS)
        assert out == {}, out
        assert not rj.carried_path("US-S", 2, "A").exists()


def test_chained_carry_preserves_the_origin_round():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2), _v("TC-1", "T1.5", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        per_tc, _ps, _notes, _pr = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:a"})
        assert per_tc == {"TC-1": {"T1.4": 2, "T1.5": 2}}, per_tc
        _score(d, "US-S", 2, {"TC-1": "sha256:a"})
        out = rj.carry_forward("US-S", 3, _tcs({"TC-1": 0}),
                               {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS)
        assert out == {"A": ["TC-1"]}, out
        cf = json.loads(rj.carried_path("US-S", 3, "A").read_text(encoding="utf-8"))
        assert {v["carried_from"] for v in cf["verdicts"]} == {1}, cf


# ------------------------------------------------ final-review fix wave
def test_a_partly_carried_case_stays_in_the_lens_pack():
    """M7: a test case leaves a lens's pack only when EVERY dimension of that
    lens was carried for it; a partial carry is still written (a fresh
    verdict wins over it) but the judge re-reads the case."""
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3),                      # T1.5 missing
                                      _v("TC-2", "T1.4", 3), _v("TC-2", "T1.5", 3)])
        out = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0}),
                               {"testcases/sit/S/TC-1": "sha256:a",
                                "testcases/sit/S/TC-2": "sha256:b"}, HASH, JUDGE_DIMS)
        assert out == {"A": ["TC-2"]}, out
        cf = json.loads(rj.carried_path("US-S", 2, "A").read_text(encoding="utf-8"))
        assert {(v["tc"], v["dimension"]) for v in cf["verdicts"]} == \
            {("TC-1", "T1.4"), ("TC-2", "T1.4"), ("TC-2", "T1.5")}, cf


def test_carry_forward_validates_every_previous_record_id():
    """M5: a round-1 record without a sealed_hash is still a test case of that
    round; its verdict is valid (not 'not an active test case') and simply
    not carried."""
    with _Redirect() as d:
        (d / "US-S-r1-score.json").write_text(json.dumps(
            {"score": 80.0, "rubric_hash": HASH,
             "test_cases": [{"id": "TC-1", "sealed_hash": "sha256:a"}, {"id": "TC-2"}]}),
            encoding="utf-8")
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-1", "T1.5", 3),
                                      _v("TC-2", "T1.4", 3), _v("TC-2", "T1.5", 3)])
        out = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0}),
                               {"testcases/sit/S/TC-1": "sha256:a",
                                "testcases/sit/S/TC-2": "sha256:b"}, HASH, JUDGE_DIMS)
        assert out == {"A": ["TC-1"]}, out


def test_a_duplicate_inside_a_carried_file_is_a_hard_refusal():
    """M6: only a fresh-over-carried duplicate is the silent win."""
    with _Redirect() as d:
        (d / "judgments").mkdir()
        rj.carried_path("US-S", 2, "A").write_text(json.dumps(
            {"rubric_hash": HASH, "scope": "US-S", "round": 2, "lens": "A",
             "verdicts": [dict(_v("TC-1", "T1.4", 3), carried_from=1),
                          dict(_v("TC-1", "T1.4", 2), carried_from=1)]}),
            encoding="utf-8")
        try:
            rj.load_judgments("US-S", 2, HASH, ["TC-1"], JUDGE_DIMS)
        except SystemExit as e:
            assert "duplicate verdict for (TC-1, T1.4)" in str(e), e
            assert "carried.json" in str(e), e
        else:
            raise AssertionError("a duplicate inside a carried file must be refused")


def test_a_fresh_duplicate_is_still_a_hard_refusal():
    with _Redirect() as d:
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-1", "T1.4", 2)])
        try:
            rj.load_judgments("US-S", 1, HASH, ["TC-1"], JUDGE_DIMS)
        except SystemExit as e:
            assert "duplicate verdict for (TC-1, T1.4)" in str(e), e
        else:
            raise AssertionError("a duplicate fresh verdict must be refused")


def test_pack_writes_the_packed_hashes():
    with _Redirect() as d:
        p = rj.write_packed("US-S", 2, "sha256:digest", {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        assert p == rj.packed_path("US-S", 2) == d / "US-S-r2-packed.json", p
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc == {"scope": "US-S", "round": 2, "sealed_digest": "sha256:digest",
                       "hashes": {"TC-1": "sha256:a", "TC-2": "sha256:b"}}, doc


def test_merge_refuses_when_the_set_changed_since_pack():
    with _Redirect() as d:
        # legacy round (no packed file): the check is skipped
        assert rj.packed_mismatch("US-S", 2, {"TC-1": "sha256:zzz"}) == []
        rj.refuse_if_packed_changed("US-S", 2, "--story", {"TC-1": "sha256:zzz"})
        rj.write_packed("US-S", 2, "sha256:d", {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        same = {"TC-1": "sha256:a", "TC-2": "sha256:b"}
        assert rj.packed_mismatch("US-S", 2, same) == []
        rj.refuse_if_packed_changed("US-S", 2, "--story", same)       # no exit
        moved = {"TC-1": "sha256:a", "TC-2": "sha256:b2", "TC-3": "sha256:c"}
        assert rj.packed_mismatch("US-S", 2, moved) == ["TC-2", "TC-3"]
        assert rj.packed_mismatch("US-S", 2, {"TC-1": "sha256:a"}) == ["TC-2"], "a dropped case"
        try:
            rj.refuse_if_packed_changed("US-S", 2, "--story", moved)
        except SystemExit as e:
            msg = str(e)
            assert msg.startswith("eval_rubric REFUSED: the sealed set of US-S changed "
                                  "since the round 2 packs were written (2 test case(s))."), msg
            assert "Verdicts describe the content the judges read." in msg, msg
            assert "Next: py tools/eval_rubric.py --story US-S --round 2 --pack" in msg, msg
        else:
            raise AssertionError("a merge on a set that moved since --pack must refuse")
        (d / "US-S-r2-packed.json").write_text("[]", encoding="utf-8")
        try:
            rj.packed_mismatch("US-S", 2, same)
        except SystemExit as e:
            assert "US-S-r2-packed.json" in str(e), e
        else:
            raise AssertionError("a malformed packed file is a refusal, not a traceback")


def test_score_rounds_refuses_a_malformed_score_file():
    """M4: `wiki next` reads every scope's rounds; a broken file is a
    refusal naming it, never a traceback."""
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        assert set(rj.score_rounds("US-S")) == {1}
        for content in ('{"score": ', "[]"):
            (d / "US-S-r2-score.json").write_text(content, encoding="utf-8")
            try:
                rj.score_rounds("US-S")
            except SystemExit as e:
                assert "US-S-r2-score.json" in str(e), e
            else:
                raise AssertionError(f"malformed score file accepted: {content!r}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric_carry OK")
