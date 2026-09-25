#!/usr/bin/env python3
"""Plain-assert tests for L13 (declared story provenance), W6 (prd-verbatim
token-coverage warning), and the empty-AC gate refusal (run: py
tools/test_wiki_l13.py). No pytest.

L13 is a pure function of concept frontmatter, so most of these call the
checker directly with in-memory concepts -- no files are written anywhere.
The gate test is the exception: it writes one fixture story file under
stories/ to exercise the real `wiki.py gate` subprocess, and deletes it in
a finally block -- verified via `git status --porcelain`."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import l13_errors

STORY = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "acceptance_criteria": [{"id": "HS-01", "text": "a"},
                                 {"id": "HS-02", "text": "b"}]}


def _res(*refs):
    return {"type": "Resolution", "id": "R-T", "title": "t", "description": "d",
            "resolves": list(refs)}


def test_prd_verbatim_story_with_derived_from_passes():
    s = dict(STORY, provenance="prd-verbatim", derived_from=["/sources/prd/1-1.md"])
    assert l13_errors({"stories/US-T": (s, "")}) == []


def test_story_without_provenance_errors_even_with_derived_from():
    s = dict(STORY, derived_from=["/sources/prd/1-1.md"])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert any("provenance" in e for e in errs), errs


def test_human_stated_with_derived_from_errors():
    s = dict(STORY, provenance="human-stated", derived_from=["/sources/prd/1-1.md"])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert any("not human-stated" in e for e in errs), errs


def test_prd_verbatim_without_derived_from_errors():
    s = dict(STORY, provenance="prd-verbatim")
    errs = l13_errors({"stories/US-T": (s, "")})
    assert any("no derived_from" in e for e in errs), errs


def test_prd_interpreted_needs_a_resolution_per_ac():
    s = dict(STORY, provenance="prd-interpreted", derived_from=["/sources/prd/1-1.md"])
    errs = l13_errors({"stories/US-T": (s, ""),
                       "resolutions/R-T": (_res("/stories/US-T.md#HS-01"), "")})
    assert len(errs) == 1 and "HS-02" in errs[0], errs


def test_fully_resolved_prd_interpreted_story_passes():
    s = dict(STORY, provenance="prd-interpreted", derived_from=["/sources/prd/1-1.md"])
    res = _res("/stories/US-T.md#HS-01", "/stories/US-T.md#HS-02")
    assert l13_errors({"stories/US-T": (s, ""), "resolutions/R-T": (res, "")}) == []


def test_prd_verbatim_with_bare_string_acs_errors():
    s = dict(STORY, provenance="prd-verbatim", derived_from=["/sources/prd/1-1.md"],
             acceptance_criteria=["The system shall do X", "The system shall do Y"])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert errs, "prd-verbatim ACs must be validated for structure"


def test_prd_verbatim_with_ac_missing_id_errors():
    s = dict(STORY, provenance="prd-verbatim", derived_from=["/sources/prd/1-1.md"],
             acceptance_criteria=[{"text": "a"}])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert errs, "prd-verbatim ACs must have ids"


def test_sourceless_story_without_provenance_errors():
    errs = l13_errors({"stories/US-T": (dict(STORY), "")})
    assert any("provenance" in e for e in errs), errs


def test_sourceless_story_needs_a_resolution_per_ac():
    s = dict(STORY, provenance="human-stated")
    errs = l13_errors({"stories/US-T": (s, ""),
                       "resolutions/R-T": (_res("/stories/US-T.md#HS-01"), "")})
    assert len(errs) == 1, errs
    assert "HS-02" in errs[0], errs


def test_fully_resolved_sourceless_story_passes():
    s = dict(STORY, provenance="human-stated")
    res = _res("/stories/US-T.md#HS-01", "/stories/US-T.md#HS-02")
    assert l13_errors({"stories/US-T": (s, ""), "resolutions/R-T": (res, "")}) == []


def test_unknown_provenance_value_errors():
    s = dict(STORY, provenance="invented")
    errs = l13_errors({"stories/US-T": (s, "")})
    assert any("provenance" in e for e in errs), errs


def test_sourceless_story_with_bare_string_acs_errors():
    # The cheapest evasion: omit the {id, text} structure entirely and L13
    # must still catch it -- it must not depend on isinstance(ac, dict).
    s = dict(STORY, provenance="human-stated",
              acceptance_criteria=["The system shall do X",
                                    "The system shall do Y"])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert errs, "bare-string ACs on a source-less story must be caught"


def test_sourceless_story_dict_ac_missing_id_errors():
    s = dict(STORY, provenance="human-stated",
              acceptance_criteria=[{"text": "a"}])
    errs = l13_errors({"stories/US-T": (s, "")})
    assert errs, errs
    assert "None" not in errs[0], errs
    assert "id" in errs[0], errs


FIXTURE_ID = "US-TESTFIXTURE-L13GATE"
FIXTURE_PATH = ROOT / "stories" / f"{FIXTURE_ID}.md"
FIXTURE_MD = f"""---
type: User Story
id: {FIXTURE_ID}
title: L13 gate fixture (temporary, deleted by the test)
description: Ephemeral fixture written by test_wiki_l13.py to exercise
  cmd_gate's empty-acceptance_criteria refusal; deleted in the test's
  finally block and must never survive the run.
