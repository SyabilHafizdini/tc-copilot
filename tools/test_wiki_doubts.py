#!/usr/bin/env python3
"""Plain-assert tests for the doubt collectors (run: py tools/test_wiki_doubts.py)."""
import copy
import re
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki
import wiki_doubts

FIX = ROOT / "tools" / "fixtures" / "doubts"


class Skip(Exception):
    pass


def _sit():
    return yaml.safe_load((FIX / "sit_spec.yaml").read_text(encoding="utf-8"))


def _uat():
    return yaml.safe_load((FIX / "uat_spec.yaml").read_text(encoding="utf-8"))


def _flow():
    fm, _ = wiki.read_concept(FIX / "flow.md")
    return fm


def test_sit_fixture_ids():
    rows = wiki_doubts.collect_sit(_sit())
    assert [r["doubt"] for r in rows] == [
        "SC-FIX-US-FIXTURE-DOUBTS-AC1-01#steps",
        "SC-FIX-US-FIXTURE-DOUBTS-AC1-01#data",
        "SC-FIX-US-FIXTURE-DOUBTS-AC2-02#scenario",
        "SC-FIX-US-FIXTURE-DOUBTS-AC2-02#expected",
    ], [r["doubt"] for r in rows]
    r = rows[1]
    assert r["kind"] == "sit" and r["part"] == "data" and r["level"] == "Low"
    assert r["story"] == "stories/US-FIXTURE-DOUBTS"
    assert r["remark"] == "Profile unconfirmed."
    assert r["scenario_id"] == "SC-FIX-US-FIXTURE-DOUBTS-AC1-01"
    assert r["text"] == "Profile A\nMailbox X exists."
    assert rows[3]["remark"] == ""


def test_basis_ignores_whitespace():
    e = {"steps": "1. Open the page.\n2. Submit."}
    b = wiki_doubts.part_basis("sit", e, "steps")
    e2 = {"steps": "1.  Open   the page.  \r\n2. Submit.   \r\n"}
    assert wiki_doubts.part_basis("sit", e2, "steps") == b
    e3 = {"steps": "1. Open the page.\n2. Submit now."}
    assert wiki_doubts.part_basis("sit", e3, "steps") != b


def test_high_part_yields_no_doubt():
    spec = _sit()
    ids = {r["doubt"] for r in wiki_doubts.collect_sit(spec)}
    assert not any("HS-02" in i for i in ids)
    assert not any(i.endswith("AC1-01#scenario") for i in ids)


def test_data_basis_covers_pre_extra():
    spec = _sit()
    before = {r["part"]: r["basis"] for r in wiki_doubts.collect_sit(spec)
              if r["scenario_id"].endswith("AC1-01")}
    spec["test_cases"][0]["pre_extra"] = "Mailbox Y exists."
    after = {r["part"]: r["basis"] for r in wiki_doubts.collect_sit(spec)
             if r["scenario_id"].endswith("AC1-01")}
    assert before["data"] != after["data"]
    assert before["steps"] == after["steps"]


def test_uat_fixture():
    spec = _uat()
    snap = copy.deepcopy(spec)
    rows = wiki_doubts.collect_uat(spec, _flow())
    assert spec == snap, "collect_uat mutated its input"
    assert [r["doubt"] for r in rows] == [
        "SC-UAT-FIX-J01#steps", "SC-UAT-FIX-J01#data", "SC-UAT-FIX-J02#expected"]
    assert rows[0]["story"] == "stories/US-FIXTURE-DOUBTS"
    assert rows[0]["kind"] == "uat"
    assert rows[0]["basis"] == rows[1]["basis"]


def test_uat_without_ref_has_no_story():
    rows = wiki_doubts.collect_uat(_uat(), _flow())
    assert rows[2]["story"] is None
    rows = wiki_doubts.collect_uat(_uat(), {"journey": [{"id": "J01", "ref": "/flows/X.md"}]})
    assert rows[0]["story"] is None
    rows = wiki_doubts.collect_uat(_uat(), {})
    assert all(r["story"] is None for r in rows)


def _count_non_high(spec, entries):
    n = 0
    for e in entries:
        conf = e.get("confidence") or {}
        n += sum(1 for p in ("scenario", "steps", "data", "expected")
                 if conf.get(p, "High") != "High")
    return n


def test_real_content():
    """Every Medium / Low part of every spec this bundle holds is one doubt.
    A content-free bundle has no spec, so there is nothing to count."""
    sit_ps = sorted((ROOT / "tools" / "sit_specs").glob("*.yaml"))
    uat_ps = sorted((ROOT / "tools" / "uat_specs").glob("*.yaml"))
    if not sit_ps and not uat_ps:
        raise Skip("no specs in this bundle")
    expected = 0
    for p in sit_ps:
        sit = yaml.safe_load(p.read_text(encoding="utf-8"))
        expected += _count_non_high(sit, sit["test_cases"])
    for p in uat_ps:
        uat = yaml.safe_load(p.read_text(encoding="utf-8"))
        expected += _count_non_high(uat, list(uat["entries"].values()))
    rows = wiki_doubts.collect_all()
    assert len(rows) == expected, (len(rows), expected)
    ids = [r["doubt"] for r in rows]
    assert len(ids) == len(set(ids)) and ids == sorted(ids)
    uat_rows = [r for r in rows if r["kind"] == "uat"]
    assert bool(uat_rows) == bool(uat_ps), (len(uat_rows), len(uat_ps))
    assert all(str(r["story"]).startswith("stories/") for r in uat_rows)


def test_empty_root():
    with tempfile.TemporaryDirectory() as d:
        assert wiki_doubts.collect_all(root=Path(d)) == []


SID = "SC-FIX-US-FIXTURE-DOUBTS"
Q1, Q2 = "Q-US-FIXTURE-DOUBTS-01", "Q-US-FIXTURE-DOUBTS-02"


def _story():
    return wiki.read_concept(FIX / "story.md")


def _reg():
    return yaml.safe_load((FIX / "register.yaml").read_text(encoding="utf-8"))


def _doubts():
    return wiki_doubts.collect_sit(_sit()) + wiki_doubts.collect_uat(_uat(), _flow())


def _errs(reg, resolutions=()):
    fm, body = _story()
    return wiki_doubts.register_errors(reg, fm, _doubts(), resolutions, body)


def _has(errs, *needles):
    return any(all(n in e for n in needles) for e in errs)


def _q(reg, i=0):
    return reg["questions"][i]


def test_valid_register():
    assert _errs(_reg()) == [], _errs(_reg())


def test_malformed_input_does_not_raise():
    assert _errs([]) and _errs({"story": "/stories/US-FIXTURE-DOUBTS.md", "questions": "x"})
    r = _reg(); r["questions"] = ["not a mapping"]
    assert _has(_errs(r), "register:")
    r = _reg(); _q(r)["members"] = "x"; _q(r)["about"] = 5; _q(r)["home"] = 3
    assert _errs(r)
    r = _reg(); _q(r)["members"] = [7]
    assert _errs(r)


def test_top_level_errors():
    r = _reg(); r["story"] = "/stories/OTHER.md"
    assert _has(_errs(r), "register:", "story")
    r = _reg(); r["extra"] = 1
    assert _has(_errs(r), "register:", "unknown key 'extra'")
    r = _reg(); _q(r)["bogus"] = 1
    assert _has(_errs(r), Q1, "unknown key 'bogus'")


def test_id_errors():
    r = _reg(); _q(r)["id"] = "Q-OTHER-01"
    assert _has(_errs(r), "Q-OTHER-01", "does not match Q-US-FIXTURE-DOUBTS-NN")
    r = _reg(); _q(r, 1)["id"] = Q1
    assert _has(_errs(r), Q1, "duplicate id")


def test_question_text_errors():
    r = _reg(); _q(r)["question"] = ""
    assert _has(_errs(r), Q1, "question must be a non-empty string")
    r = _reg(); _q(r)["question"] = "No mark."
    assert _has(_errs(r), Q1, "question must end with '?'")


def test_about_errors():
    r = _reg(); _q(r)["about"] = []
    assert _has(_errs(r), Q1, "about must be a non-empty list")
    r = _reg(); _q(r)["about"] = ["HS-99"]
    assert _has(_errs(r), Q1, "about 'HS-99' is not a fragment of the story")


def test_home_forms():
    for ok in ("ac:HS-01", "rule:BR-01", "rule:new", "component:CMP-01",
               "table:Scenario data", "none"):
        r = _reg(); _q(r)["home"] = ok
        assert _errs(r) == [], (ok, _errs(r))
    r = _reg(); _q(r)["home"] = "nonsense"
    assert _has(_errs(r), Q1, "home 'nonsense' is not one of")
    r = _reg(); _q(r)["home"] = "ac:HS-99"
    assert _has(_errs(r), Q1, "home ac 'HS-99' is not an acceptance criterion")
    r = _reg(); _q(r)["home"] = "rule:BR-99"
    assert _has(_errs(r), Q1, "home rule 'BR-99' is not a business rule")
    r = _reg(); _q(r)["home"] = "component:CMP-99"
    assert _has(_errs(r), Q1, "home component 'CMP-99' is not a component")
    r = _reg(); _q(r)["home"] = "table:No such heading"
    assert _has(_errs(r), Q1, "home table heading 'No such heading' not found")


def test_proposed_errors():
    r = _reg(); _q(r)["proposed"] = ""
    assert _has(_errs(r), Q1, "proposed must be null or a non-empty string")
    r = _reg(); _q(r)["proposed"] = 4
    assert _has(_errs(r), Q1, "proposed must be null or a non-empty string")


def test_member_errors():
    r = _reg(); _q(r)["members"] = ["no-hash-here"]
    assert _has(_errs(r), Q1, "member 'no-hash-here' is not <scenario_id>#<part>")
    r = _reg(); _q(r)["members"] = ["SC-NOPE-01#data"]
    assert _has(_errs(r), Q1, "member 'SC-NOPE-01#data': unknown scenario id")
    r = _reg(); _q(r)["members"] = [f"{SID}-AC1-01#bogus"]
    assert _has(_errs(r), Q1, "unknown part 'bogus'")
    r = _reg(); _q(r)["members"] = [f"{SID}-AC1-01#expected"]
    assert _has(_errs(r), Q1, "is not a doubt")
    r = _reg(); _q(r)["members"] = ["SC-UAT-FIX-J02#expected"]
    assert _has(_errs(r), Q1, "belongs to another story")
    r = _reg(); _q(r)["members"] = [f"{SID}-AC1-01#steps"] * 2
    assert _has(_errs(r), Q1, "listed twice")


def test_doubt_in_two_questions():
    r = _reg(); _q(r, 1)["members"].append(f"{SID}-AC1-01#steps")
    assert _has(_errs(r), Q1, Q2, "is in two questions")


