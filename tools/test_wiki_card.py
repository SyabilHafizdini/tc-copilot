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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_card OK")
