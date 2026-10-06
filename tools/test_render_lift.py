#!/usr/bin/env python3
"""Tests: the confidence lift, the raise ratchet and the lift-aware skip.

Pure functions of tools/wiki_doubts.py are tested on data. The two renderers
are driven as subprocesses of a COPY of the tools in a throwaway project
(tools/doubts_scratch.py render_project()); the real repository is never
touched."""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import doubts_scratch  # noqa: E402
import wiki_doubts  # noqa: E402

SC = "SC-X-01"
RES = "/resolutions/R-US-X-02.md"


class Skip(Exception):
    pass


def _lifts(*entries):
    out = {}
    for doubt, basis, rid in entries:
        out.setdefault(doubt, []).append({
            "basis": basis, "resolution": rid, "question": "Q-US-X-01",
            "by": "operator", "date": "2026-10-05"})
    return out


CONF = {"scenario": "High", "steps": "Medium", "data": "Low", "expected": "High"}
REM = {"steps": "Order assumed.", "data": "Profile unconfirmed."}


# ------------------------------------------------------------------ pure
def test_lift_on_basis_match():
    lifts = _lifts((f"{SC}#data", "h-data", "R-US-X-02"))
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, REM, SC, {"data": "h-data", "steps": "h-steps"}, lifts)
    assert conf["data"] == "High" and conf["steps"] == "Medium", conf
    assert rem["data"] == ("Source: R-US-X-02 - human answer to Q-US-X-01 "
                           "(operator, 2026-10-05)."), rem
    assert rem["steps"] == "Order assumed."
    assert lifted == {"data": {"authored": "Low", "resolution": RES}}, lifted
    assert list(lifted["data"]) == ["authored", "resolution"]


def test_no_lift_on_basis_mismatch():
    lifts = _lifts((f"{SC}#data", "old", "R-US-X-02"))
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, REM, SC, {"data": "new"}, lifts)
    assert (conf, rem, lifted) == (CONF, REM, {})
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, REM, SC, {}, lifts)
    assert lifted == {}


def test_corrects_and_unasserted_give_no_lift():
    base = {"type": "Resolution", "answers": "Q-US-X-01", "card": "c.json",
            "asserted_by": "h", "asserted_at": "2026-10-05T10:00:00+08:00"}
    corr = {**base, "id": "R-US-X-01", "status": "asserted", "effect": "corrects",
            "member_basis": {f"{SC}#data": "b"}}
    draft = {**base, "id": "R-US-X-02", "status": "proposed",
             "effect": "confirms", "confirmed_parts": {f"{SC}#data": "b"}}
    other = {"type": "Resolution", "id": "R-US-X-03", "status": "asserted"}
    assert wiki_doubts.lifts_from([corr, draft, other, "junk", None]) == {}
    good = {**base, "id": "R-US-X-04", "status": "asserted",
            "effect": "confirms", "confirmed_parts": {f"{SC}#data": "b"}}
    out = wiki_doubts.lifts_from([corr, draft, good])
    assert out == {f"{SC}#data": [{
        "basis": "b", "resolution": "R-US-X-04", "question": "Q-US-X-01",
        "by": "h", "date": "2026-10-05"}]}, out


def test_lifts_from_order_and_highest_wins():
    def r(n, basis):
        return {"id": f"R-US-X-{n}", "status": "asserted", "effect": "confirms",
                "answers": f"Q-{n}", "card": "c.json", "asserted_by": "h",
                "asserted_at": "2026-10-05T10:00:00+08:00",
                "confirmed_parts": {f"{SC}#data": basis}}
    out = wiki_doubts.lifts_from([r("10", "b"), r("02", "b"), r("03", "z")])
    assert [x["resolution"] for x in out[f"{SC}#data"]] == [
        "R-US-X-02", "R-US-X-03", "R-US-X-10"]
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, REM, SC, {"data": "b"}, out)
    assert lifted["data"]["resolution"] == "/resolutions/R-US-X-10.md"
    assert "Q-10" in rem["data"]