def test_empty_question():
    r = _reg(); _q(r)["members"] = []
    assert _has(_errs(r), Q1, "has no members")
    ans = {"answers": Q1, "card": "c.json", "effect": "corrects",
           "status": "asserted"}
    assert not _has(_errs(r, [ans]), "has no members")
    # only an asserted answer Resolution exempts an empty question
    assert _has(_errs(r, [{**ans, "status": "proposed"}]), "has no members")
    assert _has(_errs(r, [{"answers": Q1, "status": "asserted"}]), "has no members")


def test_load_register():
    with tempfile.TemporaryDirectory() as d:
        assert wiki_doubts.load_register("US-X", root=Path(d)) is None
        (Path(d) / "doubts").mkdir()
        p = Path(d) / "doubts" / "US-X.yaml"
        p.write_text("story: [unclosed", encoding="utf-8")
        try:
            wiki_doubts.load_register("US-X", root=Path(d))
        except ValueError as e:
            assert "US-X.yaml" in str(e)
        else:
            raise AssertionError("no ValueError")
        p.write_text("story: /stories/US-X.md\nquestions: []\n", encoding="utf-8")
        assert wiki_doubts.load_register("US-X", root=Path(d))["questions"] == []


D_STEPS = f"{SID}-AC1-01#steps"
D_DATA = f"{SID}-AC1-01#data"


def _row(doubt):
    return next(r for r in _doubts() if r["doubt"] == doubt)


def _res(rid, effect, doubt, basis, status="asserted"):
    key = "confirmed_parts" if effect == "confirms" else "member_basis"
    return {"id": rid, "status": status, "answers": Q1, "card": "c.json",
            "effect": effect, key: {doubt: basis}}


def _state(resolutions, manifest=None, doubt=D_STEPS):
    return wiki_doubts.doubt_states(_doubts(), _reg(), resolutions, manifest)[doubt]


def test_state_open():
    s = _state([])
    assert s == {"state": "open", "question": Q1, "resolution": None}, s
    assert _state([], doubt="SC-UAT-FIX-J02#expected")["question"] is None
    assert wiki_doubts.doubt_states(_doubts(), None, [])[D_STEPS]["question"] is None


def test_state_answered_rewritten():
    b = _row(D_STEPS)["basis"]
    assert _state([_res("R-1", "corrects", D_STEPS, b)]) == {
        "state": "answered", "question": Q1, "resolution": "R-1"}
    s = _state([_res("R-1", "corrects", D_STEPS, "old")])
    assert s["state"] == "rewritten" and s["resolution"] == "R-1"


def test_state_closed_and_reopen():
    b = _row(D_STEPS)["basis"]
    s = _state([_res("R-2", "confirms", D_STEPS, b)])
    assert s["state"] == "closed" and s["resolution"] == "R-2"
    s = _state([_res("R-2", "confirms", D_STEPS, "old")])
    assert s["state"] == "open" and s["resolution"] is None
    s = _state([_res("R-2", "confirms", D_STEPS, "old"),
                _res("R-1", "corrects", D_STEPS, "older")])
    assert s["state"] == "rewritten" and s["resolution"] == "R-1"


def test_state_closed_wins_and_unasserted_ignored():
    b = _row(D_STEPS)["basis"]
    s = _state([_res("R-1", "corrects", D_STEPS, b), _res("R-2", "confirms", D_STEPS, b)])
    assert s["state"] == "closed" and s["resolution"] == "R-2"
    s = _state([_res("R-3", "confirms", D_STEPS, b, status="proposed")])
    assert s["state"] == "open"


def test_state_retired_left_out():
    man = {"bindings": {f"{SID}-AC1-01": {"status": "retired"},
                        f"{SID}-AC2-02": {"status": "active"}}}
    st = wiki_doubts.doubt_states(_doubts(), _reg(), [], man)
    assert D_STEPS not in st and D_DATA not in st
    assert f"{SID}-AC2-02#scenario" in st and "SC-UAT-FIX-J01#steps" in st


def _sorted(resolutions=(), reg=None):
    d = _doubts()
    st = wiki_doubts.doubt_states(d, reg or _reg(), list(resolutions))
    return wiki_doubts.sorted_questions(reg or _reg(), d, st)


def _hand(scn, part, level):
    return {"doubt": f"{scn}#{part}", "scenario_id": scn, "part": part,
            "kind": "sit", "story": "stories/S", "level": level, "remark": "",
            "text": "", "basis": f"b-{scn}-{part}"}


def _order(specs):
    """specs: [(qid, [(scenario, part, level)])] -> ids in sorted order."""
    rows, qs = [], []
    for qid, mems in specs:
        ids = []
        for scn, part, level in mems:
            row = _hand(scn, part, level)
            rows.append(row); ids.append(row["doubt"])
        qs.append({"id": qid, "question": "q?", "about": ["HS-01"],
                   "home": "none", "proposed": None, "members": ids})
    reg = {"story": "/stories/S.md", "questions": qs}
    st = wiki_doubts.doubt_states(rows, reg, [])
    return [q["id"] for q in wiki_doubts.sorted_questions(reg, rows, st)]


def test_sorted_questions_shape():
    out = _sorted()
    assert [q["id"] for q in out] == [Q1, Q2]
    q = out[0]
    assert q["open_tcs"] == 2 and q["status"] == "open"
    assert set(q) == {"id", "question", "about", "home", "proposed", "status",
                      "open_tcs", "low", "lowest", "members"}
    assert all("state" in m and "resolution" in m for m in q["members"])
    assert [m["doubt"] for m in q["members"]] == _reg()["questions"][0]["members"]


def test_sorted_by_open_tcs():
    got = _order([("Q-A", [("S1", "data", "Low")]),
                  ("Q-B", [("S1", "data", "Medium"), ("S2", "data", "Medium")])])
    assert got == ["Q-B", "Q-A"], got


def test_sorted_low_count_breaks_open_tcs_tie():
    got = _order([("Q-A", [("S1", "data", "Medium"), ("S2", "data", "Medium")]),
                  ("Q-B", [("S3", "data", "Low"), ("S4", "data", "Low")]),
                  ("Q-C", [("S5", "data", "Low"), ("S6", "data", "Medium")])])
    assert got == ["Q-B", "Q-C", "Q-A"], got


def test_sorted_id_breaks_full_tie():
    got = _order([("Q-C", [("S1", "data", "Low")]),
                  ("Q-A", [("S2", "data", "Low")]),
                  ("Q-B", [("S3", "data", "Low")])])
    assert got == ["Q-A", "Q-B", "Q-C"], got


def test_sorted_closed_question_last():
    spec_rows = {r["doubt"]: r for r in _doubts()}
    r = _reg()
    r["questions"][0]["members"] = [D_STEPS]
    r["questions"][1]["members"] = [f"{SID}-AC2-02#scenario"]
    b = spec_rows[D_STEPS]["basis"]
    out = _sorted([_res("R-9", "confirms", D_STEPS, b)], reg=r)
    assert [q["id"] for q in out] == [Q2, Q1]
    assert out[-1]["open_tcs"] == 0 and out[-1]["status"] == "closed"
    assert out[-1]["lowest"] is None and out[-1]["low"] == 0


def test_sorted_questions_status_precedence():
    r = _reg()
    r["questions"][0]["members"] = [D_STEPS, D_DATA]
    bs, bd = _row(D_STEPS)["basis"], _row(D_DATA)["basis"]
    q = lambda res: next(x for x in _sorted(res, reg=r) if x["id"] == Q1)
    assert q([])["status"] == "open"
    assert q([_res("R-1", "corrects", D_STEPS, bs),
              _res("R-2", "confirms", D_DATA, bd)])["status"] == "rewrite-pending"
    assert q([_res("R-1", "corrects", D_STEPS, "old"),
              _res("R-2", "confirms", D_DATA, bd)])["status"] == "confirm-pending"
    assert q([_res("R-1", "corrects", D_STEPS, bs),
              _res("R-3", "corrects", D_DATA, "old")])["status"] == "rewrite-pending"
    assert q([_res("R-1", "corrects", D_STEPS, bs)])["status"] == "open"


def test_sorted_questions_skips_unknown_and_retired():
    r = _reg()
    r["questions"][0]["members"] = [D_STEPS, "SC-NOPE-01#data", D_DATA]
    d = _doubts()
    man = {"bindings": {f"{SID}-AC1-01": {"status": "retired"}}}
    st = wiki_doubts.doubt_states(d, r, [], man)
    q = wiki_doubts.sorted_questions(r, d, st)
    q1 = next(x for x in q if x["id"] == Q1)
    assert q1["members"] == [] and q1["status"] == "closed"


def test_malformed_register_never_raises():
    d = _doubts()
    r = {"story": "/stories/US-FIXTURE-DOUBTS.md", "questions": [
        {"id": ["x"], "question": "q?", "about": ["HS-01"], "home": "none",
         "members": []},
        {"id": "Q-US-FIXTURE-DOUBTS-01", "members": [["unhashable"], D_STEPS, 3]},
        {"id": "Q-US-FIXTURE-DOUBTS-02", "members": "not a list"},
        "not a mapping"]}
    fm, body = _story()
    assert wiki_doubts.register_errors(
        r, fm, d, [{"answers": ["a"]}, "junk", {"answers": Q2}], body)
    st = wiki_doubts.doubt_states(d, r, [{"status": "asserted", "confirmed_parts": []}])
    assert st[D_STEPS]["question"] == "Q-US-FIXTURE-DOUBTS-01"
    out = wiki_doubts.sorted_questions(r, d, st)
    assert [m["doubt"] for m in out[0]["members"]] == [D_STEPS]
    for bad in (None, [], {"questions": "x"}, {"questions": [None, 1]}):
        st = wiki_doubts.doubt_states(d, bad, [], manifest={"bindings": []})
        assert len(st) == len(d)
        wiki_doubts.sorted_questions(bad, d, st)


# ------------------------------------------------------- summary, list, lint

import contextlib
import io
import json
import shutil
import subprocess

STORY = "US-FIXTURE-DOUBTS"
TC_BASE = "testcases/fixture/"


def _mkroot(register="valid", resolutions=(), retire=None):
    """A fixture root in a temp dir. register: "valid" | None | yaml text."""
    d = Path(tempfile.mkdtemp(prefix="doubts-root-"))
    (d / "tools" / "sit_specs").mkdir(parents=True)
    (d / "tools" / "uat_specs").mkdir(parents=True)
    (d / "stories").mkdir()
    (d / "flows").mkdir()
    (d / "resolutions").mkdir()
    shutil.copy(FIX / "sit_spec.yaml", d / "tools" / "sit_specs" / f"{STORY}.yaml")
    shutil.copy(FIX / "uat_spec.yaml", d / "tools" / "uat_specs" / "FLOW-FIXTURE-DOUBTS.yaml")
    shutil.copy(FIX / "story.md", d / "stories" / f"{STORY}.md")
    shutil.copy(FIX / "flow.md", d / "flows" / "FLOW-FIXTURE-DOUBTS.md")
    if register == "valid":
        (d / "doubts").mkdir()
        shutil.copy(FIX / "register.yaml", d / "doubts" / f"{STORY}.yaml")
    elif register is not None:
        (d / "doubts").mkdir()
        (d / "doubts" / f"{STORY}.yaml").write_text(register, encoding="utf-8")
    bind = {f"{SID}-AC1-01": {"tc": TC_BASE + "TC-FIX-0001", "status": "active"},
            f"{SID}-AC2-02": {"tc": TC_BASE + "TC-FIX-0002", "status": "active"}}
    if retire:
        bind[retire]["status"] = "retired"
    (d / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "prds": {}, "bindings": bind}),
        encoding="utf-8")
    for rid, fm in resolutions:
        wiki.write_concept(d / "resolutions" / f"{rid}.md",
                           {"type": "Resolution", "id": rid, **fm}, "body\n")
    return d


