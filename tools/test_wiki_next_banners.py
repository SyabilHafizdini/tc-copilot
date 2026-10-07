#!/usr/bin/env python3
"""Plain-assert tests for wiki_next banners and phase
(run: py tools/test_wiki_next_banners.py). No pytest -- matches tools/smoke.py.

Cards live in gitignored build/, so these write throwaway cards there and
delete them; nothing touches tracked state."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/app"))
import wiki_next
import read_models

CARDS = ROOT / "build/cards"


class SkipTest(Exception):
    """Raised by a test that cannot run in the current repo state. The
    __main__ loop reports this as [SKIP], never [PASS] -- a skipped test
    must not be able to read as a pass in the final output."""


def _card(name, card_type="alignment", human_response=None, **extra):
    """Write a throwaway card under build/cards/. `extra` adds/overrides
    body fields -- e.g. coverage_status=..., map_corrections=..., note=...
    for a coverage-type card. Default alignment card keeps zones={} unless
    overridden, matching the original fixture shape."""
    CARDS.mkdir(parents=True, exist_ok=True)
    p = CARDS / name
    body = {"card_type": card_type, "session": "US-TEST-001",
            "story": "stories/US-TEST"}
    if card_type == "alignment":
        body["zones"] = {}
    body.update(extra)
    if human_response is not None:
        body["human_response"] = human_response
    p.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    return p


def test_pending_cards_lists_a_card_with_no_human_response():
    p = _card("_t_pending.json")
    try:
        names = [c["file"] for c in wiki_next.pending_cards()]
        assert "_t_pending.json" in names, names
    finally:
        p.unlink()


def test_pending_cards_skips_an_answered_card():
    p = _card("_t_answered.json", human_response={"answer": "assert", "by": "x"})
    try:
        names = [c["file"] for c in wiki_next.pending_cards()]
        assert "_t_answered.json" not in names, names
    finally:
        p.unlink()


def test_pending_card_raises_a_banner_naming_the_file():
    p = _card("_t_banner.json")
    try:
        banners = wiki_next.collect_next([])["banners"]
        hits = [b for b in banners if "_t_banner.json" in b["state"]]
        assert hits, [b["state"] for b in banners]
        assert "tc-align" in hits[0]["skill"], hits[0]
    finally:
        p.unlink()


def test_inbox_carries_an_alignment_card_through_unchanged():
    zones = {"acceptance_criteria": {"proposed": ["AC-1 asserted"]}}
    p = _card("_t_inbox_alignment.json", card_type="alignment", zones=zones)
    try:
        cards = read_models.inbox()["cards"]
        hits = [c for c in cards if c["file"] == "_t_inbox_alignment.json"]
        assert hits, [c["file"] for c in cards]
        item = hits[0]
        assert item["card_type"] == "alignment", item
        assert item["story"] == "stories/US-TEST", item
        assert item["session"] == "US-TEST-001", item
        assert item["zones"] == zones, item
    finally:
        p.unlink()


def test_a_triage_card_carries_a_usable_card_type():
    """A CLI-emitted triage card has `scope`, not `card_type`. The operator
    app's InboxPage does `card.card_type.replace(...)` to build the row
    title, so a null here throws during render, the whole Inbox page fails to
    mount, and the Playwright visual gate times out waiting for `.inbox`.
    The one thing this must never be is None."""
    CARDS.mkdir(parents=True, exist_ok=True)
    p = CARDS / "_t_inbox_triage.json"
    p.write_text(json.dumps(
        {"scope": "triage", "plan_hash": "sha256:x",
         "open_questions": [{"id": "q-file-a-yml-abc123", "kind": "file",
                             "item": "a.yml", "proposed": "reference",
                             "options": ["reference", "ignore"]}]},
        indent=1) + "\n", encoding="utf-8")
    try:
        hits = [c for c in wiki_next.pending_cards()
                if c["file"] == "_t_inbox_triage.json"]
        assert hits, [c["file"] for c in wiki_next.pending_cards()]
        assert hits[0]["card_type"] == "triage", hits[0]
        item = [c for c in read_models.inbox()["cards"]
                if c["file"] == "_t_inbox_triage.json"][0]
        assert item["card_type"] == "triage", item
    finally:
        p.unlink()


def test_an_explicit_card_type_still_wins_over_scope():
    p = _card("_t_inbox_scoped.json", card_type="alignment", scope="alignment")
    try:
        item = [c for c in read_models.inbox()["cards"]
                if c["file"] == "_t_inbox_scoped.json"][0]
        assert item["card_type"] == "alignment", item
    finally:
        p.unlink()


def test_inbox_carries_a_coverage_card_through_unchanged():
    p = _card("_t_inbox_coverage.json", card_type="coverage",
              coverage_status="gap", map_corrections=["fix row 3"],
              note="needs human disposition")
    try:
        cards = read_models.inbox()["cards"]
        hits = [c for c in cards if c["file"] == "_t_inbox_coverage.json"]
        assert hits, [c["file"] for c in cards]
        item = hits[0]
        assert item["card_type"] == "coverage", item
        assert item["coverage_status"] == "gap", item
        assert item["map_corrections"] == ["fix row 3"], item
        assert item["note"] == "needs human disposition", item
    finally:
        p.unlink()


def test_inbox_excludes_an_answered_card():
    p = _card("_t_inbox_answered.json",
              human_response={"answer": "assert", "by": "x"})
    try:
        names = [c["file"] for c in read_models.inbox()["cards"]]
        assert "_t_inbox_answered.json" not in names, names
    finally:
        p.unlink()


def test_inbox_does_not_mutate_the_repo():
    import subprocess
    p = _card("_t_inbox_mutation.json")
    try:
        before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True).stdout
        read_models.inbox()
        after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout
        assert before == after, f"inbox() mutated the tree:\n{after}"
    finally:
        p.unlink()


def test_phase_from_stories_is_generated_when_a_story_has_active_tcs():
    assert wiki_next.phase_from_stories(
        [{"status": "aligned", "open_questions": 0, "tc": {"active": 3}}]) == 3


def test_phase_from_stories_is_ready_when_aligned_with_no_open_questions():
    assert wiki_next.phase_from_stories(
        [{"status": "aligned", "open_questions": 0, "tc": {"active": 0}}]) == 2


def test_phase_from_stories_is_in_alignment_for_a_draft():
    assert wiki_next.phase_from_stories(
        [{"status": "draft", "open_questions": 0, "tc": {"active": 0}}]) == 1


def test_phase_from_stories_takes_the_highest_any_story_reached():
    assert wiki_next.phase_from_stories([
        {"status": "draft", "open_questions": 0, "tc": {"active": 0}},
        {"status": "aligned", "open_questions": 0, "tc": {"active": 1}},
    ]) == 3


def test_collect_next_exposes_phase():
    out = wiki_next.collect_next([])
    assert set(out) == {"banners", "rows", "phase"}, out.keys()
    assert out["phase"]["phase"] in (0, 1, 2, 3), out["phase"]
    assert isinstance(out["phase"]["label"], str) and out["phase"]["label"]


def test_dumped_file_raises_a_triage_banner():
    dump = ROOT / "PUT_FILES_HERE"
    dump.mkdir(exist_ok=True)
    p = dump / "_t_dumped.txt"
    p.write_text("x", encoding="utf-8")
    try:
        banners = wiki_next.collect_next([])["banners"]
        hits = [b for b in banners if "PUT_FILES_HERE" in b["state"]]
        assert hits, [b["state"] for b in banners]
        assert "triage" in hits[0]["command"], hits[0]
        assert "tc-intake" in hits[0]["skill"], hits[0]
    finally:
        p.unlink()


def test_no_dump_banner_when_only_the_readme_is_present():
    dump = ROOT / "PUT_FILES_HERE"
    leftovers = [p for p in dump.rglob("*")
                 if p.is_file() and p.name != "README.md"] if dump.exists() else []
    if leftovers:
        raise SkipTest(f"{len(leftovers)} file(s) in the dump")
    banners = wiki_next.collect_next([])["banners"]
    assert not [b for b in banners if "PUT_FILES_HERE" in b["state"]], banners


def _doubts_fixture():
    import test_wiki_doubts as twd
    return twd


def test_doubts_also_open_doubts_exact_entry():
    twd = _doubts_fixture()
    d = twd._mkroot()
    try:
        s = twd.wiki_doubts.story_summary(twd.STORY, root=d)
        assert s["open"] > 0, s["open"]
        got = wiki_next.doubts_also(twd.STORY, root=d)
        want = [{"state": f"{s['open']} open doubts in {s['questions_open']} questions",
                 "command": f"py tools/wiki.py doubts list --story {twd.STORY}",
                 "skill": "tc-resolve"}]
        assert got == want, got
    finally:
        twd._cleanup(d)


def test_doubts_also_invalid_register():
    twd = _doubts_fixture()
    d = twd._mkroot(register="story: [unclosed")
    try:
        got = wiki_next.doubts_also(twd.STORY, root=d)
        assert got == [{"state": "doubt register invalid - run lint",
                        "command": "py tools/wiki.py lint",
                        "skill": "tc-resolve"}], got
    finally:
        twd._cleanup(d)


def test_doubts_also_no_doubts_is_empty():
    twd = _doubts_fixture()
    d = twd._mkroot(register=None)
    try:
        assert wiki_next.doubts_also("US-NOT-A-STORY", root=d) == []
    finally:
        twd._cleanup(d)


def test_doubts_also_never_raises():
    twd = _doubts_fixture()
    orig = twd.wiki_doubts.story_summary

    def boom(*a, **k):
        raise RuntimeError("boom")
    twd.wiki_doubts.story_summary = boom
    try:
        got = wiki_next.doubts_also("US-ANY")
        assert got and got[0]["state"] == "doubt register invalid - run lint", got
    finally:
        twd.wiki_doubts.story_summary = orig


def test_collect_next_rows_carry_also_and_keep_story_next():
    out = wiki_next.collect_next([])
    if not out["rows"]:
        raise SkipTest("no stories or flows in this repo")
    for r in out["rows"]:
        assert isinstance(r["also"], list), r
        if r["scope"] == "flow":
            assert r["also"] == [], r
    concepts = {rel: (fm, body, p) for rel, fm, body, p in wiki_next.all_concepts()}
    manifest = wiki_next.load_manifest()
    checked = 0
    for rel, (fm, body, _p) in concepts.items():
        if fm and fm.get("type") == "User Story":
            row = [r for r in out["rows"] if r["id"] == fm["id"]][0]
            assert (row["state"], row["command"], row["skill"]) ==                 wiki_next.story_next(fm["id"], fm, body, manifest, rel, concepts=concepts), row
            checked += 1
    if not checked:
        raise SkipTest("no stories in this repo")


def test_cmd_next_prints_an_also_line():
    import io
    import contextlib
    rows = wiki_next.collect_next([])["rows"]
    if not any(r["also"] for r in rows):
        raise SkipTest("no story with doubts")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        wiki_next.cmd_next([])
    lines = [ln for ln in buf.getvalue().splitlines() if ln.startswith("    also:  ")]
    assert lines, buf.getvalue()
    assert " -> py tools/wiki.py " in lines[0] and "(tc-resolve)" in lines[0], lines[0]
    lines[0].encode("ascii")


def _doubts_card(name, **kw):
    return _card(name, card_type="doubts", story="US-ZZ-FAKE-DOUBTS",
                 open_questions=[], **kw)


def _banner_for(name):
    banners = wiki_next.collect_next([])["banners"]
    return [b for b in banners if name in b["state"]]


def test_pending_doubts_card_gets_the_doubts_banner():
    p = _doubts_card("_t_zz_fake_doubts_pending.json")
    try:
        hits = _banner_for("_t_zz_fake_doubts_pending.json")
        assert hits, "no banner"
        assert "doubts answer" in hits[0]["command"], hits[0]
        assert "card revise build/cards/_t_zz_fake_doubts_pending.json" \
            in hits[0]["command"], hits[0]
        assert hits[0]["skill"].startswith("tc-resolve"), hits[0]
    finally:
        p.unlink()


def test_pending_non_doubts_card_keeps_the_old_banner():
    p = _card("_t_zz_fake_align_pending.json")
    try:
        hits = _banner_for("_t_zz_fake_align_pending.json")
        assert hits and hits[0]["command"].startswith(
            "py tools/wiki.py assert story <id> --by <user> --card "
            "build/cards/_t_zz_fake_align_pending.json"), hits
        assert hits[0]["skill"].startswith("tc-align"), hits[0]
    finally:
        p.unlink()


def test_answered_unapplied_doubts_card_gets_a_banner():
    hr = {"answer": "revise", "by": "zz-fake-human",
          "answers": {"Q-ZZ-01": {"decision": "accept", "value": None}}}
    name = "_t_zz_fake_doubts_answered.json"
    p = _doubts_card(name, human_response=hr)
    try:
        assert name not in [c["file"] for c in wiki_next.pending_cards()]
        hits = _banner_for(name)
        assert hits, "no banner"
        assert hits[0]["state"] == (f"doubts card {name} is answered but not "
                                    f"applied"), hits[0]
        assert hits[0]["command"] == (
            f"py tools/wiki.py doubts answer --card build/cards/{name} "
            f"--by zz-fake-human   # refused as changed? py tools/wiki.py "
            f"card discard build/cards/{name} --by zz-fake-human, then emit "
            f"a new card: py tools/wiki.py doubts card --story "
            f"US-ZZ-FAKE-DOUBTS"), hits[0]
        assert hits[0]["skill"] == "tc-resolve"
        # once applied, no banner
        c = json.loads(p.read_text(encoding="utf-8"))
        c["applied"] = {"by": "zz-fake-human"}
        p.write_text(json.dumps(c), encoding="utf-8")
        assert _banner_for(name) == []
    finally:
        p.unlink()


def test_discarded_doubts_card_gets_no_banner():
    name = "_t_zz_fake_doubts_discarded.json"
    p = _doubts_card(name, human_response={"answer": "discard",
                                           "by": "zz-fake-human"})
    try:
        assert _banner_for(name) == []
    finally:
        p.unlink()


class _Patched:
    """Replace wiki_doubts.unrendered_lifts for a with-block."""
    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        import wiki_doubts
        self.mod, self.old = wiki_doubts, wiki_doubts.unrendered_lifts
        wiki_doubts.unrendered_lifts = self.fn

    def __exit__(self, *a):
        self.mod.unrendered_lifts = self.old


# A neutral in-memory story for a bundle that holds none (the content-free
# base). The tests that take a story row override its status, coverage and
# test-case counts themselves, so which story it is does not matter.
_FIXTURE_STORY = ("stories/US-ZZ-FIXTURE",
                  {"type": "User Story", "id": "US-ZZ-FIXTURE",
                   "title": "Fixture story", "status": "aligned",
                   "acceptance_criteria": [{"id": "AC1", "text": "Fixture."}],
                   "test_model": {"status": "confirmed"}},
                  "# Story\n\nFixture.\n")


def _story_row():
    for rel, fm, body, _p in wiki_next.all_concepts():
        if fm and fm.get("type") == "User Story":
            return rel, fm, body
    return _FIXTURE_STORY


def _entry(story, kind="sit", flow=None):
    return {"story": story, "kind": kind, "flow": flow,
            "scenario_id": "SC-ZZ", "part": "data", "doubt": "SC-ZZ#data",
            "tc": "testcases/x", "expected": "/resolutions/R-1.md",
            "rendered": None}


def test_story_next_reports_unrendered_lifts():
    rel, fm, body = _story_row()
    manifest = wiki_next.load_manifest()
    fm = dict(fm, status="aligned")
    sid = fm["id"]
    # force the state that reaches the lift row: aligned, confirmed, one TC
    orig_cov, orig_stats = wiki_next.load_coverage, wiki_next.story_tc_stats
    wiki_next.load_coverage = lambda _fm: ({}, {}, "confirmed")
    wiki_next.story_tc_stats = lambda m, r: {"active": 3, "stale": 0,
                                             "retired": 0}
    fm["test_model"] = {"status": "confirmed"}
    try:
        base = wiki_next.story_next(sid, fm, "", manifest, rel)
        assert "not rendered" not in base[0], base
        with _Patched(lambda root=None: [_entry(sid), _entry(sid)]):
            state, cmd, skill = wiki_next.story_next(sid, fm, "", manifest, rel)
        assert state == "2 confirmed doubt(s) not rendered", state
        assert cmd == (f"py tools/render_sit.py --story {sid}"
                       f"   # then: py tools/wiki.py seal"), cmd
        assert skill == "tc-resolve (render and seal the lifts)", skill
        with _Patched(lambda root=None: [_entry("US-OTHER")]):
            assert wiki_next.story_next(sid, fm, "", manifest, rel) == base
        with _Patched(lambda root=None: []):
            assert wiki_next.story_next(sid, fm, "", manifest, rel) == base
    finally:
        wiki_next.load_coverage, wiki_next.story_tc_stats = orig_cov, orig_stats


def test_story_next_does_not_take_uat_test_cases_for_the_story_set():
    """A flow's UAT test cases cover the story's criteria, but the story's own
    set is its SIT test cases: with none, the row says so and names the render,
    never the draft export (which refuses a story with no SIT test case)."""
    rel, fm, _body = _FIXTURE_STORY
    manifest = {"concepts": {"testcases/uat/F/UAT-1": {"status": "active"},
                             "testcases/uat/F/UAT-2": {"status": "active"}},
                "edges": [["testcases/uat/F/UAT-1", "covers", rel + "#AC1"],
                          ["testcases/uat/F/UAT-2", "covers", rel + "#AC1"]]}
    orig_cov = wiki_next.load_coverage
    wiki_next.load_coverage = lambda _fm: ({}, {}, "confirmed")
    try:
        state, cmd, skill = wiki_next.story_next(fm["id"], fm, "", manifest, rel)
        assert state == ("aligned · coverage confirmed · 0 SIT TCs "
                         "(2 UAT TC(s) cover it through a flow)"), state
        assert cmd == (f"py tools/render_sit.py --story {fm['id']} "
                       f"&& py tools/wiki.py seal"), cmd
        assert skill == "tc-generate-sit (render)", skill
        manifest["concepts"]["testcases/sit/m/T-1"] = {"status": "stale"}
        manifest["edges"].append(["testcases/sit/m/T-1", "covers", rel + "#AC1"])
        state, _cmd, _skill = wiki_next.story_next(fm["id"], fm, "", manifest, rel)
        assert state == "aligned · coverage confirmed · 1 STALE TC(s)", state
    finally:
        wiki_next.load_coverage = orig_cov


def test_flow_next_reports_unrendered_uat_lifts():
    fm = {"id": "FLOW-ZZ-FAKE", "status": "aligned",
          "journey": [{"id": "J01"}], "stories": []}
    manifest = {"concepts": {"testcases/uat/zz.md": {"status": "active"}}}
    base = wiki_next.flow_next("FLOW-ZZ-FAKE", fm, "", {}, manifest)
    assert "not rendered" not in base[0], base
    with _Patched(lambda root=None: [_entry("S", "uat", "FLOW-ZZ-FAKE")]):
        state, cmd, skill = wiki_next.flow_next("FLOW-ZZ-FAKE", fm, "", {},
                                                manifest)
    assert state == "1 confirmed doubt(s) not rendered", state
    assert cmd == ("py tools/render_uat.py --flow FLOW-ZZ-FAKE"
                   "   # then: py tools/wiki.py seal"), cmd
    assert skill == "tc-resolve (render and seal the lifts)"
    with _Patched(lambda root=None: [_entry("S", "uat", "FLOW-OTHER"),
                                     _entry("S", "sit")]):
        assert wiki_next.flow_next("FLOW-ZZ-FAKE", fm, "", {}, manifest) == base


def test_a_raising_unrendered_lifts_does_not_crash_next():
    calls = []

    def boom(root=None):
        calls.append(1)
        raise RuntimeError("doubts broke")
    rel, fm, body = _story_row()
    sid = fm["id"]
    with _Patched(boom):
        out = _with_active_story(
            lambda: wiki_next.story_next(sid, dict(fm, status="aligned",
                                                   test_model={"status": "confirmed"}),
                                         "", wiki_next.load_manifest(), rel))
        assert calls, "the lift check was never reached"
        assert "not rendered" not in out[0], out
        assert wiki_next.collect_next([])["rows"] is not None


def _with_active_story(fn):
    orig_cov, orig_stats = wiki_next.load_coverage, wiki_next.story_tc_stats
    wiki_next.load_coverage = lambda _fm: ({}, {}, "confirmed")
    wiki_next.story_tc_stats = lambda m, r: {"active": 3, "stale": 0,
                                             "retired": 0}
    try:
        return fn()
    finally:
        wiki_next.load_coverage, wiki_next.story_tc_stats = orig_cov, orig_stats


def test_collect_next_computes_unrendered_lifts_once():
    calls = []

    def count(root=None):
        calls.append(1)
        return []
    orig_stats = wiki_next.story_tc_stats
    orig_all, orig_cov = wiki_next.all_concepts, wiki_next.load_coverage
    wiki_next.story_tc_stats = lambda m, r: {"active": 3, "stale": 0,
                                             "retired": 0}
    real = list(orig_all())
    if not any(fm and fm.get("type") == "User Story" for _r, fm, _b, _p in real):
        # A content-free bundle: give collect_next the fixture story, at the
        # state that reaches the lift check (coverage and model confirmed).
        rel, fm, body = _FIXTURE_STORY
        wiki_next.all_concepts = lambda: real + [(rel, fm, body, None)]
        wiki_next.load_coverage = lambda _fm: ({}, {}, "confirmed")
    try:
        with _Patched(count):
            wiki_next.collect_next([])
            n_rows = len(wiki_next.collect_next([])["rows"])
    finally:
        wiki_next.story_tc_stats = orig_stats
        wiki_next.all_concepts, wiki_next.load_coverage = orig_all, orig_cov
    assert n_rows >= 1
    assert len(calls) == 2, calls   # once per collect_next, however many rows


def test_answered_banner_without_by_falls_back_to_user():
    name = "_t_zz_fake_doubts_noby.json"
    p = _doubts_card(name, human_response={
        "answer": "revise",
        "answers": {"Q-ZZ-01": {"decision": "accept", "value": None}}})
    try:
        hits = _banner_for(name)
        assert hits and "--by <user>   #" in hits[0]["command"], hits
        assert hits[0]["command"].count("--by <user>") == 2, hits
    finally:
        p.unlink()


def test_discarding_an_answered_doubts_card_clears_its_banner():
    """F4: a stale answered doubts card has a legal exit (card discard), and
    once discarded it no longer raises the answered-but-not-applied banner."""
    import contextlib
    import io
    import wiki
    hr = {"answer": "revise", "by": "zz-fake-human",
          "answers": {"Q-ZZ-01": {"decision": "accept", "value": None}}}
    name = "_t_zz_fake_doubts_stale.json"
    p = _doubts_card(name, human_response=hr)
    try:
        assert _banner_for(name)
        with contextlib.redirect_stdout(io.StringIO()):
            wiki.cmd_card(["discard", str(p), "--by", "zz-fake-human"])
        c = json.loads(p.read_text(encoding="utf-8"))
        assert c["human_response"]["answer"] == "discard", c
        assert c["superseded_response"] == hr, c
        assert _banner_for(name) == []
        assert name not in [x["file"] for x in wiki_next.pending_cards()]
    finally:
        p.unlink()


def test_card_listings_survive_a_card_that_is_not_utf8():
    """F6: a card that is not valid UTF-8 is skipped, never raised."""
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "build" / "cards"
        d.mkdir(parents=True)
        (d / "doubts-X-001.json").write_bytes(b'{"card_type": "doubts\xff"}')
        (d / "doubts-X-002.json").write_text(json.dumps({
            "card_type": "doubts", "story": "X", "human_response": {
                "answer": "revise", "by": "h", "answers": {"Q": {}}}}),
            encoding="utf-8")
        got = wiki_next.answered_doubts_cards(root=t)
        assert [c["file"] for c in got] == ["doubts-X-002.json"], got
        assert wiki_next.pending_cards(root=t) == []


if __name__ == "__main__":
    skipped = []
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except SkipTest as e:
                print(f"[SKIP] {name} ({e})")
                skipped.append(name)
            except Exception as e:
                fails += 1
                print(f"[FAIL] {name}: {e}")
            else:
                print(f"[PASS] {name}")
    print("test_wiki_next_banners " + ("FAILED" if fails else "OK") +
          (f" ({len(skipped)} skipped)" if skipped else ""))
    sys.exit(1 if fails else 0)
