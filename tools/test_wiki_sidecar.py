#!/usr/bin/env python3
"""The sidecar written beside every compiled workbook
(run: py tools/test_wiki_sidecar.py)."""
import inspect
import json
import re
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki_export
import wiki_suite

A, B, C = (f"testcases/sit/m/1.1-AC01-0{i}" for i in (1, 2, 3))
MANIFEST = {"tc_hashes": {A: "sha256:" + "a" * 64, B: "sha256:" + "b" * 64,
                          C: "sha256:" + "c" * 64}}
SUITE = {"type": "suite", "name": "demo"}


def _write(rels, source=SUITE, manifest=MANIFEST):
    with tempfile.TemporaryDirectory() as d:
        xlsx = Path(d) / "demo_20261004-101500.xlsx"
        xlsx.write_bytes(b"")
        path = wiki_suite.write_sidecar(xlsx, source, rels, manifest)
        assert path.parent == xlsx.parent, path
        return path.name, path.read_bytes()


def test_sidecar_sits_beside_the_workbook_under_the_same_stem():
    name, _raw = _write([A])
    assert name == "demo_20261004-101500.json", name


def test_sidecar_lists_exactly_the_given_test_cases_in_order():
    _name, raw = _write([B, A])
    doc = json.loads(raw)
    assert list(doc["tcs"].items()) == [(B, "sha256:" + "b" * 64),
                                        (A, "sha256:" + "a" * 64)], doc["tcs"]


def test_sidecar_records_source_compile_time_and_commit():
    source = {"type": "export", "name": "US-X-sit", "story": "US-X"}
    _name, raw = _write([A], source=source)
    doc = json.loads(raw)
    assert set(doc) == {"compiled_at", "wiki_commit", "source", "tcs",
                        "tcs_order"}, sorted(doc)
    assert doc["tcs_order"] == "sheet", doc
    assert doc["source"] == source
    assert datetime.fromisoformat(doc["compiled_at"]).tzinfo is not None, doc["compiled_at"]
    assert doc["wiki_commit"] is None or re.fullmatch(r"[0-9a-f]{40}", doc["wiki_commit"]), doc


def test_a_test_case_the_manifest_never_sealed_is_recorded_as_null():
    _name, raw = _write(["testcases/sit/m/never-sealed"], manifest={})
    assert json.loads(raw)["tcs"] == {"testcases/sit/m/never-sealed": None}


def test_sidecar_is_utf8_with_lf_endings_and_a_final_newline():
    _name, raw = _write([A], source={"type": "suite", "name": "démo"})
    assert b"\r" not in raw and raw.endswith(b"}\n"), raw[-20:]
    assert "démo" in raw.decode("utf-8")


def test_both_compile_commands_write_the_sidecar_and_its_latest_copy():
    """The end-to-end check lives in smoke's full tier (it needs project
    content); this pins the wiring on every run."""
    # `export` writes a workbook on two paths (the draft and the final), so
    # the wiring is pinned once per path.
    for fn, paths in ((wiki_suite.compile_suite, 1), (wiki_export.cmd_export, 2)):
        src = inspect.getsource(fn)
        marks = ("= render_xlsx(",      # the refs come from the renderer's own
                                        # plan, not from the selection
                 "write_sidecar(xlsx_ts,",
                 "shutil.copyfile(xlsx_ts, xlsx_latest)",
                 'shutil.copyfile(sidecar, xlsx_latest.with_suffix(".json"))')
        found = {m: [i for i in range(len(src)) if src.startswith(m, i)]
                 for m in marks}
        for m in marks:
            assert len(found[m]) == paths, (fn.__name__, m, len(found[m]))
        # The sidecar is written before -latest is touched, and the workbook
        # is copied before its sidecar: whichever write fails, -latest.xlsx
        # and -latest.json are left as a pair that describes one compile.
        for n in range(paths):
            steps = [found[m][n] for m in marks]
            assert steps == sorted(steps), (fn.__name__, n, steps)


def _interleaved():
    """tc_sort_key order: journey UAT, SIT (run "Main flow"), plain UAT.
    plan_sheets regroups by run, so the sheets hold them journey UAT, plain
    UAT (C-TC-1), then SIT (C-TC-2)."""
    def tc(tid, kind, **extra):
        fm = {"type": "Test Case", "id": tid, "kind": kind, "status": "active",
              "module": "/modules/m.md", "scenario_id": f"SC-{tid}",
              "covers": ["/stories/US-X.md#AC1"], "title": tid,
              "confidence": "High"}
        fm.update(extra)
        body = "# Steps\n1. Go.\n\n# Expected Results\n1. Ok.\n"
        return (f"testcases/{kind}/{tid}", fm, body)
    return [tc("UAT-0.1-AC01-01", "uat", covers=["/flows/f.md#J1"]),
            tc("1.1-AC01-01", "sit", run="Main flow", section="S"),
            tc("UAT-1.1-AC01-01", "uat")]


def test_render_returns_the_refs_in_sheet_and_row_order():
    tcs = _interleaved()
    keys = [wiki_suite.tc_sort_key(fm) for _r, fm, _b in tcs]
    assert keys == sorted(keys), keys
    concepts = {rel: (fm, body, None) for rel, fm, body in tcs}
    with tempfile.TemporaryDirectory() as d:
        order = wiki_suite.render_xlsx(tcs, "t", Path(d) / "x.xlsx",
                                       concepts=concepts, manifest={})
        from openpyxl import load_workbook
        wb = load_workbook(Path(d) / "x.xlsx")
    assert order == ["testcases/uat/UAT-0.1-AC01-01", "testcases/uat/UAT-1.1-AC01-01",
                     "testcases/sit/1.1-AC01-01"], order
    seen = [str(ws.cell(row=r, column=1).value)
            for ws in wb.worksheets if ws.title.startswith("C-TC")
            for r in range(wiki_suite.TC_HEADER_ROW + 1, ws.max_row + 1)
            if str(ws.cell(row=r, column=1).value).startswith("TC-")]
    assert seen == ["TC-0.1-AC01-01", "TC-1.1-AC01-01", "TC-1.1-AC01-01"], seen


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except Exception as e:
                failed += 1
                print(f"[FAIL] {name}: {e!r}")
                traceback.print_exc()
    print("test_wiki_sidecar " + ("FAILED" if failed else "OK"))
    sys.exit(1 if failed else 0)