def _cleanup(d):
    shutil.rmtree(d, ignore_errors=True)


def _tree(d):
    return {str(p.relative_to(d)): p.read_bytes()
            for p in sorted(Path(d).rglob("*")) if p.is_file()}


def _run(args, root):
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            wiki_doubts.cmd_doubts(args, root=root)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def _confirm(rid, doubt):
    return (rid, {"status": "asserted", "answers": Q2, "card": "c.json",
                  "effect": "confirms",
                  "confirmed_parts": {doubt: _row(doubt)["basis"]}})


def test_story_summary_counts_and_tc():
    d = _mkroot(retire=f"{SID}-AC2-02")
    try:
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["story"] == STORY and s["register"] is True
        assert s["register_errors"] == []
        # 6 story rows (J02 has no story), AC2-02 retired (2 rows) -> 4 live
        assert s["open"] == 4, s["open"]
        assert s["questions_open"] == 1  # Q2 lost every member to the retired binding
        assert s["ungrouped"] == 1
        ug = {r["doubt"] for r in s["ungrouped_doubts"]}
        assert ug == {"SC-UAT-FIX-J01#steps"}, ug
        assert all("tc" in r and "state" in r for r in s["doubts"])
        row = next(r for r in s["doubts"] if r["doubt"] == D_STEPS)
        assert row["tc"] == "TC-FIX-0001" and row["question"] == Q1
        assert not any(r["scenario_id"] == f"{SID}-AC2-02" for r in s["doubts"])
        uat = next(r for r in s["doubts"] if r["doubt"] == "SC-UAT-FIX-J01#steps")
        assert uat["tc"] is None
        assert s["questions"][0]["id"] == Q1
    finally:
        _cleanup(d)


def test_story_summary_closed_not_open():
    d = _mkroot(resolutions=[_confirm("R-FIX-1", D_STEPS)])
    try:
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["open"] == 5, s["open"]
        assert next(r for r in s["doubts"] if r["doubt"] == D_STEPS)["state"] == "closed"
    finally:
        _cleanup(d)


def test_story_summary_never_raises():
    d = _mkroot(register="story: [unclosed")
    try:
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["register"] is True and s["register_errors"]
        assert "invalid YAML" in s["register_errors"][0]
        assert s["questions"] == [] and s["ungrouped"] == s["open"]
    finally:
        _cleanup(d)
    d = _mkroot(register=None)
    try:
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["register"] is False and s["register_errors"] == []
        assert s["questions_open"] == 0 and s["ungrouped"] == s["open"] == 6
    finally:
        _cleanup(d)


def test_stories_with_doubts():
    d = _mkroot()
    try:
        assert wiki_doubts.stories_with_doubts(root=d) == [STORY]
        (d / "doubts" / "US-ONLY-REG.yaml").write_text("questions: []\n", encoding="utf-8")
        assert wiki_doubts.stories_with_doubts(root=d) == [STORY, "US-ONLY-REG"]
    finally:
        _cleanup(d)


def test_summary_line_format():
    line = wiki_doubts.summary_line({"story": "US-DEMO-001", "open": 12,
                                     "questions_open": 3, "ungrouped": 4})
    assert line == "US-DEMO-001: 12 open doubts in 3 questions (4 ungrouped)", line


def test_cmd_list_text():
    d = _mkroot()
    try:
        code, out = _run(["list"], d)
        assert code == 0
        lines = out.splitlines()
        assert lines[0] == "US-FIXTURE-DOUBTS: 6 open doubts in 2 questions (1 ungrouped)", lines[0]
        assert Q1 in out and Q2 in out and "Ungrouped" in out
        assert "SC-UAT-FIX-J01#steps" in out and "TC-FIX-0001" in out
        out.encode("ascii")
        code, out = _run(["list", "--story", STORY, "--ungrouped"], d)
        assert code == 0 and Q1 not in out and "Ungrouped" in out
        assert out.splitlines()[0].startswith(STORY + ":")
    finally:
        _cleanup(d)


def test_cmd_list_json_shape():
    d = _mkroot()
    try:
        code, out = _run(["list", "--json"], d)
        assert code == 0
        doc = json.loads(out)
        assert list(doc) == ["stories"] and len(doc["stories"]) == 1
        s = doc["stories"][0]
        assert {"story", "open", "questions_open", "ungrouped", "register",
                "register_errors", "questions", "ungrouped_doubts", "doubts"} <= set(s)
        u = s["ungrouped_doubts"][0]
        assert {"text", "remark", "level", "part", "kind", "tc"} <= set(u)
        assert out == json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        code, out = _run(["list", "--json", "--ungrouped"], d)
        s = json.loads(out)["stories"][0]
        assert s["questions"] == [] and "doubts" not in s and s["ungrouped_doubts"]
    finally:
        _cleanup(d)


def test_cmd_list_all_includes_closed():
    reg = _reg()
    reg["questions"][1]["members"] = [f"{SID}-AC2-02#scenario"]
    d = _mkroot(register=yaml.safe_dump(reg),
                resolutions=[_confirm("R-FIX-2", f"{SID}-AC2-02#scenario")])
    try:
        _, out = _run(["list"], d)
        assert Q1 in out and Q2 not in out
        _, out = _run(["list", "--all"], d)
        assert Q1 in out and Q2 in out
        hidden = json.loads(_run(["list", "--json"], d)[1])["stories"][0]
        shown = json.loads(_run(["list", "--json", "--all"], d)[1])["stories"][0]
        assert Q2 not in [q["id"] for q in hidden["questions"]]
        assert Q2 in [q["id"] for q in shown["questions"]]
        assert len(shown["doubts"]) == len(hidden["doubts"]) + 1
    finally:
        _cleanup(d)


def test_cmd_list_invalid_register_message():
    d = _mkroot(register="story: [unclosed")
    try:
        code, out = _run(["list"], d)
        assert code == 0
        assert "register invalid - run: py tools/wiki.py lint" in out
    finally:
        _cleanup(d)


def test_cmd_list_exit_codes():
    d = _mkroot()
    try:
        assert _run([], d)[0] == 2
        assert _run(["bogus"], d)[0] == 2
        code, out = _run(["list", "--story", "US-NOPE"], d)
        assert code == 1, code
        assert STORY in out
    finally:
        _cleanup(d)


def test_cmd_list_is_read_only():
    d = _mkroot()
    try:
        before = _tree(d)
        for a in (["list"], ["list", "--all", "--json"], ["list", "--ungrouped"]):
            _run(a, d)
        assert _tree(d) == before
    finally:
        _cleanup(d)


def test_real_cli_json():
    """`doubts list --json` on this bundle's own content: every story it
    lists reports the open count the states say. Skips on a content-free
    bundle (no SIT spec)."""
    if not sorted((ROOT / "tools" / "sit_specs").glob("*.yaml")):
        raise Skip("no specs in this bundle")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "wiki.py"),
                        "doubts", "list", "--json"],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc["stories"], doc
    res = [wiki.read_concept(p)[0] or {}
           for p in sorted((ROOT / "resolutions").glob("R-*.md"))]
    for s in doc["stories"]:
        sid = s["story"]
        rows = [x for x in wiki_doubts.collect_all() if x["story"] == f"stories/{sid}"]
        st = wiki_doubts.doubt_states(rows, wiki_doubts.load_register(sid), res,
                                      wiki.load_manifest())
        expect = sum(1 for v in st.values() if v["state"] != "closed")
        assert s["open"] == expect, (sid, s["open"], expect)


def test_l15_bad_register():
    reg = _reg()
    reg["questions"][0]["about"] = ["HS-99"]
    d = _mkroot(register=yaml.safe_dump(reg))
    try:
        errs = wiki_doubts.l15_errors(root=d)
        assert errs and all(e.startswith(f"L15 doubts/{STORY}.yaml: ") for e in errs), errs
        assert any("HS-99" in e for e in errs)
        assert wiki_doubts.w8_warnings(root=d) == []
    finally:
        _cleanup(d)


def test_l15_invalid_yaml_and_missing_story():
    d = _mkroot(register="story: [unclosed")
    try:
        errs = wiki_doubts.l15_errors(root=d)
        assert len(errs) == 1 and errs[0].startswith(f"L15 doubts/{STORY}.yaml:"), errs
        assert wiki_doubts.w8_warnings(root=d) == []
    finally:
        _cleanup(d)
    d = _mkroot()
    try:
        g = d / "doubts" / "US-GHOST.yaml"
        g.write_text("story: /stories/US-GHOST.md\nquestions: []\n", encoding="utf-8")
        errs = wiki_doubts.l15_errors(root=d)
        assert any("US-GHOST.yaml" in e and "story" in e for e in errs), errs
        g.write_text("- a\n- b\n", encoding="utf-8")
        assert wiki_doubts.l15_errors(root=d)
    finally:
        _cleanup(d)


def test_lint_valid_register_clean_and_w8():
    d = _mkroot()
    try:
        assert wiki_doubts.l15_errors(root=d) == []
        w = wiki_doubts.w8_warnings(root=d)
        assert w == [f"W8 {STORY}: 1 ungrouped doubt(s) - group them in "
                     f"doubts/{STORY}.yaml (tc-resolve)"], w
    finally:
        _cleanup(d)
    d = _mkroot(register=None)
    try:
        assert wiki_doubts.l15_errors(root=d) == []
        w = wiki_doubts.w8_warnings(root=d)
        assert len(w) == 1 and w[0].startswith(f"W8 {STORY}: 6 ungrouped"), w
    finally:
        _cleanup(d)


