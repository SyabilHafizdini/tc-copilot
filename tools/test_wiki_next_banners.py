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


if __name__ == "__main__":
    skipped = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except SkipTest as e:
                print(f"[SKIP] {name} ({e})")
                skipped.append(name)
            else:
                print(f"[PASS] {name}")
    print("test_wiki_next_banners OK" +
          (f" ({len(skipped)} skipped)" if skipped else ""))
