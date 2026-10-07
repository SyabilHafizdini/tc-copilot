#!/usr/bin/env python3
"""Plain-assert tests for the test case grid read model
(run: py tools/test_app_testcase_models.py). Runs against the real wiki and
asserts the payload against the workbook export's own functions, so it holds
for whatever project this bundle is checked out as."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
import testcase_models
import wiki
import wiki_suite
import wiki_tcedit
from testkit import require

ROW_KEYS = {"ref", "id", "display_id", "level", "story", "flow", "module", "run",
            "section", "order", "group", "status", "priority", "technique",
            "covers", "title", "objective", "scenario", "chain", "steps", "data",
            "expected", "element_block", "pre_extra", "post", "confidence",
            "parts", "part_fields", "cells", "editable", "spec", "prds"}
PAYLOAD = None


def _payload():
    global PAYLOAD
    if PAYLOAD is None:
        PAYLOAD = testcase_models.testcases()
    return PAYLOAD


def test_payload_shape_and_json_safety():
    p = _payload()
    assert set(p) == {"rows", "groups"}, sorted(p)
    json.dumps(p)
    for r in p["rows"]:
        assert set(r) == ROW_KEYS, (r.get("id"), sorted(set(r) ^ ROW_KEYS))
        assert set(r["parts"]) == {"scenario", "steps", "data", "expected"}
        for part in r["parts"].values():
            assert set(part) == {"level", "authored", "remark", "state",
                                 "question", "resolution"}, sorted(part)
        assert set(r["cells"]) == {"scenario", "steps", "data", "expected", "remarks"}
    for g in p["groups"]:
        assert set(g) == {"key", "label", "kind", "level", "sections", "common"}, g
        assert g["kind"] in ("run", "module", "flow"), g


def test_group_common_is_the_exports_shared_precondition_block():
    concepts, _m = wiki.load_all()
    by_key = {g["key"]: g for g in _payload()["groups"]}
    checked = 0
    for kind in testcase_models.LEVELS:
        selected, _retired, _stale = wiki_suite.select({"kind": kind}, concepts)
        for _name, _mod, subs, _dash in wiki_suite.plan_sheets(selected, concepts):
            sheet = [tc for _s, _f, tcl in subs for tc in tcl]
            if not sheet:
                continue
            key = testcase_models._group_of(kind, sheet[0][1], concepts)[0]
            assert by_key[key]["common"] == wiki_suite.sheet_common(sheet), key
            checked += 1
    assert checked
    for g in by_key.values():
        assert isinstance(g["common"], list)


def test_journey_rows_key_active_flow_test_cases_by_the_entry_they_walk():
    def row(tid, status, covers):
        return {"display_id": tid, "status": status, "covers": covers, "section": "Login",
                "confidence": "High",
                "cells": {"scenario": "s", "steps": "1. x", "data": "", "expected": "e", "remarks": "r"}}
    out = testcase_models.journey_rows([
        row("TC-A", "active", ["/stories/US-T.md#AC-1", "/flows/FLOW-T.md#J01"]),
        row("TC-B", "retired", ["/flows/FLOW-T.md#J02"]),
        row("TC-C", "active", ["/stories/US-T.md#AC-1"]),
    ])
    assert out == {"FLOW-T#J01": {"id": "TC-A", "section": "Login", "confidence": "High",
                                  "scenario": "s", "steps": "1. x", "data": "",
                                  "expected": "e", "remarks": "r"}}, out


def test_every_test_case_is_a_row_once():
    concepts, _m = wiki.load_all()
    want = sorted(fm["id"] for _r, (fm, _b, _p) in concepts.items()
                  if fm and fm.get("type") == "Test Case"
                  and fm.get("kind") in testcase_models.LEVELS)
    assert sorted(r["id"] for r in _payload()["rows"]) == want


def test_active_rows_carry_the_cells_the_export_builds():
    """The grid cannot diverge from the sheet: for the full SIT and UAT
    selections, a row's cells are exactly wiki_suite.tc_cells over the sheet
    plan the export uses."""
    import wiki_doubts
    concepts, _m = wiki.load_all()
    qmap = wiki_suite._question_map(
        [wiki_doubts.story_summary(s) for s in wiki_doubts.stories_with_doubts()])
    by_id = {r["id"]: r for r in _payload()["rows"]}
    checked = 0
    for kind in testcase_models.LEVELS:
        selected, _retired, _stale = wiki_suite.select({"kind": kind}, concepts)
        for _name, _mod, subs, _dash in wiki_suite.plan_sheets(selected, concepts):
            sheet = [tc for _s, _f, tcl in subs for tc in tcl]
            common = wiki_suite.sheet_common(sheet)
            for _rel, fm, body in sheet:
                c = wiki_suite.tc_cells(fm, body, concepts, common, qmap)
                row = by_id[fm["id"]]
                assert row["display_id"] == c["id"]
                assert row["scenario"] == c["scenario"]
                assert row["confidence"] == c["confidence"]
                assert row["cells"] == {k: c[k] for k in row["cells"]}, fm["id"]
                checked += 1
    assert checked == sum(1 for r in by_id.values() if r["status"] == "active")


def test_parts_recombine_into_the_export_cells():
    """What the panel shows part by part is the same text the cell shows whole:
    chain + steps, data + extra pre-conditions, own expected + element block.
    Holds for every active row whose spec is rendered and sealed."""
    for r in _payload()["rows"]:
        if r["status"] != "active" or not r["spec"]:
            continue
        c = r["cells"]
        assert c["steps"] == (r["chain"] + "\n\n" if r["chain"] else "") + r["steps"], r["id"]
        assert c["expected"] == r["expected"] + \
            ("\n" + r["element_block"] if r["element_block"] else ""), r["id"]
        if r["level"] == "sit":
            assert r["pre_extra"] in c["data"] and c["data"].startswith(r["data"]), r["id"]


def test_rows_and_groups_follow_workbook_order():
    concepts, _m = wiki.load_all()
    p = _payload()
    for level in testcase_models.LEVELS:
        tcs = sorted((fm for _r, (fm, _b, _p) in concepts.items()
                      if fm and fm.get("type") == "Test Case" and fm.get("kind") == level),
                     key=wiki_suite.tc_sort_key)
        assert [r["id"] for r in p["rows"] if r["level"] == level] == \
            [fm["id"] for fm in tcs]
        runs = [name for name, _t in wiki_suite.run_groups(
            [(None, fm, "") for fm in tcs]) if name]
        assert [g["label"] for g in p["groups"]
                if g["level"] == level and g["kind"] == "run"] == runs
    keys = [g["key"] for g in p["groups"]]
    assert len(keys) == len(set(keys)), keys
    assert {r["group"] for r in p["rows"]} == set(keys)
    for g in p["groups"]:
        seen = []
        for r in p["rows"]:
            if r["group"] == g["key"] and r["section"] and r["section"] not in seen:
                seen.append(r["section"])
        assert g["sections"] == seen, g["key"]


def test_editable_matches_what_tc_edit_accepts():
    index = wiki_tcedit.spec_index()
    concepts, _m = wiki.load_all()
    fms = {fm["id"]: fm for _r, (fm, _b, _p) in concepts.items()
           if fm and fm.get("type") == "Test Case"}
    for r in _payload()["rows"]:
        assert r["editable"] == wiki_tcedit.editable_fields(fms[r["id"]], index), r["id"]
        if r["level"] == "uat":
            assert "data" not in r["editable"] and "post" not in r["editable"]
        if r["status"] != "active":
            assert r["editable"] == [], r["id"]
        if r["editable"]:
            assert r["spec"] and (ROOT / r["spec"]).is_file(), r["spec"]


def test_editor_text_is_the_spec_text():
    index = wiki_tcedit.spec_index()
    concepts, _m = wiki.load_all()
    sc = {fm["id"]: fm.get("scenario_id") for _r, (fm, _b, _p) in concepts.items()
          if fm and fm.get("type") == "Test Case"}
    for r in _payload()["rows"]:
        for field in r["editable"]:
            entry = index[sc[r["id"]]][3]
            if isinstance(entry.get(field), str) and field != "data":
                assert r[field] == entry[field], (r["id"], field)


def test_part_fields_mirror_the_doubt_rules():
    """Which spec fields make up a confidence part is wiki_doubts.PART_TEXT;
    the panel uses it to warn before an edit re-opens a confirmed part."""
    import wiki_doubts
    for r in _payload()["rows"]:
        for part, fields in r["part_fields"].items():
            assert fields == list(wiki_doubts.PART_TEXT[(r["level"], part)]), r["id"]


def test_testcases_does_not_mutate_the_repo():
    def status():
        return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                              capture_output=True, text=True).stdout
    before = status()
    testcase_models.testcases()
    assert status() == before


class _Patched:
    """Run testcases() against a temporary input root and a counted fake
    builder, restoring the module afterwards. Touches nothing in the repo."""
    def __init__(self, tmp, build=None):
        self.tmp, self.calls = Path(tmp), []
        self.build = build or (lambda: {"rows": [], "groups": []})

    def __enter__(self):
        self.saved = (testcase_models._signature, testcase_models._build,
                      testcase_models._CACHE)
        real_sig = self.saved[0]
        testcase_models._signature = lambda root=None: real_sig(self.tmp)
        testcase_models._build = lambda: (self.calls.append(1), self.build())[1]
        testcase_models._CACHE = None
        return self

    def __exit__(self, *exc):
        (testcase_models._signature, testcase_models._build,
         testcase_models._CACHE) = self.saved


def _tmp_root():
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "config.yaml").write_text("a: 1\n", encoding="utf-8")
    (d / "doubts").mkdir()
    return d


def test_cache_skips_the_build_when_nothing_changed():
    with _Patched(_tmp_root()) as p:
        testcase_models.testcases()
        testcase_models.testcases()
        testcase_models.testcases()
        assert p.calls == [1], p.calls


def test_cache_rebuilds_when_an_input_mtime_changes():
    import os
    root = _tmp_root()
    target = root / "config.yaml"
    with _Patched(root) as p:
        testcase_models.testcases()
        st = target.stat()
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        testcase_models.testcases()
        assert p.calls == [1, 1], p.calls
        testcase_models.testcases()
        assert p.calls == [1, 1], p.calls


def test_signature_sees_added_and_removed_inputs():
    root = _tmp_root()
    sig = testcase_models._signature(root)
    extra = root / "doubts" / "ZZ.yaml"
    extra.write_text("story: x\nquestions: []\n", encoding="utf-8")
    assert testcase_models._signature(root) != sig
    extra.unlink()
    assert testcase_models._signature(root) == sig


def test_signature_survives_files_vanishing_mid_scan():
    import os
    root = _tmp_root()
    (root / "doubts" / "A.yaml").write_text("x: 1\n", encoding="utf-8")
    (root / "doubts" / "B.yaml").write_text("x: 1\n", encoding="utf-8")
    sig_ok = testcase_models._signature(root)
    real_scan = os.scandir

    class Boom:
        """A DirEntry whose stat raises, as if the file just vanished."""
        def __init__(self, e):
            self._e, self.name, self.path = e, e.name, e.path
        def is_dir(self, follow_symlinks=True):
            return self._e.is_dir(follow_symlinks=follow_symlinks)
        def stat(self):
            if self.name == "A.yaml":
                raise FileNotFoundError(self.path)
            return self._e.stat()

    class Scan:
        def __init__(self, path):
            self._it = real_scan(path)
            self._path = str(path)
        def __enter__(self):
            return (Boom(e) for e in list(self._it))
        def __exit__(self, *a):
            self._it.close()

    def flaky(path):
        if str(path).endswith("sit_specs"):
            raise FileNotFoundError(path)  # directory deleted mid-walk
        return Scan(path)

    os.scandir = flaky
    try:
        sig = testcase_models._signature(root)
    finally:
        os.scandir = real_scan
    names = [r[0] for r in sig]
    assert "doubts/B.yaml" in names and "doubts/A.yaml" not in names, names
    assert len(sig) < len(sig_ok) + 1


def test_concurrent_cold_calls_build_once_and_never_return_none():
    import threading
    import time
    root = _tmp_root()
    payload = {"rows": [{"id": "X"}], "groups": []}

    def slow():
        time.sleep(0.3)
        return payload

    with _Patched(root, build=slow) as p:
        out, errs = [], []

        def worker():
            try:
                out.append(testcase_models.testcases())
            except Exception as e:  # noqa
                errs.append(e)

        ts = [threading.Thread(target=worker) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert not errs, errs
        assert p.calls == [1], p.calls
        assert len(out) == 4 and all(o == payload for o in out), out
        assert all(o is not payload for o in out)

def test_mutating_the_result_does_not_change_the_next_call():
    a = testcase_models.testcases()
    want = json.dumps(a, sort_keys=True)
    a["rows"].clear()
    a["groups"].append("junk")
    if _payload()["rows"]:
        b = testcase_models.testcases()
        b["rows"][0]["cells"]["steps"] = "MUTATED"
    assert json.dumps(testcase_models.testcases(), sort_keys=True) == want


if __name__ == "__main__":
    require("Test Case", "test_app_testcase_models")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_testcase_models OK")