def _add_other_story(d):
    """A second story US-OTHER with its own SIT spec (scenario ids SC-OTH-...)."""
    spec = yaml.safe_load((FIX / "sit_spec.yaml").read_text(encoding="utf-8"))
    spec["story"] = "/stories/US-OTHER.md"
    spec["ac_prefix"] = "US-OTHER"
    spec["scenario_id"] = "SC-OTH-{ac_id}-{seq:02d}"
    (d / "tools" / "sit_specs" / "US-OTHER.yaml").write_text(
        yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    text = (FIX / "story.md").read_text(encoding="utf-8")
    (d / "stories" / "US-OTHER.md").write_text(
        text.replace("id: US-FIXTURE-DOUBTS", "id: US-OTHER", 1), encoding="utf-8")


def test_cross_story_member_same_verdict_in_lint_and_summary():
    other = "SC-OTH-US-OTHER-AC1-01#steps"
    reg = _reg()
    reg["questions"][0]["members"].append(other)
    d = _mkroot(register=yaml.safe_dump(reg))
    try:
        _add_other_story(d)
        errs = wiki_doubts.l15_errors(root=d)
        mine = [e for e in errs if other in e]
        assert mine and all("belongs to another story" in e for e in mine), errs
        assert not any("unknown scenario" in e for e in errs), errs
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["register_errors"]
        lint_msgs = [e[len(f"L15 doubts/{STORY}.yaml: "):] for e in errs]
        assert lint_msgs == s["register_errors"], (lint_msgs, s["register_errors"])
        assert wiki_doubts.w8_warnings(root=d) == [
            w for w in wiki_doubts.w8_warnings(root=d) if "US-OTHER" in w]
    finally:
        _cleanup(d)


def test_l15_register_story_differs_from_file_name():
    reg = _reg()
    reg["story"] = "/stories/US-SOMETHING-ELSE.md"
    d = _mkroot(register=yaml.safe_dump(reg))
    try:
        errs = wiki_doubts.l15_errors(root=d)
        assert any(e.startswith(f"L15 doubts/{STORY}.yaml: ") and "register: story" in e
                   for e in errs), errs
        s = wiki_doubts.story_summary(STORY, root=d)
        assert s["register_errors"]
    finally:
        _cleanup(d)


# ------------------------------------------------------------------- card

def _corrects(rid, doubt, basis, qid=Q1):
    return (rid, {"status": "asserted", "answers": qid, "card": "c.json",
                  "effect": "corrects", "member_basis": {doubt: basis}})


def _summary(d):
    return wiki_doubts.story_summary(STORY, root=d)


def _card(d, **kw):
    s = _summary(d)
    return wiki_doubts.build_card(s, wiki_doubts.register_hash(STORY, root=d), **kw)


def _crun(args, root):
    return _run(["card"] + args, root)


def test_card_deterministic():
    d = _mkroot()
    try:
        assert _card(d) == _card(d)
        c = _card(d)
        assert c["card_type"] == "doubts" and c["story"] == STORY
        assert c["register_hash"].startswith("sha256:")
        p1 = wiki_doubts.write_doubts_card(c, root=d)
        p2 = wiki_doubts.write_doubts_card(c, root=d)
        assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")
        assert p1.read_text(encoding="utf-8").endswith("}\n")
        assert b"\r" not in p1.read_bytes()
    finally:
        _cleanup(d)


def test_card_register_hash_absent_and_changes():
    d = _mkroot(register=None)
    try:
        assert wiki_doubts.register_hash(STORY, root=d) == ""
    finally:
        _cleanup(d)
    d = _mkroot()
    try:
        h = wiki_doubts.register_hash(STORY, root=d)
        assert h == wiki_doubts.register_hash(STORY, root=d)
        p = d / "doubts" / f"{STORY}.yaml"
        p.write_text(p.read_text(encoding="utf-8") + "# note\n", encoding="utf-8")
        assert wiki_doubts.register_hash(STORY, root=d) != h
    finally:
        _cleanup(d)


def test_card_order_top_and_filter():
    d = _mkroot()
    try:
        c = _card(d)
        ids = [q["id"] for q in c["open_questions"]]
        assert ids == [q["id"] for q in _summary(d)["questions"]] and len(ids) == 2
        assert [q["id"] for q in _card(d, top=1)["open_questions"]] == ids[:1]
        assert [q["id"] for q in _card(d, question_ids=[ids[1]])["open_questions"]] == [ids[1]]
        both = _card(d, question_ids=[ids[1], ids[0]], top=1)
        assert [q["id"] for q in both["open_questions"]] == ids[:1]
    finally:
        _cleanup(d)


def test_card_refuses_unknown_and_ineligible_ids():
    sc, ex = f"{SID}-AC2-02#scenario", f"{SID}-AC2-02#expected"
    d = _mkroot(resolutions=[_confirm("R-FIX-1", D_STEPS),
                             _confirm("R-FIX-2", D_DATA),
                             _confirm("R-FIX-3", "SC-UAT-FIX-J01#data"),
                             _corrects("R-FIX-4", sc, _row(sc)["basis"], Q2),
                             _corrects("R-FIX-5", ex, _row(ex)["basis"], Q2)])
    try:
        msgs = {}
        for qid in ("Q-NOPE", Q1):
            try:
                _card(d, question_ids=[qid])
                raise AssertionError(f"{qid} accepted")
            except ValueError as e:
                msgs[qid] = str(e)
        assert "unknown" in msgs["Q-NOPE"]
        assert "closed" in msgs[Q1]
        # answered and not rewritten is not a dead end: it is a confirm
        q2 = _card(d, question_ids=[Q2])["open_questions"]
        assert [q["kind"] for q in q2] == ["confirm"], q2
    finally:
        _cleanup(d)


def test_card_top_must_be_positive():
    d = _mkroot()
    try:
        for bad in (0, -1):
            try:
                _card(d, top=bad)
                raise AssertionError("accepted")
            except ValueError:
                pass
    finally:
        _cleanup(d)


def test_card_ask_lists_only_open_members_and_keys():
    d = _mkroot(resolutions=[_confirm("R-FIX-1", D_STEPS)])
    try:
        q = next(x for x in _card(d)["open_questions"] if x["id"] == Q1)
        assert q["kind"] == "ask"
        assert [m["doubt"] for m in q["members"]] == [D_DATA, "SC-UAT-FIX-J01#data"]
        for m in q["members"]:
            assert list(m) == ["doubt", "tc", "part", "level", "remark", "text", "basis"]
        assert q["proposed"] is None and q["about"] == ["HS-01"]
        assert q["home"] == "table:Scenario data"
        q2 = next(x for x in _card(d)["open_questions"] if x["id"] == Q2)
        assert q2["proposed"] == "The page shows done."
    finally:
        _cleanup(d)


def test_card_confirm_only_for_rewritten():
    sc, ex = f"{SID}-AC2-02#scenario", f"{SID}-AC2-02#expected"
    d = _mkroot(resolutions=[
        _corrects("R-FIX-9", sc, "sha256:old", Q2),
        _corrects("R-FIX-8", ex, "sha256:older", Q2)])
    try:
        c = _card(d)
        q2 = next(x for x in c["open_questions"] if x["id"] == Q2)
        assert q2["kind"] == "confirm"
        assert [m["doubt"] for m in q2["members"]] == [sc, ex]
        assert q2["members"][0]["basis"] == _row(sc)["basis"]
        assert q2["members"][0]["text"] == _row(sc)["text"]
        assert q2["proposed"] == ("Rewritten after R-FIX-8; confirm the text "
                                  "shown for each member.")
        q1 = next(x for x in c["open_questions"] if x["id"] == Q1)
        assert q1["kind"] == "ask"
    finally:
        _cleanup(d)


def test_card_confirm_shows_rewritten_and_answered_members():
    sc, ex = f"{SID}-AC2-02#scenario", f"{SID}-AC2-02#expected"
    d = _mkroot(resolutions=[_corrects("R-FIX-9", sc, "sha256:old", Q2),
                             _corrects("R-FIX-8", ex, _row(ex)["basis"], Q2)])
    try:
        q2 = next(x for x in _card(d)["open_questions"] if x["id"] == Q2)
        assert q2["kind"] == "confirm"
        assert [m["doubt"] for m in q2["members"]] == [sc, ex], q2
        assert q2["proposed"] == ("Rewritten after R-FIX-9; confirm the text "
                                  "shown for each member.")
    finally:
        _cleanup(d)


def test_card_answered_only_question_is_a_confirm_of_the_current_text():
    sc, ex = f"{SID}-AC2-02#scenario", f"{SID}-AC2-02#expected"
    d = _mkroot(resolutions=[_corrects("R-FIX-8", sc, _row(sc)["basis"], Q2),
                             _corrects("R-FIX-7", ex, _row(ex)["basis"], Q2)])
    try:
        c = _card(d)
        assert [q["id"] for q in c["open_questions"]] == [Q1, Q2], c
        q2 = c["open_questions"][1]
        assert q2["kind"] == "confirm"
        assert [m["doubt"] for m in q2["members"]] == [sc, ex]
        assert [m["text"] for m in q2["members"]] == [_row(sc)["text"],
                                                       _row(ex)["text"]]
        assert [m["basis"] for m in q2["members"]] == [_row(sc)["basis"],
                                                        _row(ex)["basis"]]
        assert q2["proposed"] == ("Answered by R-FIX-7; confirm the text shown "
                                  "for each member is correct as it stands.")
    finally:
        _cleanup(d)


def test_card_file_numbering():
    d = _mkroot()
    try:
        c = _card(d)
        p1 = wiki_doubts.write_doubts_card(c, root=d)
        p2 = wiki_doubts.write_doubts_card(c, root=d)
        assert p1.parent == d / "build" / "cards"
        assert p1.name == f"doubts-{STORY}-001.json"
        assert p2.name == f"doubts-{STORY}-002.json"
    finally:
        _cleanup(d)


def test_card_cli_success_and_refusals():
    d = _mkroot()
    try:
        code, out = _crun(["--story", STORY], d)
        assert code == 0, out
        card = d / "build" / "cards" / f"doubts-{STORY}-001.json"
        assert card.exists()
        assert "build/cards/doubts-" in out and "2 question" in out
        assert "card revise" in out and "doubts answer --card" in out
        code, out = _crun(["--story", STORY, "--top", "1"], d)
        assert code == 0
        second = d / "build" / "cards" / f"doubts-{STORY}-002.json"
        assert len(json.loads(second.read_text(encoding="utf-8"))["open_questions"]) == 1
        before = _tree(d)
        for args in (["--story", STORY, "--top", "0"], ["--story", STORY, "--top", "x"],
                     ["--story", STORY, "--question", "Q-NOPE"], []):
            code, out = _crun(args, d)
            assert code not in (0, None), args
        assert _tree(d) == before
    finally:
        _cleanup(d)


def test_card_cli_refuses_no_register_invalid_nothing_eligible():
    d = _mkroot(register=None)
    try:
        code, out = _crun(["--story", STORY], d)
        assert code == 1 and "no register" in out, out
        assert not (d / "build").exists()
    finally:
        _cleanup(d)
    d = _mkroot(register="story: /stories/X.md\nquestions: nope\n")
    try:
        code, out = _crun(["--story", STORY], d)
        assert code == 1 and "lint" in out, out
        assert not (d / "build").exists()
    finally:
        _cleanup(d)
    d = _mkroot(resolutions=[_confirm("R-FIX-1", D_STEPS), _confirm("R-FIX-2", D_DATA),
                             _confirm("R-FIX-3", "SC-UAT-FIX-J01#data"),
                             _confirm("R-FIX-4", f"{SID}-AC2-02#scenario"),
                             _confirm("R-FIX-5", f"{SID}-AC2-02#expected")])
    try:
        code, out = _crun(["--story", STORY], d)
        assert code == 1 and "no question" in out, out
        assert not (d / "build").exists()
    finally:
        _cleanup(d)


def test_card_round_trip_with_real_card_revise():
    d = _mkroot()
    try:
        card = wiki_doubts.write_doubts_card(_card(d), root=d)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            wiki.cmd_card(["revise", str(card), "--by", "tester", "--answer",
                           f"{Q2}=accept", "--answer", f"{Q1}=Profile A, mailbox X"])
        got = json.loads(card.read_text(encoding="utf-8"))
        ans = got["human_response"]["answers"]
        assert ans[Q2] == {"decision": "accept", "value": None}
        assert ans[Q1] == {"decision": "correct", "value": "Profile A, mailbox X"}
    finally:
        _cleanup(d)


# ----------------------------------------------------------------- answer
# Every run goes through a throwaway scratch project (tools/doubts_scratch.py)
# as a subprocess of its COPY of the tools; the real repository is never touched.

sys.path.insert(0, str(ROOT / "tools"))
import doubts_scratch  # noqa: E402

PY = sys.executable
BY = "tester"


def _real_status():
    r = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout


def _sw(d, *args):
    r = subprocess.run([PY, str(d / "tools" / "wiki.py"), *args], cwd=d,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, r.stdout, r.stderr


def _git_out(d, *args):
    return subprocess.run(["git", *args], cwd=d, capture_output=True,
                          text=True, encoding="utf-8").stdout


def _commits(d):
    return int(_git_out(d, "rev-list", "--count", "HEAD").strip())


def _res_files(d):
    return sorted(p.name for p in (d / "resolutions").glob("*.md"))


def _emit(d, answers=None, by=BY, questions=None):
    """Emit a doubts card in the scratch project; answer it with the real
    `card revise` when answers ({Q: "accept" | text}) are given. Returns the
    card path."""
    args = ["doubts", "card", "--story", STORY]
    if questions:
        args += ["--question", ",".join(questions)]
    code, out, err = _sw(d, *args)
    assert code == 0, out + err
    rel = out.splitlines()[0].split(":")[0]
    path = d / rel
    if answers:
        a = ["card", "revise", rel, "--by", by]
        for q, v in answers.items():
            a += ["--answer", f"{q}={v}"]
        code, out, err = _sw(d, *a)
        assert code == 0, out + err
    return path


def _edit_card(path, fn):
    c = json.loads(path.read_text(encoding="utf-8"))
    fn(c)
    path.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def _answer(d, card, by=BY, *extra):
    return _sw(d, "doubts", "answer", "--card", str(card.relative_to(d)),
               "--by", by, *extra)


def _expect_refusal(d, card, why, by=BY, extra=()):
    """Run `doubts answer`; assert exit 1, the prefix and `why`, and that no
    file, commit or card byte changed."""
    before = (_res_files(d), _commits(d),
              card.read_bytes() if card.exists() else None)
    code, out, err = _answer(d, card, by, *extra)
    assert code == 1, (code, out, err)
    assert err.startswith("doubts answer refused:"), err
    assert why in err, (why, err)
    after = (_res_files(d), _commits(d),
             card.read_bytes() if card.exists() else None)
    assert before == after, "a refused answer changed state"
    return err


def _with_scratch(fn):
    d = doubts_scratch.scratch_project()
    try:
        return fn(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_scratch_project_lints_clean():
    def go(d):
        code, out, err = _sw(d, "lint")
        assert code == 0 and "0 error(s)" in out, out + err
        assert _git_out(d, "log", "-1", "--format=%an").strip() == "tc-agent"
        assert _git_out(d, "status", "--short").strip() == ""
    _with_scratch(go)


def test_answer_refuses_missing_args_file_json_type():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        code, out, err = _sw(d, "doubts", "answer", "--by", BY)
        assert code == 1 and "--card" in err and err.startswith(
            "doubts answer refused:"), err
        code, out, err = _sw(d, "doubts", "answer", "--card",
                             str(card.relative_to(d)))
        assert code == 1 and "--by" in err, err
        _expect_refusal(d, d / "build" / "cards" / "nope.json", "card not found")
        bad = d / "build" / "cards" / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        _expect_refusal(d, bad, "not valid JSON")
        _edit_card(card, lambda c: c.update(card_type="alignment"))
        _expect_refusal(d, card, "not a doubts card")
    _with_scratch(go)


def test_answer_refuses_story_without_register_or_mismatch():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        _expect_refusal(d, card, "not OTHER-STORY",
                        extra=("--story", "OTHER-STORY"))
        _edit_card(card, lambda c: c.update(story="US-NOPE"))
        _expect_refusal(d, card, "no register")
    _with_scratch(go)


def test_answer_refuses_no_answers():
    def go(d):
        card = _emit(d)
        _expect_refusal(d, card, "no human_response.answers")
        _edit_card(card, lambda c: c.update(
            human_response={"answer": "revise", "by": BY, "at": "x"}))
        _expect_refusal(d, card, "no human_response.answers")
        _edit_card(card, lambda c: c["human_response"].update(answers={}))
        _expect_refusal(d, card, "no human_response.answers")
    _with_scratch(go)


def test_answer_refuses_by_mismatch():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        _expect_refusal(d, card, "differs from the card's human_response.by",
                        by="someone-else")
    _with_scratch(go)


def test_answer_refuses_already_applied():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        _edit_card(card, lambda c: c.update(applied={"by": BY}))
        _expect_refusal(d, card, "already applied")
    _with_scratch(go)


def test_answer_refuses_changed_register_or_spec():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        reg = d / "doubts" / f"{STORY}.yaml"
        txt = reg.read_text(encoding="utf-8")
        reg.write_text(txt.replace("The page shows done.",
                                   "The page shows finished."),
                       encoding="utf-8", newline="\n")
        err = _expect_refusal(d, card, "emit a new card")
        assert (f"card discard build/cards/{card.name} --by {BY}" in err), err
        reg.write_text(txt, encoding="utf-8", newline="\n")
        spec = d / "tools" / "sit_specs" / f"{STORY}.yaml"
        stxt = spec.read_text(encoding="utf-8")
        spec.write_text(stxt.replace("Wording guessed.", "Wording guessed.")
                        .replace("Fixture objective three.",
                                 "Fixture objective three, reworded."),
                        encoding="utf-8", newline="\n")
        _expect_refusal(d, card, "emit a new card")
    _with_scratch(go)


def test_answer_unanswered_question_change_is_not_compared_but_hash_is():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        # Q1's member text changes: the register is untouched, only an
        # UNANSWERED question's entry differs, so the answer proceeds.
        spec = d / "tools" / "sit_specs" / f"{STORY}.yaml"
        stxt = spec.read_text(encoding="utf-8")
        spec.write_text(stxt.replace("Profile A", "Profile B"),
                        encoding="utf-8", newline="\n")
        _commit_all(d, "scratch: reword an unanswered member")
        code, out, err = _answer(d, card)
        assert code == 0, out + err
    _with_scratch(go)


def test_answer_refuses_accept_without_proposed():
    def go(d):
        card = _emit(d, {Q1: "accept"})
        _expect_refusal(d, card, "no proposed answer")
    _with_scratch(go)


def test_answer_refuses_accept_on_stale_or_unbound_test_case():
    def go(d):
        tc = d / "testcases" / "fixture" / "TC-FIX-0002.md"
        orig = tc.read_text(encoding="utf-8")
        card = _emit(d, {Q2: "accept"})
        tc.write_text(orig.replace("stale_because: []",
                                   "stale_because:\n- /stories/X.md#HS-01"),
                      encoding="utf-8", newline="\n")
        _expect_refusal(d, card, "stale test case")
        tc.write_text(orig.replace("status: active", "status: stale"),
                      encoding="utf-8", newline="\n")
        _expect_refusal(d, card, "stale test case")
        tc.unlink()
        _expect_refusal(d, card, "no test case file")
        man = d / "manifest.json"
        m = json.loads(man.read_text(encoding="utf-8"))
        m["bindings"].pop(f"{SID}-AC2-02")
        man.write_text(json.dumps(m), encoding="utf-8")
        _expect_refusal(d, card, "no bound test case")
    _with_scratch(go)


def test_answer_refuses_empty_correction():
    def go(d):
        card = _emit(d, {Q1: "   "})
        _expect_refusal(d, card, "non-empty text")
        card = _emit(d, {Q1: ""})
        _expect_refusal(d, card, "non-empty text")
    _with_scratch(go)


def test_answer_refuses_unknown_question_id():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        _edit_card(card, lambda c: c["human_response"]["answers"].update(
            {"Q-US-FIXTURE-DOUBTS-99": {"decision": "accept", "value": None}}))
        _expect_refusal(d, card, "not on")
    _with_scratch(go)


def _fm_body(path):
    fm, body = wiki.read_concept(path)
    return fm, body


def test_answer_accept_confirms_and_closes():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        before = _commits(d)
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        new = [n for n in _res_files(d) if n != f"R-{STORY}-01.md"]
        assert new == [f"R-{STORY}-02.md"], new
        fm, body = _fm_body(d / "resolutions" / new[0])
        keys = list(fm)
        assert keys[:12] == ["type", "id", "title", "description", "origin",
                             "status", "asserted_by", "asserted_at", "resolves",
                             "answers", "effect", "card"], keys
        assert fm["effect"] == "confirms" and fm["origin"] == "agent-proposed"
        assert fm["status"] == "asserted" and fm["asserted_by"] == BY
        assert fm["answers"] == Q2 and fm["card"] == card.name
        assert fm["resolves"] == [f"/stories/{STORY}.md#HS-02",
                                  f"/stories/{STORY}.md#BR-01"]
        assert fm["description"] == (f"Human answer to doubt question {Q2} on "
                                     f"card {card.name}.")
        assert fm["title"] == f"{STORY} {Q2}: What does the fixture page show at the end?"
        s = wiki_doubts.story_summary(STORY, root=d)
        bases = {x["doubt"]: x["basis"] for x in s["doubts"]
                 if x["doubt"].endswith(("AC2-02#scenario", "AC2-02#expected"))}
        assert fm["confirmed_parts"] == bases and len(bases) == 2
        assert "member_basis" not in fm
        for h in ("# Human Statement", "# Question", "# Adopted answer",
                  "# Applies to", "# Propagation"):
            assert h in body, h
        assert f'> Card {card.name} answer: "accept" -- adopts the proposed ' \
               f"answer below verbatim." in body
        assert "The page shows done." in body.split("# Adopted answer")[1]
        assert "None. Confirms the current text" in body
        assert f"- {SID}-AC2-02#expected - TC-FIX-0002" in body
        stamp = json.loads(card.read_text(encoding="utf-8"))["applied"]
        assert stamp["by"] == BY and stamp["resolutions"] == {Q2: fm["id"]}
        assert _commits(d) == before + 1
        msg = _git_out(d, "log", "-1", "--format=%B")
        assert f"doubts answer: {STORY} {Q2} by {BY}" in msg
        assert f"Assertion-Event: cli-doubts-answer {STORY} {Q2} by {BY} at " in msg
        assert f"card {card.name}" in msg
        assert "Co-Authored-By" not in msg
        assert _git_out(d, "log", "-1", "--format=%an <%ae>").strip() == \
            "tc-agent <tc-agent@internal>"
        assert "render_sit.py --story US-FIXTURE-DOUBTS" in out
        assert "tools/wiki.py seal" in out and "closed" in out
        assert "tc-agent" not in _git_out(d, "status", "--short")
        code, out2, err2 = _sw(d, "doubts", "list", "--json", "--all",
                               "--story", STORY)
        assert code == 0, err2
        got = {x["doubt"]: x["state"]
               for x in json.loads(out2)["stories"][0]["doubts"]}
        assert got[f"{SID}-AC2-02#scenario"] == "closed"
        assert got[f"{SID}-AC2-02#expected"] == "closed"
        assert got[f"{SID}-AC1-01#data"] == "open"
        code, out3, err3 = _sw(d, "lint")
        assert code == 0 and "0 error(s)" in out3, out3 + err3
    _with_scratch(go)


def test_answer_text_corrects_and_answers():
    text = "Profile A, mailbox  X\n  second line, verbatim"

    def go(d):
        card = _emit(d, {Q1: text})
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        path = d / "resolutions" / f"R-{STORY}-02.md"
        fm, body = _fm_body(path)
        assert fm["effect"] == "corrects" and fm["origin"] == "human-stated"
        assert "confirmed_parts" not in fm
        s = wiki_doubts.story_summary(STORY, root=d)
        bases = {x["doubt"]: x["basis"] for x in s["doubts"]
                 if x["doubt"] in fm["member_basis"]}
        assert fm["member_basis"] == bases and len(bases) == 3
        assert fm["resolves"] == [f"/stories/{STORY}.md#HS-01"]
        stmt = body.split("# Human Statement")[1].split("# Question")[0]
        assert "> Profile A, mailbox  X\n>   second line, verbatim" in stmt
        assert body.split("# Adopted answer")[1].split("# Applies to")[0].strip() \
            == "> Profile A, mailbox  X\n>   second line, verbatim"
        assert "Pending. Write the answer to table:Scenario data" in body
        assert f"- SC-UAT-FIX-J01#data - (no test case yet)" in body
        assert "answered" in out and "table:Scenario data" in out
        states = {x["doubt"]: x["state"] for x in s["doubts"]}
        assert states[f"{SID}-AC1-01#data"] == "answered"
        assert states[f"SC-UAT-FIX-J01#data"] == "answered"
        code, out3, err3 = _sw(d, "lint")
        assert code == 0 and "0 error(s)" in out3, out3 + err3
    _with_scratch(go)


def test_answer_partial_then_second_run_refused():
    def go(d):
        card = _emit(d, {Q2: "accept"})
        assert len(json.loads(card.read_text(encoding="utf-8"))
                   ["open_questions"]) == 2
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        assert [n for n in _res_files(d) if n != f"R-{STORY}-01.md"] == \
            [f"R-{STORY}-02.md"]
        assert "applied" in json.loads(card.read_text(encoding="utf-8"))
        _expect_refusal(d, card, "already applied")
    _with_scratch(go)


def test_answer_two_questions_numbering_in_question_order():
    def go(d):
        card = _emit(d, {Q2: "accept", Q1: "Profile A"})
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        assert _res_files(d) == [f"R-{STORY}-01.md", f"R-{STORY}-02.md",
                                 f"R-{STORY}-03.md"]
        assert wiki.read_concept(d / "resolutions" / f"R-{STORY}-02.md")[0][
            "answers"] == Q1
        assert wiki.read_concept(d / "resolutions" / f"R-{STORY}-03.md")[0][
            "answers"] == Q2
        stamp = json.loads(card.read_text(encoding="utf-8"))["applied"]
        assert stamp["resolutions"] == {Q1: f"R-{STORY}-02", Q2: f"R-{STORY}-03"}
        assert _git_out(d, "log", "-1", "--format=%s").strip() == \
            f"doubts answer: {STORY} {Q1},{Q2} by {BY}"
    _with_scratch(go)


def test_answer_numbering_continues_from_highest():
    def go(d):
        src = d / "resolutions" / f"R-{STORY}-01.md"
        fm, body = _fm_body(src)
        fm["id"] = f"R-{STORY}-07"
        wiki.write_concept(d / "resolutions" / f"R-{STORY}-07.md", fm, body)
        src.unlink()
        _git_out(d, "add", "-A")
        subprocess.run(["git", "commit", "-qm", "renumber\n\nAssertion-Event: t"],
                       cwd=d, capture_output=True)
        card = _emit(d, {Q2: "accept"})
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        assert f"R-{STORY}-08.md" in _res_files(d)
    _with_scratch(go)


def test_answer_leaves_the_real_repository_untouched():
    before = _real_status()
    real_res = sorted(p.name for p in (ROOT / "resolutions").glob("*.md"))
    real_cards = sorted(p.name for p in (ROOT / "build" / "cards").glob("*")) \
        if (ROOT / "build" / "cards").is_dir() else []

    def go(d):
        card = _emit(d, {Q2: "accept", Q1: "Profile A"})
        code, out, err = _answer(d, card)
        assert code == 0, out + err
    _with_scratch(go)
    assert _real_status() == before
    assert sorted(p.name for p in (ROOT / "resolutions").glob("*.md")) == real_res
    after_cards = sorted(p.name for p in (ROOT / "build" / "cards").glob("*")) \
        if (ROOT / "build" / "cards").is_dir() else []
    assert after_cards == real_cards


# ----------------------------------------- L15 lifts, W9, unrendered_lifts
RS = doubts_scratch.RSTORY
RF = doubts_scratch.RFLOW
RQ1, RQ2 = f"Q-{RS}-01", f"Q-{RS}-02"
RTC_A = "testcases/sit/lift-fixture/9.9-AC01-01.md"
RSIT_SPEC = f"tools/sit_specs/{RS}.yaml"


def _rwith(fn):
    d = doubts_scratch.render_project()
    try:
        return fn(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _rrender(d):
    for a in (["render_sit.py", "--story", RS], ["render_uat.py", "--flow", RF]):
        code, out, err = _sw_path(d, a)
        assert code == 0, out + err
    code, out, err = _sw(d, "seal", "--no-commit")
    assert code == 0, out + err
    _commit_all(d, "scratch: render and seal")


def _sw_path(d, args):
    r = subprocess.run([PY, str(d / "tools" / args[0]), *args[1:]], cwd=d,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, r.stdout, r.stderr


def _ranswer(d, answers):
    """Emit, answer and apply a card in the render project; returns the new
    Resolution ids."""
    before = set(_res_files(d))
    code, out, err = _sw(d, "doubts", "card", "--story", RS,
                         "--question", ",".join(answers))
    assert code == 0, out + err
    rel = out.splitlines()[0].split(":")[0]
    a = ["card", "revise", rel, "--by", BY]
    for q, v in answers.items():
        a += ["--answer", f"{q}={v}"]
    code, out, err = _sw(d, *a)
    assert code == 0, out + err
    code, out, err = _sw(d, "doubts", "answer", "--card", rel, "--by", BY)
    assert code == 0, out + err
    return sorted(n[:-3] for n in set(_res_files(d)) - before)


def _lint(d):
    code, out, err = _sw(d, "lint")
    return code, out + err


def _l15(out):
    return [ln for ln in out.splitlines() if "L15 " in ln]


def test_unrendered_lifts_and_w9_lifecycle():
    def go(d):
        assert wiki_doubts.unrendered_lifts(d) == []
        code, out = _lint(d)
        assert code == 0 and "0 error(s)" in out and "W9" not in out, out
        (rid,) = _ranswer(d, {RQ1: "accept"})
        got = wiki_doubts.unrendered_lifts(d)
        assert [e["doubt"] for e in got] == [
            "SC-LIFT-HS-01-01#data", "SC-LIFT-HS-01-01#steps",
            "SC-UAT-LIFT-J01#data"], got
        assert all(e["expected"] == f"/resolutions/{rid}.md"
                   and e["rendered"] is None and e["story"] == RS
                   for e in got), got
        assert [e["kind"] for e in got] == ["sit", "sit", "uat"]
        assert got[2]["flow"] == RF and got[0]["tc"].endswith("9.9-AC01-01")
        code, out = _lint(d)
        assert code == 0 and "0 error(s)" in out, out
        w9 = [ln[ln.index("W9"):] for ln in out.splitlines() if "W9 " in ln]
        assert w9 == [f"W9 {RS}: 3 confirmed doubt(s) not rendered - run: "
                      f"py tools/render_sit.py --story {RS} ; "
                      f"py tools/render_uat.py --flow {RF}"], w9
        _rrender(d)
        assert wiki_doubts.unrendered_lifts(d) == []
        code, out = _lint(d)
        assert code == 0 and "0 error(s)" in out and "W9" not in out, out
        assert _l15(out) == []

        # rewrite a lifted text: the rendered lift no longer holds
        def edit(spec):
            tc = next(t for t in spec["test_cases"]
                      if t["ac"] == "HS-01" and t["seq"] == 1)
            tc["steps"] = "1. Open the page.\n2. Submit twice."
        p = d / RSIT_SPEC
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        edit(spec)
        p.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True),
                     encoding="utf-8", newline="\n")
        got = wiki_doubts.unrendered_lifts(d)
        assert [(e["doubt"], e["expected"]) for e in got] == [
            ("SC-LIFT-HS-01-01#steps", None)], got
        assert got[0]["rendered"] == f"/resolutions/{rid}.md"
        assert "W9 " in _lint(d)[1]
    _rwith(go)


def test_l15_forged_lifts_and_orphan_answers():
    def go(d):
        (rid,) = _ranswer(d, {RQ1: "accept"})
        _rrender(d)
        code, out = _lint(d)
        assert code == 0 and _l15(out) == [], out
        tc = d / RTC_A
        good = tc.read_text(encoding="utf-8")
        ref = f"/resolutions/{rid}.md"
        assert good.count(ref) >= 2

        def forge(text, why):
            tc.write_text(text, encoding="utf-8", newline="\n")
            code, out = _lint(d)
            lines = [ln for ln in _l15(out) if RTC_A in ln]
            assert code == 1 and lines and any(why in ln for ln in lines), \
                (why, out)
            tc.write_text(good, encoding="utf-8", newline="\n")

        forge(good.replace(ref, "/resolutions/R-NOPE-99.md"),
              "which does not exist")
        forge(good.replace(ref, f"/resolutions/R-{RS}-01.md"),
              "which is no answer Resolution")
        forge(re.sub(r"\n\s+resolution: \S+", "", good),
              "names no resolution")
        # a correcting Resolution never lifts
        (corr,) = _ranswer(d, {RQ2: "The page shows a timeout banner."})
        forge(good.replace(ref, f"/resolutions/{corr}.md"),
              "which does not confirm (effect 'corrects')")
        # a confirming Resolution for another doubt does not lift this one
        forge(good.replace(ref, f"/resolutions/{rid}.md").replace(
            "scenario_id: SC-LIFT-HS-01-01", "scenario_id: SC-LIFT-HS-01-77"),
            "does not confirm SC-LIFT-HS-01-77#")

        rp = d / "resolutions" / f"{rid}.md"
        rgood = rp.read_text(encoding="utf-8")

        def orphan(text, why):
            assert text != rgood
            rp.write_text(text, encoding="utf-8", newline="\n")
            code, out = _lint(d)
            lines = [ln for ln in _l15(out) if f"{rid}.md" in ln]
            assert code == 1 and any(why in ln for ln in lines), (why, out)
            rp.write_text(rgood, encoding="utf-8", newline="\n")

        orphan(rgood.replace(f"answers: {RQ1}", "answers: Q-NO-SUCH-01"),
               "which is no question of the register")
        orphan(rgood.replace("confirmed_parts:\n",
                             "confirmed_parts:\n  SC-LIFT-HS-02-02#expected: abc\n"),
               "not a member of")
        orphan(rgood.replace("effect: confirms", "effect: maybe"),
               "effect is 'maybe'")
        orphan(rgood.replace("\nresolves:",
                             "\nmember_basis:\n  SC-UAT-LIFT-J02#expected: abc\n"
                             "resolves:"),
               "member_basis names SC-UAT-LIFT-J02#expected")
        orphan(re.sub(r"confirmed_parts:\n(  .*\n)+", "confirmed_parts: {}\n",
                      rgood),
               "needs a non-empty confirmed_parts")
        # a lift whose Resolution is not asserted is forged
        assert "status: asserted" in rgood
        rp.write_text(rgood.replace("status: asserted", "status: proposed"),
                      encoding="utf-8", newline="\n")
        code, out = _lint(d)
        assert code == 1 and any(RTC_A in ln and "which is not asserted" in ln
                                 for ln in _l15(out)), out
        rp.write_text(rgood, encoding="utf-8", newline="\n")
        assert _lint(d)[0] == 0
        # the pre-check must not hide a rendered lift whose Resolution is gone
        rp.unlink()
        got = wiki_doubts.unrendered_lifts(d)
        assert got and all(e["expected"] is None and e["rendered"]
                           for e in got), got
    _rwith(go)


def test_unrendered_lifts_precheck_and_w9_ignore_missing_flow():
    with tempfile.TemporaryDirectory() as t:
        assert wiki_doubts.unrendered_lifts(Path(t)) == []
    orig = wiki_doubts.unrendered_lifts
    base = {"story": "US-X", "part": "data", "tc": "t", "expected": "r",
            "rendered": None, "scenario_id": "S", "doubt": "S#data"}
    wiki_doubts.unrendered_lifts = lambda root=None: [
        {**base, "kind": "uat", "flow": None},
        {**base, "kind": "uat", "flow": "FLOW-A"},
        {**base, "kind": "sit", "flow": None}]
    try:
        out = wiki_doubts.w9_warnings(Path("."))
    finally:
        wiki_doubts.unrendered_lifts = orig
    assert out == ["W9 US-X: 3 confirmed doubt(s) not rendered - run: "
                   "py tools/render_sit.py --story US-X ; "
                   "py tools/render_uat.py --flow FLOW-A"], out



# ------------------------------------- final review: fences and robustness
SC2, EX2 = f"{SID}-AC2-02#scenario", f"{SID}-AC2-02#expected"


def _answer_fm(qid, effect, parts, status="asserted", card="c.json",
               about=("HS-02",)):
    key = "confirmed_parts" if effect == "confirms" else "member_basis"
    fm = {"title": "t", "description": "d", "status": status,
          "asserted_by": "h", "asserted_at": "2026-10-05T10:00:00+08:00",
          "resolves": [f"/stories/{STORY}.md#{a}" for a in about],
          "answers": qid, "effect": effect, "card": card, key: dict(parts)}
    return {k: v for k, v in fm.items() if v is not None}


def test_hand_written_confirms_resolution_lifts_nothing():
    """F1: a Resolution with effect confirms but no answers (or no card) is
    not an answer: it lifts nothing, closes nothing and is an L15 error."""
    basis = _row(D_DATA)["basis"]
    forged = {"status": "asserted", "effect": "confirms", "asserted_by": "x",
              "asserted_at": "2026-10-05T10:00:00+08:00",
              "resolves": [f"/stories/{STORY}.md#HS-01"],
              "confirmed_parts": {D_DATA: basis}}
    full = {"type": "Resolution", "id": f"R-{STORY}-09", **forged}
    nocard = {**full, "id": f"R-{STORY}-10", "answers": Q1}
    assert wiki_doubts.lifts_from([full]) == {}
    assert wiki_doubts.lifts_from([nocard]) == {}
    assert wiki_doubts.lifts_from([{**nocard, "card": "c.json"}]), "sanity"
    for res in ([full], [nocard]):
        _c, _r, lifted = wiki_doubts.effective_confidence(
            {"data": "Low"}, {}, f"{SID}-AC1-01", {"data": basis},
            wiki_doubts.lifts_from(res))
        assert lifted == {}, lifted
        assert _state(res, doubt=D_DATA)["state"] == "open"
    d = _mkroot(resolutions=[(full["id"], forged),
                             (nocard["id"], {**forged, "answers": Q1}),
                             (f"R-{STORY}-11", {"status": "asserted",
                                                "member_basis": {D_DATA: basis}})])
    try:
        errs = wiki_doubts.l15_errors(d)
        assert _has(errs, f"L15 resolutions/R-{STORY}-09.md", "effect",
                    "confirmed_parts", "answers"), errs
        assert _has(errs, f"L15 resolutions/R-{STORY}-10.md", "card"), errs
        assert _has(errs, f"L15 resolutions/R-{STORY}-11.md",
                    "member_basis"), errs
        st = {x["doubt"]: x["state"]
              for x in wiki_doubts.story_summary(STORY, root=d)["doubts"]}
        assert st[D_DATA] == "open", st
        assert wiki_doubts.load_lifts(d) == {}
    finally:
        _cleanup(d)


def test_forged_lift_names_a_resolution_that_is_no_answer():
    """F1.3: a rendered lift backed by an asserted confirms Resolution that
    carries no answers/card is forged."""
    d = _mkroot()
    try:
        rid = f"R-{STORY}-09"
        res = [{"type": "Resolution", "id": rid, "status": "asserted",
                "effect": "confirms",
                "confirmed_parts": {f"{SID}-AC1-01#data": "x"}}]
        tc = d / "testcases" / "fixture" / "TC-FIX-0001.md"
        tc.parent.mkdir(parents=True)
        wiki.write_concept(tc, {
            "type": "Test Case", "id": "TC-FIX-0001", "title": "t",
            "description": "d", "scenario_id": f"{SID}-AC1-01",
            "confidence_parts": {"data": {
                "level": "High", "remark": "r", "authored": "Low",
                "resolution": f"/resolutions/{rid}.md"}}}, "body\n")
        errs = wiki_doubts._forged_lift_errors(d, res)
        assert _has(errs, "confidence_parts.data", rid, "no answer"), errs
    finally:
        _cleanup(d)


def test_state_closed_and_answered_come_from_answer_resolutions():
    """F2: closed derives from lifts_from; answered/rewritten only from
    asserted answer Resolutions with effect corrects."""
    b = _row(D_STEPS)["basis"]
    both = {"id": "R-1", "status": "asserted", "answers": Q1, "card": "c.json",
            "effect": "corrects", "member_basis": {D_STEPS: b},
            "confirmed_parts": {D_STEPS: b}}
    assert _state([both])["state"] == "answered"
    assert wiki_doubts.lifts_from([both]) == {}
    noans = {"id": "R-2", "status": "asserted", "effect": "confirms",
             "confirmed_parts": {D_STEPS: b}}
    assert _state([noans])["state"] == "open"
    corr = {"id": "R-3", "status": "asserted", "effect": "corrects",
            "member_basis": {D_STEPS: b}}
    assert _state([corr])["state"] == "open"
    for r in ([both], [noans], [corr], [_res("R-4", "confirms", D_STEPS, b)]):
        closed = _state(r)["state"] == "closed"
        lifted = bool(wiki_doubts.lifts_from(r).get(D_STEPS))
        assert closed == lifted, r


def _drop_ac2_02(d):
    p = d / "tools" / "sit_specs" / f"{STORY}.yaml"
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    spec["test_cases"] = [t for t in spec["test_cases"]
                          if not (t["ac"] == "AC2" and t["seq"] == 2)]
    p.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")


def test_l15_membership_skips_vanished_doubts_only():
    """F8: an answered member whose test case left the spec can be dropped
    from the register without locking lint; a member key that is a current
    doubt outside the question stays an error."""
    bases = {SC2: _row(SC2)["basis"], EX2: _row(EX2)["basis"]}
    rid = f"R-{STORY}-05"
    d = _mkroot(resolutions=[(rid, _answer_fm(Q2, "confirms", bases))])
    try:
        assert wiki_doubts.l15_errors(d) == [], wiki_doubts.l15_errors(d)
        _drop_ac2_02(d)
        # keeping the members: the register names an unknown scenario
        assert _has(wiki_doubts.l15_errors(d), "unknown scenario id")
        # dropping them is the legal exit
        reg = d / "doubts" / f"{STORY}.yaml"
        r = yaml.safe_load(reg.read_text(encoding="utf-8"))
        r["questions"][1]["members"] = []
        reg.write_text(yaml.safe_dump(r, sort_keys=False), encoding="utf-8")
        assert wiki_doubts.l15_errors(d) == [], wiki_doubts.l15_errors(d)
    finally:
        _cleanup(d)
    # a current doubt in another question, or in none, stays an error
    other = {SC2: _row(SC2)["basis"], D_STEPS: _row(D_STEPS)["basis"],
             "SC-UAT-FIX-J02#expected": "sha256:x"}
    d = _mkroot(resolutions=[(rid, _answer_fm(Q2, "confirms", other)),
                             (f"R-{STORY}-06", _answer_fm(
                                 Q2, "confirms", {D_DATA: "x"},
                                 status="proposed"))])
    try:
        errs = wiki_doubts.l15_errors(d)
        assert _has(errs, f"{rid}.md", D_STEPS, "not a member"), errs
        assert _has(errs, f"{rid}.md", "SC-UAT-FIX-J02#expected",
                    "not a member"), errs
        assert not _has(errs, f"{rid}.md", SC2), errs
        # the membership check applies only to asserted Resolutions
        assert not _has(errs, f"R-{STORY}-06.md", "not a member"), errs
    finally:
        _cleanup(d)


def test_l15_observations_and_register_with_non_string_ids_never_raise():
    """F6: list-valued observation question / register id are messages."""
    d = _mkroot()
    try:
        p = d / "doubts" / "observations" / f"{STORY}.yaml"
        p.parent.mkdir(parents=True)
        obs = {"question": [Q1], "text": ["x"], "by": "t",
               "at": "2026-10-06T10:00:00+08:00", "workbook_hash": "ab"}
        p.write_text(yaml.safe_dump({"story": f"/stories/{STORY}.md",
                                     "observations": [obs]}), encoding="utf-8")
        reg = d / "doubts" / f"{STORY}.yaml"
        r = yaml.safe_load(reg.read_text(encoding="utf-8"))
        r["questions"][0]["id"] = [Q1]
        reg.write_text(yaml.safe_dump(r, sort_keys=False), encoding="utf-8")
        errs = wiki_doubts.l15_errors(d)
        assert _has(errs, "L15 doubts/observations/", "question"), errs
        assert _has(errs, "L15 doubts/observations/", "text"), errs
        assert wiki_doubts.latest_observations([obs]) == {}
    finally:
        _cleanup(d)


def test_bad_specs_yield_no_rows_and_one_l15_line_each():
    """F6: a bad spec never raises in the collectors, W8, W9 or L15."""
    d = _mkroot()
    try:
        sit, uat = d / "tools" / "sit_specs", d / "tools" / "uat_specs"
        (uat / "NOFLOW.yaml").write_text(
            "scenario_id: SC-NF-{jid}\nentries:\n  J01: {confidence: "
            "{steps: Low}}\n", encoding="utf-8")
        (uat / "GHOST.yaml").write_text(
            "flow: /flows/FLOW-NOT-THERE.md\nscenario_id: SC-GH-{jid}\n"
            "entries:\n  J01: {steps: s, confidence: {steps: Low}}\n",
            encoding="utf-8")
        (uat / "LIST.yaml").write_text("- a\n- b\n", encoding="utf-8")
        (sit / "BROKEN.yaml").write_text("story: [unclosed\n", encoding="utf-8")
        (sit / "NOID.yaml").write_text(
            "story: /stories/X.md\ntest_cases:\n  - {ac: A, seq: 1}\n",
            encoding="utf-8")
        (sit / "BINARY.yaml").write_bytes(b"\xff\xfe\x00bad")
        rows = wiki_doubts.collect_all(root=d)
        assert not any(r["doubt"].startswith("SC-NF-") for r in rows), rows
        # a missing flow concept is not fatal: its rows have no story
        assert [r["story"] for r in rows if r["doubt"].startswith("SC-GH-")] \
            == [None]
        errs = wiki_doubts.l15_errors(d)
        for name in ("uat_specs/NOFLOW.yaml", "uat_specs/LIST.yaml",
                     "sit_specs/BROKEN.yaml", "sit_specs/NOID.yaml",
                     "sit_specs/BINARY.yaml"):
            assert sum(1 for e in errs if f"L15 tools/{name}:" in e) == 1, \
                (name, errs)
        assert not _has(errs, "GHOST.yaml"), errs
        wiki_doubts.w8_warnings(d)
        wiki_doubts.w9_warnings(d)
        wiki_doubts._flow_of_scenarios(d)
        wiki_doubts._uat_flows(d, ["SC-NF-J01#steps", "SC-GH-J01#steps"])
        wiki_doubts.story_summary(STORY, root=d)
    finally:
        _cleanup(d)


def test_fresh_observations_survive_list_values():
    """F6: the observe duplicate check skips malformed existing entries."""
    have = [{"question": [Q1], "text": "a", "workbook_hash": "h"},
            {"question": Q1, "text": ["a"], "workbook_hash": "h"},
            {"question": Q1, "text": "same", "workbook_hash": "h"}]
    new = [{"question": Q1, "text": "same", "workbook_hash": "h"},
           {"question": Q1, "text": "a", "workbook_hash": "h"},
           {"question": Q1, "text": "a", "workbook_hash": "h"}]
    got = wiki_doubts._fresh_observations(have, new)
    assert got == [new[1]], got


def _entry_for(qid, proposed, origin=None):
    e = {"id": qid, "question": "Which one?", "about": ["HS-01"],
         "home": "table:Scenario data", "proposed": proposed,
         "members": [{"doubt": D_DATA, "basis": "sha256:b", "tc": "TC-1"}]}
    if origin:
        e.update(proposed_origin=origin, observed_by="carol",
                 observation_at="2026-10-06T10:00:00+08:00")
    return e


def _section(body, head):
    return body.split(f"\n# {head}\n", 1)[1].split("\n# ", 1)[0]


def test_adopted_answer_is_quoted_and_cannot_forge_a_section():
    """F9: correcting and observed text is a blockquote under # Adopted
    answer, so a '# Propagation' line in it is no heading."""
    text = "Profile A\n# Propagation\nfake  spaced\n\nend"
    quoted = "> Profile A\n> # Propagation\n> fake  spaced\n>\n> end"
    for entry, ans in (
            (_entry_for(Q1, None), {"decision": "correct", "value": text}),
            (_entry_for(Q1, text, origin="tester-observation"),
             {"decision": "accept", "value": None})):
        _fm, body = wiki_doubts._resolution(STORY, f"R-{STORY}-02", entry, ans,
                                            "h", "card.json", "now")
        heads = re.findall(r"^# .+$", body, re.M)
        assert heads == ["# Human Statement", "# Question", "# Adopted answer",
                         "# Applies to", "# Propagation"], heads
        assert _section(body, "Adopted answer").strip() == quoted, body
    _fm, body = wiki_doubts._resolution(
        STORY, f"R-{STORY}-02", _entry_for(Q2, "The page shows done."),
        {"decision": "accept", "value": None}, "h", "card.json", "now")
    assert _section(body, "Adopted answer").strip() == "The page shows done."


# ------------------------------- final review: answer is atomic and fenced
def _commit_all(d, msg="scratch: test setup"):
    _git_out(d, "add", "-A")
    r = subprocess.run(["git", "commit", "-qm", msg + "\n\nAssertion-Event: t"],
                       cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_answer_refuses_dirty_tree_lint_errors_and_rolls_back():
    """F1.4, F1.5, F3: the dirty-tree refusal, the lint gate before any
    write, an answer Resolution committed by hand is L15, and a commit that
    fails after writing rolls everything back."""
    def go(d):
        card = _emit(d, {Q2: "accept"})
        stray = d / "notes.txt"
        stray.write_text("x\n", encoding="utf-8")
        err = _expect_refusal(d, card, "the working tree has other uncommitted "
                                       "changes")
        assert "notes.txt" in err, err
        stray.unlink()
        # a hand-written answer Resolution (to Q1, which the card does not
        # answer): uncommitted it is exempt from the adding-commit check,
        # committed by hand it is an L15 error
        s = wiki_doubts.story_summary(STORY, root=d)
        bases = {x["doubt"]: x["basis"] for x in s["doubts"]
                 if x["question"] == Q1}
        assert len(bases) == 3, bases
        forged = d / "resolutions" / f"R-{STORY}-05.md"
        wiki.write_concept(forged, {"type": "Resolution", "id": forged.stem,
                                    **_answer_fm(Q1, "corrects", bases,
                                                 about=("HS-01",))},
                           "body\n")
        code, out, err = _sw(d, "lint")
        assert "cli-doubts-answer" not in out, out
        _commit_all(d, "hand: add an answer")
        code, out, err = _sw(d, "lint")
        assert code == 1 and any(
            f"L15 resolutions/{forged.name}" in ln and "cli-doubts-answer" in ln
            for ln in out.splitlines()), out
        log = d / "log.md"
        log_before = log.read_bytes() if log.exists() else None
        err = _expect_refusal(d, card, "does not lint clean")
        assert f"R-{STORY}-05.md" in err, err
        assert (log.read_bytes() if log.exists() else None) == log_before
        forged.unlink()
        _commit_all(d, "hand: remove it")
        # a commit that fails after the write: everything is rolled back
        hook = d / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        before = (_res_files(d), _commits(d), card.read_bytes(),
                  log.read_bytes() if log.exists() else None)
        code, out, err = _answer(d, card)
        assert code == 1, (code, out, err)
        assert "rolled back" in err, err
        after = (_res_files(d), _commits(d), card.read_bytes(),
                 log.read_bytes() if log.exists() else None)
        assert before == after, "a failed commit left state behind"
        assert _git_out(d, "status", "--porcelain").strip() == ""
        hook.unlink()
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        assert _commits(d) == before[1] + 1
    _with_scratch(go)


def test_answered_question_is_confirmed_on_the_next_card():
    """F5: a correcting answer whose text needs no rewrite is confirmed on
    the next card (kind confirm, current text), and accept closes it."""
    def go(d):
        card = _emit(d, {Q2: "The page shows done, as it says."})
        code, out, err = _answer(d, card)
        assert code == 0, out + err
        c2 = _emit(d, questions=[Q2])
        q = json.loads(c2.read_text(encoding="utf-8"))["open_questions"][0]
        assert q["kind"] == "confirm" and q["proposed"].startswith(
            f"Answered by R-{STORY}-02; confirm the text shown"), q
        assert [m["doubt"] for m in q["members"]] == [SC2, EX2]
        code, out, err = _sw(d, "card", "revise", str(c2.relative_to(d)),
                             "--by", BY, "--answer", f"{Q2}=accept")
        assert code == 0, out + err
        code, out, err = _answer(d, c2)
        assert code == 0, out + err
        fm = wiki.read_concept(d / "resolutions" / f"R-{STORY}-03.md")[0]
        assert fm["effect"] == "confirms" and fm["answers"] == Q2
        st = {x["doubt"]: x["state"]
              for x in wiki_doubts.story_summary(STORY, root=d)["doubts"]}
        assert st[SC2] == st[EX2] == "closed", st
        code, out, err = _sw(d, "lint")
        assert code == 0 and "0 error(s)" in out, out + err
    _with_scratch(go)



def test_suite_export_leaves_the_doubts_sheet_out_when_summaries_fail():
    """F6: compile_suite's doubt summaries never stop an export."""
    import wiki_suite
    d = _mkroot()
    orig = wiki_doubts.stories_with_doubts
    try:
        got = wiki_suite.doubt_summaries(root=d)
        assert [s["story"] for s in got] == [STORY], got

        def boom(root=None, _rows=None):
            raise KeyError("flow")
        wiki_doubts.stories_with_doubts = boom
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert wiki_suite.doubt_summaries(root=d) is None
        assert "Doubts sheet is left out" in err.getvalue(), err.getvalue()
        assert len(err.getvalue().splitlines()) == 1
    finally:
        wiki_doubts.stories_with_doubts = orig
        _cleanup(d)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"[PASS] {name}")
            except Skip as e:
                print(f"[SKIP] {name} ({e})")
            except Exception as e:
                fails += 1; print(f"[FAIL] {name}: {e}")
    sys.exit(1 if fails else 0)
