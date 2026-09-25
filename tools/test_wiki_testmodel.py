#!/usr/bin/env python3
"""Plain-assert tests for the test-model scaffold, lint L14 / W7 and the
assert-time confirmation (run: py tools/test_wiki_testmodel.py). No pytest.

Pure functions over synthetic frontmatter; nothing on disk is touched.
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import confirm_test_model, l14_errors, w7_warnings  # noqa: E402
from wiki_rubric import validate_test_model  # noqa: E402
from wiki_testmodel import propose_flow_model, propose_story_model  # noqa: E402
import wiki_next  # noqa: E402

STORY = {
    "type": "User Story", "id": "US-M",
    "acceptance_criteria": [
        {"id": "M-AC1", "scenario": "Open the page",
         "text": "Given I am signed in, when I open the page, then it shows."},
        {"id": "M-AC2", "scenario": "Count range",
         "text": "When I enter a count that is less than 1, then the system "
                 "rejects it; Quantity must be a whole number of 1 or more."},
        {"id": "M-AC3", "scenario": "Selector values",
         "text": "When I open the selector, then the system lists only the "
                 "systems fitted to the platform, with no value pre-selected."},
        {"id": "M-AC4", "scenario": "Clear",
         "text": "When I clear the selector, then the system clears the table "
                 "and redisplays the prompt."},
    ],
    "business_rules": [
        {"id": "BR-M-01", "title": "One per ship", "text": "At most one.",
         "verified_by": ["M-AC2", "M-AC9"]},
    ],
}


def test_scaffold_has_one_scenario_per_ac_and_one_rule_per_br():
    items = propose_story_model(STORY)
    sc = [i for i in items if i["technique"] == "UC"]
    rules = [i for i in items if i["technique"] == "DT"]
    assert [i["id"] for i in sc] == ["SC-01", "SC-02", "SC-03", "SC-04"], sc
    assert len(rules) == 1 and rules[0]["basis"] == ["BR-M-01", "M-AC2"], rules


def test_scaffold_detects_a_boundary_a_partition_and_a_transition():
    items = propose_story_model(STORY)
    by = {i["id"]: i for i in items}
    assert "BVA-01" in by and by["BVA-01"]["basis"] == ["M-AC2"], by.keys()
    assert "EP-01" in by and by["EP-01"]["basis"] == ["M-AC3"], by.keys()
    assert "ST-01" in by and by["ST-01"]["basis"] == ["M-AC4"], by.keys()


def test_scaffold_validates_against_the_story():
    fm = dict(STORY, test_model={"status": "proposed",
                                 "items": propose_story_model(STORY)})
    assert validate_test_model(fm, "US-M") == []


def test_scaffold_skips_a_voided_ac():
    fm = dict(STORY)
    fm["acceptance_criteria"] = STORY["acceptance_criteria"] + [
        {"id": "M-AC5", "text": "dead", "status": "voided"}]
    ids = [i["id"] for i in propose_story_model(fm)]
    assert "SC-05" not in ids, ids


def test_flow_scaffold_is_the_main_scenario_only():
    fm = {"type": "Flow", "id": "FLOW-X",
          "journey": [{"id": "J01", "ref": "/stories/A.md#AC1"},
                      {"id": "J02", "ref": "/stories/B.md#AC1"}]}
    items = propose_flow_model(fm)
    assert len(items) == 1 and items[0]["role"] == "main"
    assert items[0]["basis"] == ["J01", "J02"]
    assert validate_test_model(dict(fm, test_model={"status": "proposed",
                                                    "items": items}),
                               "FLOW-X") == []


def test_flow_without_journey_scaffolds_nothing():
    assert propose_flow_model({"type": "Flow", "id": "F"}) == []


# ----------------------------------------------------------- lint L14 / W7
def test_l14_reports_a_bad_basis_and_ignores_an_absent_model():
    bad = dict(STORY, test_model={"status": "proposed", "items": [
        {"id": "X-1", "technique": "EP", "kind": "partition",
         "basis": ["M-AC99"], "feasible": True}]})
    errs = l14_errors({"stories/US-M": (bad, ""),
                       "stories/US-N": (dict(STORY, id="US-N"), "")})
    assert len(errs) == 1 and errs[0].startswith("L14 stories/US-M") \
        and "M-AC99" in errs[0], errs


def test_w7_warns_on_a_coverage_item_the_model_does_not_define():
    story = dict(STORY, test_model={"status": "confirmed", "items": [
        {"id": "SC-01", "technique": "UC", "kind": "scenario",
         "basis": ["M-AC1"], "feasible": True}]})
    tc = {"type": "Test Case", "id": "T", "status": "active",
          "covers": ["/stories/US-M.md#M-AC1"], "coverage_items": ["SC-99"]}
    w = w7_warnings({"stories/US-M": (story, ""), "testcases/sit/US-M/T": (tc, "")})
    assert len(w) == 1 and "SC-99" in w[0], w


def test_w7_is_silent_for_an_unmodelled_story():
    tc = {"type": "Test Case", "id": "T", "status": "active",
          "covers": ["/stories/US-M.md#M-AC1"], "coverage_items": ["SC-99"]}
    assert w7_warnings({"stories/US-M": (dict(STORY), ""),
                        "testcases/sit/US-M/T": (tc, "")}) == []


# ------------------------------------------------- assert-time confirmation
def _refused(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


def test_assert_confirms_a_proposed_model_the_card_carries():
    items = propose_story_model(STORY)
    fm = dict(STORY, test_model={"status": "proposed", "items": items})
    card = {"story": "US-M", "test_model": {"items": items}}
    confirm_test_model(fm, card, "US-M", "human")
    assert fm["test_model"]["status"] == "confirmed"
    assert fm["test_model"]["asserted_by"] == "human"


def test_assert_leaves_the_model_alone_when_the_card_has_none():
    fm = dict(STORY, test_model={"status": "proposed", "items": []})
    confirm_test_model(fm, {"story": "US-M"}, "US-M", "human")
    assert fm["test_model"]["status"] == "proposed"


def test_assert_refuses_when_the_card_shows_a_different_model():
    items = propose_story_model(STORY)
    fm = dict(STORY, test_model={"status": "proposed", "items": items})
    card = {"story": "US-M", "test_model": {"items": items[:-1]}}
    msg = _refused(lambda: confirm_test_model(fm, card, "US-M", "human"))
    assert msg and "different model" in msg, msg
    assert fm["test_model"]["status"] == "proposed"


def test_assert_refuses_an_invalid_model():
    fm = dict(STORY, test_model={"status": "proposed", "items": [
        {"id": "X", "technique": "EP", "kind": "partition",
         "basis": ["NOPE"], "feasible": True}]})
    card = {"story": "US-M", "test_model": {"items": [{"id": "X"}]}}
    msg = _refused(lambda: confirm_test_model(fm, card, "US-M", "human"))
    assert msg and "L14" in msg, msg


# ------------------------------------------------------------- wiki next
_TC_REL = "testcases/sit/US-M/M-AC1-01"
_MANIFEST = {"concepts": {_TC_REL: {"status": "active"}},
             "edges": [[_TC_REL, "covers", "stories/US-M#M-AC1"]],
             "bindings": {}}

def test_next_demands_a_test_model_after_coverage_is_confirmed():
    fm = dict(STORY, status="aligned", coverage_status="confirmed",
              coverage_map=[{"ac": "M-AC1", "components": []}])
    state, cmd, skill = wiki_next.story_next("US-M", fm, "", _MANIFEST,
                                             "stories/US-M")
    assert "test_model" in state and "NOT confirmed" in state, state
    assert cmd == "py tools/wiki.py testmodel --story US-M --propose", cmd
    assert skill.startswith("tc-generate-sit"), skill


def _graded_fm():
    return dict(STORY, status="aligned", coverage_status="confirmed",
                coverage_map=[{"ac": "M-AC1", "components": []}],
                test_model={"status": "confirmed", "items": [
                    {"id": "SC-01", "technique": "UC", "kind": "scenario",
                     "basis": ["M-AC1"], "feasible": True}]})


class _Build:
    """Real build/rubric files in a temp dir: rubric_judge's paths are
    redirected, wiki_next reads them through its real (unstubbed) readers."""
    def __enter__(self):
        import rubric_judge as rj
        self.rj = rj
        self.d = Path(tempfile.mkdtemp(prefix="next-"))
        self.old = (rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR)
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = \
            self.d, self.d / "packs", self.d / "judgments"
        return self

    def __exit__(self, *a):
        self.rj.RUBRIC_BUILD, self.rj.PACK_DIR, self.rj.JUDGMENT_DIR = self.old
        shutil.rmtree(self.d)

    def reset(self):
        for p in self.d.glob("*.json"):
            p.unlink()

    def _write(self, path, doc):
        import json
        path.write_text(json.dumps(doc), encoding="utf-8")

    def snapshot(self, digest):
        self._write(self.rj.draft_path("US-M"), {"sealed_digest": digest})

    def score(self, rnd, digest, score=90.0, partial=False):
        from wiki import load_config
        version = (load_config().get("rubric") or {}).get("version", "v1")
        self._write(self.rj.score_path("US-M", rnd),
                    {"score": score, "partial": partial, "rubric_version": version,
                     "sealed_digest": digest})

    def changes(self, digest):
        self._write(self.rj.changes_path("US-M"), {"to_digest": digest})


def _next_on(tc_hash):
    """story_next on the one-case story whose sealed hash is `tc_hash`,
    concepts passed (the path collect_next takes)."""
    from wiki_rubric import sealed_digest
    m = dict(_MANIFEST, tc_hashes={_TC_REL: tc_hash})
    concepts = {"stories/US-M": (_graded_fm(), "", None),
                _TC_REL: ({"type": "Test Case", "id": "M-AC1-01", "kind": "sit",
                           "status": "active",
                           "covers": ["/stories/US-M.md#M-AC1"]}, "", None)}
    return (wiki_next.story_next("US-M", _graded_fm(), "", m, "stories/US-M",
                                 concepts=concepts),
            sealed_digest({_TC_REL: tc_hash}, [_TC_REL]))


def test_next_walks_the_delivery_steps_from_real_build_files():
    """C1: the route is read from real snapshot / round / changes files. The
    improved set (post patch) is round 2's job, never a second draft."""
    (_s, _c, _k), D0 = _next_on("sha256:v0")        # the first cut
    (_s, _c, _k), D1 = _next_on("sha256:v1")        # after the improve patch
    with _Build() as b:
        # (a) no snapshot -> draft
        (state, cmd, skill), _ = _next_on("sha256:v0")
        assert "first cut NOT delivered" in state and cmd.endswith("--name US-M-sit --draft"), (state, cmd)
        assert skill.startswith("tc-generate-sit"), skill
        # (b) snapshot == current, no rounds -> round 1 pack
        b.snapshot(D0)
        (state, cmd, skill), _ = _next_on("sha256:v0")
        assert "NOT graded" in state and cmd.endswith("--story US-M --round 1 --pack"), (state, cmd)
        assert skill.startswith("tc-rubric"), skill
        # (c) r1 on the snapshot's set, current unchanged -> merge round 1
        b.score(1, D0)
        (state, cmd, _k), _ = _next_on("sha256:v0")
        assert "improve round NOT run" in state and cmd.endswith("--story US-M --round 1"), (state, cmd)
        # (d) r1 on the snapshot's set, set improved since -> round 2 pack, NOT a draft
        (state, cmd, skill), _ = _next_on("sha256:v1")
        assert state == "graded round 1 · set improved - round 2 NOT packed", state
        assert cmd == "py tools/eval_rubric.py --story US-M --round 2 --pack", cmd
        assert skill.startswith("tc-rubric") and "--draft" not in cmd, (skill, cmd)
        # (i) round 2 packed (partial) on the improved set -> the strict merge
        b.score(2, D1, partial=True)
        (state, cmd, _k), _ = _next_on("sha256:v1")
        assert "no strict score" in state and cmd.endswith("--round 2 --strict"), (state, cmd)
        # (e) r2 == current at threshold, no changes file -> diff
        b.score(2, D1)
        (state, cmd, skill), _ = _next_on("sha256:v1")
        assert "change log NOT built" in state and cmd.endswith("--story US-M --diff"), (state, cmd)
        # (f) plus a current changes file -> final export
        b.changes(D1)
        (state, cmd, skill), _ = _next_on("sha256:v1")
        assert "ready to export" in state, state
        assert cmd == "py tools/wiki.py export --story US-M --name US-M-sit", cmd
        assert skill.startswith("tc-suite-author"), skill
        # (g) round 2 regressed, round 1 restored: r1 == current -> diff
        (state, cmd, _k), _ = _next_on("sha256:v0")
        assert "graded r1" in state and cmd.endswith("--story US-M --diff"), (state, cmd)
        # (h) regenerated set: matches no round and differs from the snapshot
        # (whose digest no round was graded on) -> draft, a new first cut
        b.reset()
        b.snapshot(D0)
        (state, cmd, _k), _ = _next_on("sha256:v2")
        assert "first cut NOT delivered" in state and cmd.endswith("--draft"), (state, cmd)
        b.score(1, "sha256:legacy-set")
        (state, cmd, _k), _ = _next_on("sha256:v2")
        assert "first cut NOT delivered" in state and cmd.endswith("--draft"), (state, cmd)
        # (g') restored round 1 below threshold: the strict merge names round 1
        b.reset()
        b.snapshot(D0)
        b.score(1, D0, score=10.0)
        b.score(2, D1, score=5.0)
        (state, cmd, _k), _ = _next_on("sha256:v0")
        assert cmd.endswith("--round 1 --strict"), (state, cmd)


