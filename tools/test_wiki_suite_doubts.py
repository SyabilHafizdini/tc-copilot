#!/usr/bin/env python3
"""Doubts sheet and question ids in Test Case Remarks
(run: py tools/test_wiki_suite_doubts.py)."""
import sys
import tempfile
import traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki_suite

HEADERS = ["Question ID", "Question", "Status", "Test cases", "Lowest level",
           "Affected (TC id / column)", "Answer", "Observation", "Observed by", "Date"]


def _concepts():
    return {
        "modules/m": ({"type": "Module", "title": "Alpha Module",
                       "description": "PRD section §1"}, "", None),
        "stories/US-X": ({"type": "User Story", "title": "Story X",
                          "description": "§1.1"}, "", None),
    }


def _tc(i, parts=None, run=None):
    fm = {"id": f"1.1-AC01-{i:02d}", "module": "/modules/m.md",
          "scenario_id": f"SC-X-{i:02d}",
          "covers": ["/stories/US-X.md#AC1"], "section": "S",
          "confidence": "Low", "title": "t"}
    if run:
        fm["run"] = run
    if parts is not None:
        fm["confidence_parts"] = {p: {"level": lv, "remark": f"Inferred: {p} {i}."}
                                  for p, lv in parts.items()}
    body = "# Steps\n1. Do.\n\n# Expected Results\n1. Done.\n"
    return (f"testcases/sit/m/{fm['id']}", fm, body)


def _mem(i, part, level="Low", state="open", resolution=None):
    sid = f"SC-X-{i:02d}"
    return {"doubt": f"{sid}#{part}", "scenario_id": sid, "part": part,
            "level": level, "state": state, "resolution": resolution,
            "remark": f"Inferred: {part} {i}."}


def _q(qid, members, status="open"):
    live = [m for m in members if m["state"] != "closed"]
    return {"id": qid, "question": f"Question {qid}?", "status": status,
            "open_tcs": len({m["scenario_id"] for m in live}),
            "low": sum(1 for m in live if m["level"] == "Low"),
            "members": members}


def _summary(questions, ungrouped=(), errors=()):
    doubts = [m for q in questions for m in q["members"]] + list(ungrouped)
    return {"story": "US-X", "questions": list(questions),
            "ungrouped_doubts": list(ungrouped), "doubts": doubts,
            "register_errors": list(errors), "register": True}


def _fixture():
    tcs = [_tc(1, {"scenario": "High", "data": "Low"}),
           _tc(2, {"data": "Low", "expected": "Medium"}),
           _tc(3, {"data": "Low", "steps": "Medium"}),
           _tc(4, {"data": "High"})]          # TC 4 is selected, no doubts
    qa = _q("Q-X-01", [_mem(1, "data"), _mem(2, "data")])
    qb = _q("Q-X-02", [_mem(3, "data"), _mem(2, "expected", "Medium")])
    qc = _q("Q-X-03", [_mem(9, "data")])       # TC 9 is not selected
    ung = {**_mem(3, "steps", "Medium"), "question": None}
    return tcs, [_summary([qc, qb, qa], [ung])]


def _render(tcs, summaries, path=None):
    from openpyxl import load_workbook
    with tempfile.TemporaryDirectory() as d:
        out = Path(path) if path else Path(d) / "w.xlsx"
        wiki_suite.render_xlsx(tcs, "t", out, concepts=_concepts(), manifest={},
                               doubt_summaries=summaries)
        return load_workbook(out), out.read_bytes()


def _sheet_rows(wb):
    return [[c.value for c in row] for row in wb["Doubts"].iter_rows()]


def test_sheet_sits_after_the_last_c_tc_sheet_and_is_in_the_toc():
    tcs = [_tc(1, {"data": "Low"}, "Main flow"), _tc(2, {"data": "Low"}, "Variant")]
    tcs += [_tc(3, {"data": "Low"}, "Variant")]
    _t, sums = _fixture()
    wb, _ = _render(tcs, sums)
    names = wb.sheetnames
    last = max(i for i, n in enumerate(names) if n.startswith("C-TC"))
    assert names[last + 1] == "Doubts" and names[last + 2] == "Test Statistics", names
    toc = [wb["A - Table of Contents"].cell(row=r, column=1).value for r in range(23, 32)]
    assert "Doubts" in toc, toc


def test_header_row_has_the_ten_titles_in_order():
    tcs, sums = _fixture()
    wb, _ = _render(tcs, sums)
    assert _sheet_rows(wb)[0] == HEADERS, _sheet_rows(wb)[0]


def test_first_row_is_the_question_with_most_selected_test_cases():
    tcs, sums = _fixture()
    rows = _sheet_rows(_render(tcs, sums)[0])
    # Q-X-01 hits TC 1 and 2 (2 test cases); Q-X-02 hits TC 3 and 2 (2): tie,
    # Low count 1 vs 2 -> Q-X-01 first. Q-X-03 only on an unselected case.
    assert [r[0] for r in rows[1:]] == ["Q-X-01", "Q-X-02", "-"], rows
    assert rows[1][3] == 2 and rows[1][4] == "Low"


