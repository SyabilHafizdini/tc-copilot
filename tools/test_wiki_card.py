#!/usr/bin/env python3
"""Plain-assert tests for `wiki card revise|discard`
(run: py tools/test_wiki_card.py). No pytest -- matches tools/smoke.py.
Cards live in gitignored build/, so these write throwaway card files there
and delete them; nothing touches tracked state."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki

CARDS = ROOT / "build/cards"


def _mk(name, extra):
    CARDS.mkdir(parents=True, exist_ok=True)
    p = CARDS / name
    card = {"card_type": "alignment", "session": "US-TEST-001",
            "story": "stories/US-TEST", "zones": {"open_questions": [
                {"id": "Q1", "about": "AC1", "question": "q", "proposed": "p"},
                {"id": "Q2", "about": "AC2", "question": "q", "proposed": "p"}]}}
    card.update(extra)
    p.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    return p


def test_revise_stamps_structured_answers():
    p = _mk("_t_revise.json", {})
    try:
        wiki.cmd_card(["revise", str(p), "--by", "tester",
                       "--answer", "Q1=accept", "--answer", "Q2=fix the label",
                       "--note", "overall note"])
        hr = json.loads(p.read_text(encoding="utf-8"))["human_response"]
        assert hr["answer"] == "revise" and hr["by"] == "tester", hr
        assert hr["answers"]["Q1"] == {"decision": "accept", "value": None}, hr
        assert hr["answers"]["Q2"] == {"decision": "correct", "value": "fix the label"}, hr
        assert hr["note"] == "overall note", hr
    finally:
        p.unlink()


def test_discard_stamps_answer():
    p = _mk("_t_discard.json", {})
    try:
        wiki.cmd_card(["discard", str(p), "--by", "tester", "--note", "wrong"])
        hr = json.loads(p.read_text(encoding="utf-8"))["human_response"]
        assert hr == {**hr, "answer": "discard", "by": "tester", "note": "wrong"}, hr
        assert "at" in hr, hr
    finally:
        p.unlink()


def test_refuses_already_answered():
    p = _mk("_t_answered.json", {"human_response": {"answer": "assert"}})
    try:
        try:
            wiki.cmd_card(["revise", str(p), "--by", "t", "--answer", "Q1=accept"])
            assert False, "expected SystemExit on already-answered card"
        except SystemExit:
            pass
    finally:
        p.unlink()


def test_refuses_unknown_qid():
    p = _mk("_t_badq.json", {})
    try:
        try:
            wiki.cmd_card(["revise", str(p), "--by", "t", "--answer", "Q9=x"])
            assert False, "expected SystemExit on unknown Qid"
        except SystemExit:
            pass
    finally:
        p.unlink()


def test_requires_by():
    p = _mk("_t_noby.json", {})
    try:
        try:
            wiki.cmd_card(["discard", str(p)])
            assert False, "expected SystemExit without --by"
        except SystemExit:
            pass
    finally:
        p.unlink()



def _doubts(name, extra):
    return _mk(name, {"card_type": "doubts", "story": "US-TEST",
                      "open_questions": [{"id": "Q-US-TEST-01"}], **extra})


def _exit_text(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e.code)
    raise AssertionError("expected SystemExit")


ANSWERED = {"answer": "revise", "by": "tester", "at": "x",
            "answers": {"Q-US-TEST-01": {"decision": "accept", "value": None}}}


def test_discard_an_answered_unapplied_doubts_card():
    """F4: the legal exit for a doubts card that can no longer be applied."""
    p = _doubts("_t_doubts_stale.json", {"human_response": ANSWERED})
    try:
        wiki.cmd_card(["discard", str(p), "--by", "tester", "--note", "stale"])
        c = json.loads(p.read_text(encoding="utf-8"))
        assert c["superseded_response"] == ANSWERED, c
        hr = c["human_response"]
        assert hr["answer"] == "discard" and hr["by"] == "tester", hr
        assert hr["note"] == "stale" and "answers" not in hr, hr
        # once discarded it is answered for good
        msg = _exit_text(lambda: wiki.cmd_card(["discard", str(p), "--by", "t"]))
        assert "already answered (discard)" in msg, msg
    finally:
        p.unlink()


def test_discard_refused_for_an_applied_doubts_card_or_revise():
    p = _doubts("_t_doubts_applied.json",
                {"human_response": ANSWERED, "applied": {"by": "tester"}})
    try:
        before = p.read_bytes()
        msg = _exit_text(lambda: wiki.cmd_card(["discard", str(p), "--by", "t"]))
        assert "already answered" in msg, msg
        assert p.read_bytes() == before
    finally:
        p.unlink()
    p = _doubts("_t_doubts_rerevise.json", {"human_response": ANSWERED})
    try:
        msg = _exit_text(lambda: wiki.cmd_card(
            ["revise", str(p), "--by", "t", "--answer", "Q-US-TEST-01=accept"]))
        assert "already answered" in msg, msg
    finally:
        p.unlink()


def test_discard_still_refused_for_an_answered_non_doubts_card():
    """F4: other card types keep today's behaviour exactly."""
    for hr in ({"answer": "assert"}, {**ANSWERED}):
        p = _mk("_t_align_answered.json", {"human_response": hr})
        try:
            before = p.read_bytes()
            msg = _exit_text(lambda: wiki.cmd_card(
                ["discard", str(p), "--by", "t"]))
            assert msg == (f"card discard refused: {p.name} already answered "
                           f"({hr['answer']})"), msg
            assert p.read_bytes() == before
        finally:
            p.unlink()


def test_require_card_refuses_a_doubts_card():
    """F7: a doubts card answers doubt questions; it cannot assert a story."""
    p = _doubts("_t_doubts_assert.json", {})
    try:
        msg = _exit_text(lambda: wiki.require_card(
            "story", "US-TEST", ["--card", str(p)], "tester"))
        assert msg == (f"assert refused: {p.name} is a doubts card; it answers "
                       f"doubt questions (wiki doubts answer), it cannot assert "
                       f"a story or flow"), msg
        # the same card under another type passes the fence
        c = json.loads(p.read_text(encoding="utf-8"))
        c["card_type"] = "alignment"
        p.write_text(json.dumps(c), encoding="utf-8")
        got_path, _card = wiki.require_card("story", "US-TEST",
                                            ["--card", str(p)], "tester")
        assert got_path == p
    finally:
        p.unlink()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except (Exception, SystemExit) as e:
                fails += 1
                print(f"[FAIL] {name}: {e}")
    print("test_wiki_card " + ("FAILED" if fails else "OK"))
    sys.exit(1 if fails else 0)