def test_high_part_untouched_and_inputs_not_mutated():
    lifts = _lifts((f"{SC}#expected", "b", "R-US-X-02"),
                   (f"{SC}#data", "d", "R-US-X-02"))
    conf0, rem0 = copy.deepcopy(CONF), copy.deepcopy(REM)
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, REM, SC, {"expected": "b", "data": "d"}, lifts)
    assert "expected" not in lifted and conf["expected"] == "High"
    assert "expected" not in rem
    assert CONF == conf0 and REM == rem0
    assert conf is not CONF and rem is not REM


def test_no_lifts_outputs_equal_inputs():
    for lifts in ({}, None):
        conf, rem, lifted = wiki_doubts.effective_confidence(
            CONF, REM, SC, {"data": "b"}, lifts)
        assert conf == CONF and rem == REM and lifted == {}
    conf, rem, lifted = wiki_doubts.effective_confidence(
        CONF, None, SC, {}, {})
    assert rem == {} and lifted == {}


def _fm(**parts):
    return {"confidence_parts": {p: v for p, v in parts.items()}}


def _p(level, authored=None):
    d = {"level": level, "remark": ""}
    if authored:
        d.update(authored=authored, resolution="/resolutions/R-1.md")
    return d


def _conf(**kw):
    c = {"scenario": "High", "steps": "High", "data": "High", "expected": "High"}
    c.update(kw)
    return c


def _full(**kw):
    p = {k: _p("High") for k in ("scenario", "steps", "data", "expected")}
    p.update(kw)
    return _fm(**p)


def test_raise_refused_low_medium_to_high_and_low_to_medium():
    errs = wiki_doubts.raise_errors(_full(data=_p("Low")), _conf(), "W")
    assert len(errs) == 1 and errs[0].startswith(
        "W: confidence.data raised from Low to High - only a human answer "
        "raises a level"), errs
    errs = wiki_doubts.raise_errors(_full(steps=_p("Medium")), _conf(), "W")
    assert "confidence.steps raised from Medium to High" in errs[0]
    errs = wiki_doubts.raise_errors(_full(data=_p("Low")),
                                    _conf(data="Medium"), "W")
    assert "confidence.data raised from Low to Medium" in errs[0]
    errs = wiki_doubts.raise_errors(_full(data=_p("Low")), _conf(), "W",
                                    story="US-X")
    assert "doubts card --story US-X" in errs[0]


def test_raise_lowering_and_equal_allowed():
    assert wiki_doubts.raise_errors(
        _full(), _conf(data="Low", steps="Medium"), "W") == []
    assert wiki_doubts.raise_errors(
        _full(data=_p("Low")), _conf(data="Low"), "W") == []
    assert wiki_doubts.raise_errors(
        _full(data=_p("Medium")), _conf(data="Low"), "W") == []


def test_raise_lifted_part_is_not_a_raise():
    prior = _full(data=_p("High", authored="Medium"))
    assert wiki_doubts.raise_errors(prior, _conf(data="Medium"), "W") == []
    errs = wiki_doubts.raise_errors(prior, _conf(data="High"), "W")
    assert "confidence.data raised from Medium to High" in errs[0], errs
    assert wiki_doubts.raise_errors(prior, _conf(data="Low"), "W") == []


def test_raise_no_prior_gives_no_errors():
    assert wiki_doubts.raise_errors(None, _conf(), "W") == []
    assert wiki_doubts.raise_errors({}, _conf(), "W") == []
    assert wiki_doubts.raise_errors({"id": "x"}, _conf(), "W") == []
    assert wiki_doubts.raise_errors({"confidence_parts": None}, _conf(),
                                    "W") == []


def test_lifted_parts_projection():
    fm = _full(data=_p("High", authored="Low"), steps=_p("Medium"))
    assert wiki_doubts.lifted_parts(fm["confidence_parts"]) == {
        "data": "/resolutions/R-1.md"}
    assert wiki_doubts.lifted_parts(None) == {}
    assert wiki_doubts.lifted_parts({}) == {}
    assert wiki_doubts.lifted_parts(_full()["confidence_parts"]) == {}