def test_draft_current_counts_a_draft_grading_started_on():
    """A1: a snapshot whose digest is some round's digest is delivered."""
    with _Build() as b:
        assert not wiki_next.draft_current("US-M", "d1", {"d0"})
        b.snapshot("d0")
        assert wiki_next.draft_current("US-M", "d0", set())
        assert wiki_next.draft_current("US-M", "d1", {"d0"})
        assert not wiki_next.draft_current("US-M", "d1", {"dx"})
        assert not wiki_next.draft_current("US-M", "d1")


def test_next_and_export_agree_on_the_digest():
    """I3/I5: `wiki next` reads the scope from the concept files with the
    selector export uses - a test case sealed but not yet in the manifest's
    concepts/edges counts for both, and a flow's UAT case covering the
    story counts for neither."""
    import wiki_export as wx
    from wiki_rubric import sealed_digest
    added = "testcases/sit/US-M/M-AC1-02"
    uat = "testcases/uat/f/UAT-01"
    hashes = {_TC_REL: "sha256:a", added: "sha256:b", uat: "sha256:u"}
    m = dict(_MANIFEST, tc_hashes=hashes)          # no manifest entry for `added`
    tc = lambda tid, kind: {"type": "Test Case", "id": tid, "kind": kind,
                            "status": "active", "title": tid,
                            "covers": ["/stories/US-M.md#M-AC1"]}
    concepts = {"stories/US-M": (_graded_fm(), "", None),
                _TC_REL: (tc("M-AC1-01", "sit"), "", None),
                added: (tc("M-AC1-02", "sit"), "", None),
                uat: (tc("UAT-01", "uat"), "", None)}
    _rel, _sfm, tcs = wx.select_scope_tcs(concepts, "story", "US-M")
    export_digest = sealed_digest(hashes, [r for r, _f, _b in tcs])
    assert wiki_next.scope_digest(m, "stories/US-M", concepts) == export_digest
    assert sorted(r for r, _f, _b in tcs) == [_TC_REL, added], tcs
    assert wiki_next.scope_digest(m, "stories/US-M") != export_digest, \
        "the manifest-only fallback misses the unmanifested case"


def test_scope_digest_reads_the_manifest_only():
    from wiki_rubric import sealed_digest
    m = dict(_MANIFEST, tc_hashes={_TC_REL: "sha256:q"})
    assert wiki_next.scope_digest(m, "stories/US-M") == sealed_digest({_TC_REL: "sha256:q"}, [_TC_REL])


def test_json_field_matches_treats_non_object_json_as_not_current():
    d = Path(tempfile.mkdtemp())
    try:
        cases = {"null.json": "null", "list.json": "[]",
                 "bad.json": '"not json'}
        for name, content in cases.items():
            (d / name).write_text(content, encoding="utf-8")
            assert wiki_next._json_field_matches(d / name, "sealed_digest", "x") is False, name
        assert wiki_next._json_field_matches(d / "missing.json", "sealed_digest", "x") is False
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_testmodel OK")