def test_tie_breaks_by_low_count_then_id():
    tcs = [_tc(1), _tc(2), _tc(3)]
    a = _q("Q-X-05", [_mem(1, "data", "Medium"), _mem(2, "data", "Medium")])
    b = _q("Q-X-04", [_mem(1, "steps", "Medium"), _mem(2, "steps", "Medium")])
    c = _q("Q-X-06", [_mem(1, "expected"), _mem(2, "expected")])
    rows = wiki_suite._doubt_sheet_rows(tcs, [_summary([a, b, c])])
    assert [r["id"] for r in rows] == ["Q-X-06", "Q-X-04", "Q-X-05"], rows


def test_unselected_members_are_neither_listed_nor_counted():
    tcs = [_tc(1)]
    q = _q("Q-X-01", [_mem(1, "data"), _mem(9, "data")])
    rows = wiki_suite._doubt_sheet_rows(tcs, [_summary([q])])
    assert len(rows) == 1 and rows[0]["tcs"] == 1
    assert rows[0]["affected"] == ["TC-1.1-AC01-01 / Field / Values"], rows
    gone = wiki_suite._doubt_sheet_rows(tcs, [_summary([_q("Q-X-03", [_mem(9, "data")])])])
    assert gone == []


def test_ungrouped_follow_questions_with_dash_and_status():
    tcs, sums = _fixture()
    rows = _sheet_rows(_render(tcs, sums)[0])
    last = rows[-1]
    assert last[0] == "-" and last[2] == "ungrouped", last
    assert last[1] == "Inferred: steps 3." and last[3] == 1
    assert last[5] == "TC-1.1-AC01-03 / Test Steps", last


def test_affected_lines_and_answer_column():
    tcs = [_tc(1), _tc(2)]
    q = _q("Q-X-01", [_mem(1, "data", "Low", "closed", "R-X-01"),
                      _mem(2, "expected", "Medium", "answered", "R-X-02")])
    row = wiki_suite._doubt_sheet_rows(tcs, [_summary([q])])[0]
    assert row["affected"] == ["TC-1.1-AC01-01 / Field / Values",
                               "TC-1.1-AC01-02 / Expected Results"], row
    assert row["answer"] == "R-X-01, R-X-02", row
    assert row["lowest"] == "Medium", row


def test_invalid_register_makes_every_doubt_ungrouped():
    tcs = [_tc(1)]
    q = _q("Q-X-01", [_mem(1, "data")])
    rows = wiki_suite._doubt_sheet_rows(tcs, [_summary([q], errors=["bad"])])
    assert [(r["id"], r["status"]) for r in rows] == [("-", "ungrouped")], rows
    assert wiki_suite._question_map([_summary([q], errors=["bad"])]) == {}


def test_remarks_carry_the_question_id_after_the_level():
    tcs, sums = _fixture()
    wb, _ = _render(tcs, sums)
    ws = wb[[n for n in wb.sheetnames if n.startswith("C-TC")][0]]
    cells = {}
    for row in ws.iter_rows():
        if str(row[0].value).startswith("TC-"):
            cells[row[0].value] = str(row[6].value)
    one = cells["TC-1.1-AC01-01"]
    assert "Field / Values**: Low [Q-X-01] - Inferred: data 1." in one or \
        "Field / Values: Low [Q-X-01] - Inferred: data 1." in one, one
    assert "Scenario" in one and "High [" not in one, one
    three = cells["TC-1.1-AC01-03"]
    assert "Medium - Inferred: steps 3." in three and "[Q-" in three, three
    assert "Test Steps: Medium [" not in three.replace("**", ""), three
    assert "[Q-" not in cells["TC-1.1-AC01-04"]


def test_no_summaries_means_no_sheet_and_untagged_remarks():
    tcs, _ = _fixture()
    for none in (None, []):
        wb, _b = _render(tcs, none)
        assert "Doubts" not in wb.sheetnames
        toc = [wb["A - Table of Contents"].cell(row=r, column=1).value
               for r in range(23, 32)]
        assert "Doubts" not in toc
        ws = wb[[n for n in wb.sheetnames if n.startswith("C-TC")][0]]
        assert not any("[Q-" in str(c.value) for row in ws.iter_rows() for c in row)
    fm = tcs[0][1]
    assert wiki_suite._confidence_remarks(fm) == wiki_suite._confidence_remarks(fm, None)
    assert "[" not in wiki_suite._confidence_remarks(fm)


def test_two_renders_are_identical():
    # openpyxl stamps docProps/core.xml `modified` with the save time whatever
    # the workbook properties say (true without the doubts sheet too), so the
    # zip is compared member by member without that one file, plus every cell.
    import io
    import zipfile
    tcs, sums = _fixture()
    wb1, b1 = _render(tcs, sums)
    wb2, b2 = _render(tcs, sums)
    z1, z2 = zipfile.ZipFile(io.BytesIO(b1)), zipfile.ZipFile(io.BytesIO(b2))
    assert z1.namelist() == z2.namelist()
    for n in z1.namelist():
        if n != "docProps/core.xml":
            assert z1.read(n) == z2.read(n), n
    assert wb1.sheetnames == wb2.sheetnames
    for n in wb1.sheetnames:
        assert ([[c.value for c in r] for r in wb1[n].iter_rows()]
                == [[c.value for c in r] for r in wb2[n].iter_rows()]), n


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
    print("test_wiki_suite_doubts " + ("FAILED" if failed else "OK"))
    sys.exit(1 if failed else 0)