def test_merge_lifted_key_order():
    parts = {"data": {"level": "High", "remark": "r"},
             "steps": {"level": "Medium", "remark": "s"}}
    out = wiki_doubts.merge_lifted(
        parts, {"data": {"authored": "Low", "resolution": RES}})
    assert list(out["data"]) == ["level", "remark", "authored", "resolution"]
    assert out["steps"] == parts["steps"]
    assert "authored" not in parts["data"]


# ---------------------------------------------------------------- scratch
PY = sys.executable
STORY = doubts_scratch.RSTORY
FLOW = doubts_scratch.RFLOW
Q1 = f"Q-{STORY}-01"
Q2 = f"Q-{STORY}-02"
SIT_SPEC = f"tools/sit_specs/{STORY}.yaml"
UAT_SPEC = f"tools/uat_specs/{FLOW}.yaml"
TC_A = "testcases/sit/lift-fixture/9.9-AC01-01.md"
TC_B = "testcases/sit/lift-fixture/9.9-AC02-01.md"
TC_C = "testcases/sit/lift-fixture/9.9-AC02-02.md"
U1 = "testcases/uat/UAT-9.9-AC01-01.md"
U2 = "testcases/uat/UAT-9.9-AC02-01.md"
ALL_TCS = (TC_A, TC_B, TC_C, U1, U2)
BY = "tester"


def _run(d, *args):
    r = subprocess.run([PY, *args], cwd=d, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def _sit(d, *extra):
    return _run(d, "tools/render_sit.py", "--story", STORY, *extra)


def _uat(d, *extra):
    return _run(d, "tools/render_uat.py", "--flow", FLOW, *extra)


def _wiki(d, *args):
    code, out, err = _run(d, "tools/wiki.py", *args)
    assert code == 0, (args, out, err)
    return out


def _rendered(out):
    return int(out.split("rendered ")[1].split(",")[0])


def _bytes(d):
    return {t: (d / t).read_bytes() for t in ALL_TCS}


def _fm_body(path):
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body


def _answer_card(d, answers):
    """Emit a card for the questions, answer it with the real `card revise`,
    apply it with `doubts answer`. Returns the new Resolution file names."""
    before = {p.name for p in (d / "resolutions").glob("*.md")}
    out = _wiki(d, "doubts", "card", "--story", STORY,
                "--question", ",".join(answers))
    rel = out.splitlines()[0].split(":")[0]
    args = ["card", "revise", rel, "--by", BY]
    for q, v in answers.items():
        args += ["--answer", f"{q}={v}"]
    _wiki(d, *args)
    _wiki(d, "doubts", "answer", "--card", rel, "--by", BY)
    return sorted({p.name for p in (d / "resolutions").glob("*.md")} - before)


def _edit_spec(d, rel, fn):
    p = d / rel
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    fn(spec)
    p.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True),
                 encoding="utf-8", newline="\n")