status: aligned
acceptance_criteria: []
---

Ephemeral gate-fixture story, deleted by the test that wrote it.
"""


FIXTURE_BARESTRING_ID = "US-TESTFIXTURE-L13BARESTRING"
FIXTURE_BARESTRING_PATH = ROOT / "stories" / f"{FIXTURE_BARESTRING_ID}.md"
FIXTURE_BARESTRING_MD = f"""---
type: User Story
id: {FIXTURE_BARESTRING_ID}
title: L13 bare-string fixture (temporary, deleted by the test)
description: Ephemeral fixture written by test_wiki_l13.py to prove lint
  reaches L13 for bare-string ACs through the real CLI (cmd_lint), instead
  of crashing earlier in voided_ac_refs with an AttributeError. Deleted in
  the test's finally block and must never survive the run.
status: aligned
provenance: human-stated
acceptance_criteria:
  - "The system shall do X"
  - "The system shall do Y"
---

Ephemeral fixture, deleted by the test that wrote it.
"""


def _git_porcelain():
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                          capture_output=True, text=True).stdout


def test_gate_refuses_story_with_empty_acceptance_criteria():
    # Diff against a baseline rather than asserting total cleanliness -- the
    # repo may legitimately carry unrelated uncommitted work (e.g. this very
    # file, mid-edit). What must be true is that THIS test adds nothing that
    # survives its own finally block.
    baseline = _git_porcelain()
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(FIXTURE_MD, encoding="utf-8", newline="\n")
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "wiki.py"), "gate",
             "--story", FIXTURE_ID],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "has no acceptance_criteria" in r.stdout, r.stdout
    finally:
        if FIXTURE_PATH.exists():
            FIXTURE_PATH.unlink()
    after = _git_porcelain()
    assert after == baseline, \
        f"fixture left the repo dirty -- before:\n{baseline}\nafter:\n{after}"


def test_lint_cli_reaches_l13_for_bare_string_acs():
    # Regression for the real bug: voided_ac_refs() used to call ac.get(...)
    # on every AC unconditionally, and cmd_lint calls voided_ac_refs() BEFORE
    # l13_errors() runs. A bare-string AC therefore crashed lint with an
    # AttributeError (stack trace on stderr) before L13 ever got a chance to
    # report it as a clean ERROR line -- and cmd_gate only forwards stdout
    # lines starting with "ERROR", so the operator saw "GATE BLOCKED: -
    # L-series lint errors exist:" and nothing else. This must go through
    # the actual `py tools/wiki.py lint` subprocess, not l13_errors() called
    # directly, or it would not have caught the ordering bug at all.
    baseline = _git_porcelain()
    FIXTURE_BARESTRING_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_BARESTRING_PATH.write_text(FIXTURE_BARESTRING_MD, encoding="utf-8",
                                        newline="\n")
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "wiki.py"), "lint",
             "--no-commit"],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "Traceback" not in r.stderr, r.stderr
        assert "AttributeError" not in r.stderr, r.stderr
        error_lines = [ln for ln in r.stdout.splitlines()
                       if ln.startswith("ERROR")]
        assert any("L13" in ln and FIXTURE_BARESTRING_ID in ln
                   for ln in error_lines), r.stdout
        assert any("is not a mapping" in ln for ln in error_lines), r.stdout
    finally:
        if FIXTURE_BARESTRING_PATH.exists():
            FIXTURE_BARESTRING_PATH.unlink()
    after = _git_porcelain()
    assert after == baseline, \
        f"fixture left the repo dirty -- before:\n{baseline}\nafter:\n{after}"


def test_w6_silent_when_verbatim_ac_text_is_in_a_cited_section():
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text": "The system shall lock the record on submit."}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    body = "Some preamble. The system shall lock the record on submit. More text."
    assert w6_warnings({"stories/US-T": (s, ""), "sources/prd/1-1": (prd, body)}) == []


def test_w6_warns_when_verbatim_ac_text_is_absent_from_every_cited_section():
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text": "The system shall email the auditor nightly."}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    warns = w6_warnings({"stories/US-T": (s, ""),
                         "sources/prd/1-1": (prd, "Unrelated prose about layout.")})
    assert len(warns) == 1 and "AC1" in warns[0], warns


def test_w6_ignores_interpreted_and_human_stated_stories():
    from wiki import w6_warnings
    for prov in ("prd-interpreted", "human-stated"):
        s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
             "provenance": prov, "acceptance_criteria": [{"id": "AC1", "text": "x" * 40}]}
        if prov == "prd-interpreted":
            s["derived_from"] = ["/sources/prd/1-1.md"]
        assert w6_warnings({"stories/US-T": (s, "")}) == [], prov


def test_w6_realistic_reflowed_table_cell_does_not_warn():
    """The real failure mode a substring test choked on: a Phase A AC reflows
    a PRD table cell into one prose sentence, while the stored section body
    keeps the table's pipe rows and intra-cell breaks. Token coverage should
    see through that and not warn."""
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text":
             "The amount entered must not exceed the approved credit limit "
             "for the customer account."}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    body = ("| Field | Validation |\n| --- | --- |\n"
             "| Amount | The amount entered must not / exceed the approved "
             "credit limit for the / customer account. |")
    assert w6_warnings({"stories/US-T": (s, ""), "sources/prd/1-1": (prd, body)}) == []


def test_w6_invented_ac_warns():
    """An AC with almost no vocabulary overlap with its cited section is the
    case W6 exists to catch."""
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text":
             "The system shall email the auditor nightly with a summary."}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    body = "Unrelated prose about layout and screen colors."
    warns = w6_warnings({"stories/US-T": (s, ""), "sources/prd/1-1": (prd, body)})
    assert len(warns) == 1 and "AC1" in warns[0], warns


def _coverage_fixture(hits):
    """A 20-token AC where exactly `hits` of its tokens appear in the cited
    section, for pinning the 0.75 threshold precisely (each token is 5% of
    coverage)."""
    ac_tokens = [f"tok{i}" for i in range(20)]
    hay_tokens = ac_tokens[:hits]
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text": " ".join(ac_tokens)}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    body = " ".join(hay_tokens)
    return {"stories/US-T": (s, ""), "sources/prd/1-1": (prd, body)}


def test_w6_at_threshold_coverage_does_not_warn():
    """15/20 = 0.75 exactly -- 'below 0.75' must not include the boundary."""
    from wiki import w6_warnings
    assert w6_warnings(_coverage_fixture(15)) == []


def test_w6_just_below_threshold_warns():
    """14/20 = 0.70 -- one token short of the boundary must warn."""
    from wiki import w6_warnings
    warns = w6_warnings(_coverage_fixture(14))
    assert len(warns) == 1 and "AC1" in warns[0], warns


def test_w6_skips_story_when_derived_from_unresolved():
    """A prd-verbatim story whose derived_from points nowhere is an L2/L13
    fault, not a W6 one -- W6 must stay silent rather than warn at 0%
    coverage and misattribute the fault."""
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/missing.md"],
         "acceptance_criteria": [{"id": "AC1", "text": "x" * 40}]}
    assert w6_warnings({"stories/US-T": (s, "")}) == []


def test_w6_still_warns_on_genuinely_absent_ac():
    """Genuinely absent AC should still warn (guard against over-correcting)."""
    from wiki import w6_warnings
    s = {"type": "User Story", "id": "US-T", "title": "t", "description": "d",
         "provenance": "prd-verbatim", "derived_from": ["/sources/prd/1-1.md"],
         "acceptance_criteria": [{"id": "AC1", "text": "The system shall transform lead into gold."}]}
    prd = {"type": "PRD Section", "id": "prd#1-1", "title": "t", "description": "d"}
    body = "The user can filter by status and export results."
    warns = w6_warnings({"stories/US-T": (s, ""), "sources/prd/1-1": (prd, body)})
    assert len(warns) == 1 and "AC1" in warns[0], warns


def test_l13_rejects_a_story_sourced_only_from_reference_material():
    from wiki import l13_errors
    concepts = {
        "stories/US-1": ({
            "type": "User Story", "id": "US-1",
            "provenance": "prd-interpreted",
            "derived_from": ["/sources/reference/L-control-a-rules.md"],
            "acceptance_criteria": [{"id": "AC-1", "text": "x"}],
        }, "body"),
    }
    errs = [e for e in l13_errors(concepts) if "sources/prd/" in e]
    assert errs, l13_errors(concepts)


def test_l13_accepts_a_story_mixing_prd_and_reference_sources():
    from wiki import l13_errors
    concepts = {
        "stories/US-2": ({
            "type": "User Story", "id": "US-2",
            "provenance": "prd-interpreted",
            "derived_from": ["/sources/prd/3-1.md",
                             "/sources/reference/L-control-a-rules.md"],
            "acceptance_criteria": [{"id": "AC-1", "text": "x"}],
        }, "body"),
    }
    errs = [e for e in l13_errors(concepts) if "sources/prd/" in e]
    assert not errs, errs


def test_l13_still_accepts_human_stated_with_no_sources():
    from wiki import l13_errors
    concepts = {
        "stories/US-3": ({
            "type": "User Story", "id": "US-3",
            "provenance": "human-stated",
            "acceptance_criteria": [{"id": "AC-1", "text": "x"}],
        }, "body"),
    }
    errs = [e for e in l13_errors(concepts) if "sources/prd/" in e]
    assert not errs, errs


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_l13 OK")