def _with_project(fn):
    d = doubts_scratch.render_project()
    try:
        return fn(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _sit_tc(spec, ac, seq):
    return next(t for t in spec["test_cases"]
                if t["ac"] == ac and t["seq"] == seq)


def test_lift_lifecycle_in_both_renderers():
    """Baseline, correcting answer, confirming answer, second run, reopen."""
    def go(d):
        # baseline: nothing lifted, nothing re-rendered
        assert _rendered(_sit(d)[1]) == 0
        assert _rendered(_uat(d)[1]) == 0
        base = _bytes(d)

        # a correcting answer lifts nothing
        rids = _answer_card(d, {Q2: "The page shows a timeout banner."})
        assert len(rids) == 1
        assert _wiki_has(d, rids[0], "effect: corrects")
        c, out, err = _sit(d)
        assert c == 0 and _rendered(out) == 0, out + err
        c, out, err = _uat(d)
        assert c == 0 and _rendered(out) == 0, out + err
        assert _bytes(d) == base

        # a confirming answer lifts exactly the confirmed parts
        rids = _answer_card(d, {Q1: "accept"})
        rid = rids[0].removesuffix(".md")
        c, out, err = _sit(d)
        assert c == 0 and _rendered(out) == 1, out + err
        c, out, err = _uat(d)
        assert c == 0 and _rendered(out) == 1, out + err
        src = (f"Source: {rid} - human answer to {Q1} ({BY}, ")
        fm, body = _fm_body(d / TC_A)
        cp = fm["confidence_parts"]
        for part, authored in (("steps", "Medium"), ("data", "Low")):
            assert cp[part]["level"] == "High", cp
            assert cp[part]["authored"] == authored
            assert cp[part]["resolution"] == f"/resolutions/{rid}.md"
            assert cp[part]["remark"].startswith(src), cp[part]
            assert list(cp[part]) == ["level", "remark", "authored", "resolution"]
            assert src in body
        for part in ("scenario", "expected"):
            assert set(cp[part]) == {"level", "remark"}, cp[part]
        assert fm["confidence"] == "High"
        assert f"- **Field / Values**: High - {src}" in body, body
        assert "**High** (lowest of the four parts)" in body
        fm_u, body_u = _fm_body(d / U1)
        assert fm_u["confidence_parts"]["data"]["authored"] == "Medium"
        assert fm_u["confidence_parts"]["steps"] == {
            "level": "Medium", "remark": "Assumed."}
        assert fm_u["confidence"] == "Medium"
        assert src in body_u
        after = _bytes(d)
        for t in (TC_B, TC_C, U2):
            assert after[t] == base[t], f"{t} changed"
        assert after[TC_A] != base[TC_A] and after[U1] != base[U1]

        # a second run touches nothing
        c, out, err = _sit(d)
        assert c == 0 and _rendered(out) == 0, out + err
        c, out, err = _uat(d)
        assert c == 0 and _rendered(out) == 0, out + err
        assert _bytes(d) == after
        # a forced render of a lifted file is not a raise (authored is kept)
        c, out, err = _sit(d, "--force")
        assert c == 0 and "raised from" not in err, out + err
        # HEAD moved since TC_B and TC_C were rendered (the answers were
        # committed), but their text did not change: a forced render leaves
        # them byte for byte, wiki_commit included, so their sealed hashes hold
        assert _rendered(out) == 0 and "unchanged 3 (same text)" in out, out
        c, out, err = _uat(d, "--force")
        assert c == 0 and "raised from" not in err, out + err
        assert _rendered(out) == 0 and "unchanged 2 (same text)" in out, out
        fm, _b = _fm_body(d / TC_A)
        assert fm["confidence_parts"]["data"]["authored"] == "Low"
        assert _bytes(d) == after, "a forced render rewrote an unchanged file"

        # reopen: rewrite the lifted steps text; only that test case re-renders
        # back to its authored level, the data part (other text) stays lifted
        _edit_spec(d, SIT_SPEC, lambda s: _sit_tc(s, "HS-01", 1).update(
            steps="1. Open the page.\n2. Submit twice."))
        c, out, err = _sit(d)
        assert c == 0 and _rendered(out) == 1, out + err
        fm, body = _fm_body(d / TC_A)
        cp = fm["confidence_parts"]
        assert cp["steps"] == {"level": "Medium", "remark": "Order assumed."}, cp
        assert cp["data"]["authored"] == "Low" and cp["data"]["level"] == "High"
        assert fm["confidence"] == "Medium"
        assert _bytes(d)[TC_B] == after[TC_B] and _bytes(d)[TC_C] == after[TC_C]
        c, out, err = _sit(d)
        assert _rendered(out) == 0, out + err

        # reopen in UAT: the data basis is the steps text
        _edit_spec(d, UAT_SPEC, lambda s: s["entries"]["J01"].update(
            steps="1. Log in with profile B."))
        c, out, err = _uat(d)
        assert c == 0 and _rendered(out) == 1, out + err
        fm_u, body_u = _fm_body(d / U1)
        for part in ("steps", "data"):
            assert set(fm_u["confidence_parts"][part]) == {"level", "remark"}
        assert fm_u["confidence"] == "Medium"
        assert src not in body_u
        assert _bytes(d)[U2] == after[U2]
        assert _rendered(_uat(d)[1]) == 0
    _with_project(go)


def _wiki_has(d, rid, text):
    return text in (d / "resolutions" / rid).read_text(encoding="utf-8")


def _git(d, *args):
    r = subprocess.run(["git", *args], cwd=d, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


def _tc_edit(d, tc_id, field, text):
    """The real `wiki tc edit` of the scratch copy: (exit code, output)."""
    src = d / "build/edits/lift-test.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(text.encode("utf-8"))
    c, out, err = _run(d, "tools/wiki.py", "tc", "edit", tc_id, "--field",
                       field, "--from", "build/edits/lift-test.txt", "--by", BY)
    return c, out + err


def test_tc_edit_of_a_confirmed_part_returns_it_to_its_authored_level():
    """`wiki tc edit` forces a render of the whole story or flow. A confirmed
    (lifted) part whose text the edit does not touch stays lifted; one whose
    text it changes returns to its authored level and remark, because the
    confirmation was of the old text. Neither is a raise, so the ratchet says
    nothing, the edit is one commit and nothing is rolled back."""
    def go(d):
        rid = _answer_card(d, {Q1: "accept"})[0].removesuffix(".md")
        assert _rendered(_sit(d)[1]) == 1 and _rendered(_uat(d)[1]) == 1
        _wiki(d, "seal", "--no-commit")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "scratch: render and seal the lifts\n\n"
             "Assertion-Event: scratch-fixture " + STORY)
        ref = f"/resolutions/{rid}.md"
        spec0 = yaml.safe_load((d / SIT_SPEC).read_text(encoding="utf-8"))
        conf0 = _sit_tc(spec0, "HS-01", 1)["confidence"]
        sealed = _bytes(d)
        hashes0 = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["tc_hashes"]

        # the title is the scenario part's text: both lifts survive the forced
        # render, and so do the other test cases of the story
        head = _git(d, "rev-parse", "HEAD")
        c, out = _tc_edit(d, "9.9-AC01-01", "title", "Lift title one reworded")
        assert c == 0 and "saved by tester" in out, out
        assert "raised from" not in out, out
        assert _git(d, "rev-list", "--count", f"{head}..HEAD") == "1"
        assert _git(d, "status", "--porcelain") == "", "tree not clean"
        fm, _b = _fm_body(d / TC_A)
        assert fm["title"] == "Lift title one reworded"
        for part, authored in (("steps", "Medium"), ("data", "Low")):
            assert fm["confidence_parts"][part]["level"] == "High"
            assert fm["confidence_parts"][part]["authored"] == authored
            assert fm["confidence_parts"][part]["resolution"] == ref
        assert (d / TC_B).exists() and (d / TC_C).exists()
        assert "no longer applies" not in out and "also rendered" not in out, out
        # one edit changes one test case: the forced render leaves the files
        # whose text did not change, so their sealed hashes (and every
        # compiled workbook's view of them) stay as they were
        assert _bytes(d)[TC_B] == sealed[TC_B] and _bytes(d)[TC_C] == sealed[TC_C]
        touched = [n for n in _git(d, "show", "--format=", "--name-only",
                                   "HEAD").splitlines()
                   if n.startswith("testcases/") and not n.endswith("index.md")]
        assert touched == [TC_A], touched
        hashes = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["tc_hashes"]
        assert {r for r, h in hashes.items() if h != hashes0[r]} == \
            {TC_A.removesuffix(".md")}, "one edit must change one sealed hash"

        # the steps text is what the human confirmed: editing it reopens the
        # steps part at its authored level; the data part (other text) stays
        head = _git(d, "rev-parse", "HEAD")
        c, out = _tc_edit(d, "9.9-AC01-01", "steps",
                          "1. Open the page.\n2. Submit twice.")
        assert c == 0 and "saved by tester" in out, out
        assert "raised from" not in out and "refused" not in out, out
        assert _git(d, "rev-list", "--count", f"{head}..HEAD") == "1"
        assert _git(d, "log", "-1", "--format=%an|%s") == \
            "tc-agent|tc edit(9.9-AC01-01): steps by tester"
        assert _git(d, "status", "--porcelain") == "", "tree not clean"
        # a human's confirmation stopped applying: the command, the log and
        # the commit all say so, naming the Resolution, the test case and
        # the part (the data part's confirmation still holds: no line for it)
        voided = (f"confirmation {rid} of 9.9-AC01-01 steps no longer applies "
                  f"(text changed)")
        assert voided in out, out
        assert voided in (d / "log.md").read_text(encoding="utf-8").splitlines()[-1]
        assert voided in _git(d, "log", "-1", "--format=%b")
        assert "9.9-AC01-01 data no longer applies" not in out, out
        fm, body = _fm_body(d / TC_A)
        cp = fm["confidence_parts"]
        assert cp["steps"] == {"level": "Medium", "remark": "Order assumed."}, cp
        assert cp["data"]["level"] == "High" and cp["data"]["authored"] == "Low"
        assert cp["data"]["resolution"] == ref
        assert fm["confidence"] == "Medium"
        assert "2. Submit twice." in body
        spec = yaml.safe_load((d / SIT_SPEC).read_text(encoding="utf-8"))
        assert _sit_tc(spec, "HS-01", 1)["confidence"] == conf0, \
            "an edit never changes an authored level"
        states = {x["doubt"]: x["state"] for x in
                  wiki_doubts.story_summary(STORY, root=d)["doubts"]}
        assert states["SC-LIFT-HS-01-01#steps"] == "open", states
        assert states["SC-LIFT-HS-01-01#data"] == "closed", states
        c, out, err = _run(d, "tools/wiki.py", "lint", "--no-commit")
        assert c == 0 and "0 error(s)" in out and "W9 " not in out, out + err
        # sealed as rendered: a plain render afterwards has nothing to do
        assert _rendered(_sit(d)[1]) == 0

        # UAT: the data part's basis is the steps text, so editing the steps
        # returns the confirmed data part to its authored level
        fm_u, _b = _fm_body(d / U1)
        assert fm_u["confidence_parts"]["data"]["resolution"] == ref
        head = _git(d, "rev-parse", "HEAD")
        c, out = _tc_edit(d, "UAT-9.9-AC01-01", "steps",
                          "1. Log in with profile B.")
        assert c == 0 and "saved by tester" in out, out
        assert "raised from" not in out, out
        assert _git(d, "rev-list", "--count", f"{head}..HEAD") == "1"
        assert _git(d, "status", "--porcelain") == "", "tree not clean"
        fm_u, body_u = _fm_body(d / U1)
        assert fm_u["confidence_parts"]["data"] == {
            "level": "Medium", "remark": "Profile guessed."}, fm_u
        assert fm_u["confidence_parts"]["steps"] == {
            "level": "Medium", "remark": "Assumed."}
        assert f"Source: {rid}" not in body_u
        c, out, err = _run(d, "tools/wiki.py", "lint", "--no-commit")
        assert c == 0 and "0 error(s)" in out and "W9 " not in out, out + err
        assert _rendered(_uat(d)[1]) == 0
    _with_project(go)


def test_tc_edit_says_when_it_also_renders_a_pending_lift():
    """A confirmed answer that was never rendered is rendered by the edit's
    forced render, in the edit's commit. That is a level change riding on a
    rewording, so the command, the log and the commit name the Resolution."""
    def go(d):
        rid = _answer_card(d, {Q1: "accept"})[0].removesuffix(".md")
        assert _git(d, "status", "--porcelain") == ""
        fm, _b = _fm_body(d / TC_A)
        assert "resolution" not in fm["confidence_parts"]["steps"], "not rendered yet"
        c, out = _tc_edit(d, "9.9-AC02-01", "title", "Lift title two reworded")
        assert c == 0 and "saved by tester" in out, out
        note = f"also rendered 1 confirmed lift(s): {rid}"
        assert note in out, out
        assert note in (d / "log.md").read_text(encoding="utf-8").splitlines()[-1]
        assert note in _git(d, "log", "-1", "--format=%b")
        assert "no longer applies" not in out, out
        fm, _b = _fm_body(d / TC_A)
        assert fm["confidence_parts"]["steps"]["resolution"] == f"/resolutions/{rid}.md"
    _with_project(go)


def test_the_drift_refusal_names_seal_for_a_render_that_was_not_sealed():
    """`doubts answer` prints "render ... then seal". Stopping after the
    render leaves the lifted file unsealed; `revert` would throw the render
    away, so the refusal must name `seal` for this case."""
    def go(d):
        _answer_card(d, {Q1: "accept"})
        assert _rendered(_sit(d)[1]) == 1
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "scratch: rendered, not sealed\n\n"
             "Assertion-Event: scratch-fixture " + STORY)
        head = _git(d, "rev-parse", "HEAD")
        c, out = _tc_edit(d, "9.9-AC02-01", "title", "Never lands")
        assert c != 0 and "tc edit refused" in out, out
        assert "If you have just rendered" in out and "py tools/wiki.py seal" in out, out
        assert "wiki release" in out and "wiki revert" in out, out
        assert _git(d, "rev-parse", "HEAD") == head
        assert _git(d, "status", "--porcelain") == "", "a refusal wrote something"
    _with_project(go)


def test_tc_edit_refuses_allow_lint_errors_and_a_signature_that_is_not_a_name():
    def go(d):
        head = _git(d, "rev-parse", "HEAD")
        src = d / "build/edits/lift-test.txt"
        for extra, by, needle in (
                (["--allow-lint-errors"], BY, "--allow-lint-errors is not accepted"),
                ([], "", "it is empty"),
                ([], "  ", "it is empty"),
                ([], "a\nb", "more than one line"),
                ([], "--field", "is a flag, not a name")):
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_bytes(b"Never lands")
            c, out, err = _run(d, "tools/wiki.py", "tc", "edit", "9.9-AC02-01",
                               "--field", "title", "--from",
                               "build/edits/lift-test.txt", "--by", by, *extra)
            assert c != 0 and "tc edit refused" in out + err, (by, extra, out, err)
            assert needle in out + err, (by, extra, out, err)
            assert "Traceback" not in out + err
        assert _git(d, "rev-parse", "HEAD") == head
        assert _git(d, "status", "--porcelain") == "", "a refusal wrote something"
        # --no-commit stays: the rendered edit is left in the tree, uncommitted
        src.write_bytes(b"Lift title two, uncommitted")
        c, out, err = _run(d, "tools/wiki.py", "tc", "edit", "9.9-AC02-01",
                           "--field", "title", "--from",
                           "build/edits/lift-test.txt", "--by", BY, "--no-commit")
        assert c == 0 and "saved by tester" in out, out + err
        assert _git(d, "rev-parse", "HEAD") == head
        assert _git(d, "status", "--porcelain") != ""
    _with_project(go)


def test_tc_edit_of_a_test_case_covering_a_voided_ac_is_refused():
    def go(d):
        import wiki
        story = d / "stories" / f"{STORY}.md"
        fm, body = wiki.read_concept(story)
        ac = fm["acceptance_criteria"][0]
        ac["status"] = "voided"
        ac["voided"] = {"caused_by": "human decision", "cause_version": 1,
                        "asserted_by": BY, "asserted_at": "2026-01-01T00:00:00+08:00"}
        wiki.write_concept(story, fm, body)
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "scratch: an AC voided\n\n"
             "Assertion-Event: scratch-fixture " + STORY)
        head = _git(d, "rev-parse", "HEAD")
        spec = (d / SIT_SPEC).read_bytes()
        c, out = _tc_edit(d, "9.9-AC01-01", "title", "Never lands")
        assert c != 0 and "tc edit refused" in out, out
        assert f"#{ac['id']}, which is voided" in out, out
        assert "Nothing was changed" in out, out
        assert (d / SIT_SPEC).read_bytes() == spec
        assert _git(d, "rev-parse", "HEAD") == head
        assert _git(d, "status", "--porcelain") == "", "a refusal wrote something"
    _with_project(go)


def refuse_sit_raise(d, base):
    """Raise Low -> High and Medium -> High by hand in the SIT spec; both a
    plain and a forced render must refuse and write nothing (shared with the
    smoke fence, tools/fence_raise_ratchet.py)."""
    def raise_sit(s):
        tc = _sit_tc(s, "HS-01", 1)
        tc["confidence"]["data"] = "High"
        tc["confidence"]["steps"] = "High"
    _edit_spec(d, SIT_SPEC, raise_sit)
    for extra in ((), ("--force",)):
        c, out, err = _sit(d, *extra)
        assert c != 0, (extra, out, err)
        assert "confidence.data raised from Low to High" in err, err
        assert "confidence.steps raised from Medium to High" in err, err
        assert "SC-LIFT-HS-01-01" in err, err
        assert "Nothing was written" in err
        assert _bytes(d) == base, "a refused render wrote a file"


def test_ratchet_refuses_a_hand_raised_level_in_both_renderers():
    def go(d):
        # a new scenario has no file yet: High on any part is not a raise
        def add(s):
            new = copy.deepcopy(_sit_tc(s, "HS-02", 2))
            new.update(seq=3, continue_from="HS-02/2",
                       confidence={"scenario": "High", "steps": "High",
                                   "data": "High", "expected": "High"})
            new.pop("remarks")
            s["test_cases"].append(new)
        _edit_spec(d, SIT_SPEC, add)
        c, out, err = _sit(d)
        assert c == 0 and _rendered(out) == 1, out + err
        assert (d / "testcases/sit/lift-fixture/9.9-AC02-03.md").exists()
        base = _bytes(d)
        refuse_sit_raise(d, base)

        # UAT
        _edit_spec(d, UAT_SPEC, lambda s: s["entries"]["J02"]["confidence"]
                   .update(expected="High"))
        for extra in ((), ("--force",)):
            c, out, err = _uat(d, *extra)
            assert c != 0, (extra, out, err)
            assert "confidence.expected raised from Low to High" in err, err
            assert "SC-UAT-LIFT-J02" in err, err
            assert _bytes(d) == base

        # lowering renders (forced) without a ratchet error
        _edit_spec(d, SIT_SPEC, lambda s: (
            _sit_tc(s, "HS-01", 1).update(
                confidence={"scenario": "Medium", "steps": "Medium",
                            "data": "Low", "expected": "High"},
                remarks={"scenario": "Now doubted.", "steps": "Order assumed.",
                         "data": "Profile unconfirmed."})))
        c, out, err = _sit(d, "--force")
        assert c == 0 and "raised from" not in err, out + err
        fm, _b = _fm_body(d / TC_A)
        assert fm["confidence_parts"]["scenario"]["level"] == "Medium"
        _edit_spec(d, UAT_SPEC, lambda s: s["entries"]["J02"].update(
            confidence={"scenario": "Medium", "steps": "High", "data": "High",
                        "expected": "Low"},
            remarks={"scenario": "Now doubted.", "expected": "Outcome guessed."}))
        c, out, err = _uat(d, "--force")
        assert c == 0 and "raised from" not in err, out + err
    _with_project(go)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except Skip as e:
                print(f"[SKIP] {name} ({e})")
            except Exception as e:
                fails += 1
                print(f"[FAIL] {name}: {e}")
    sys.exit(1 if fails else 0)
