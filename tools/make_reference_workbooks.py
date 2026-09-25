#!/usr/bin/env python3
"""Regenerate the two tracked reference-format workbooks (run: py
tools/make_reference_workbooks.py; add --check to only verify, not write).

These are layout references, not project content: `tools/reference-format-
sit.xlsx` is the current 5-sheet SIT export layout `wiki_suite.render_xlsx`
produces (reusing its `_styles`, `TC_COLS`, `COL_W`, `TC_HEADER_ROW`,
`STATS_FIRST_ID_ROW`, `_fill_toc`, `_fill_refs`, `_fill_stats` and
`_fill_change_log` so the two never drift apart); `tools/reference-
format.xlsx` is the older single-sheet manual-TC convention `config.yaml`'s
`ids.tc_format` comment points at. All header values, ids and test-case text
below are invented and generic -- deliberately no organisation, project,
customer, person or internal-endpoint identifier (this script is exercised
by the public-base sweep, tools/test_public_base.py::test_reference_
workbooks_clean, and by --check here).

Deterministic like `wiki_suite.render_xlsx`: pinned `creator` / `created` /
`modified` doc properties mean identical inputs produce a byte-identical
file, so re-running this script with no code change is a no-op diff.
openpyxl's own `save_workbook()` unconditionally re-stamps `modified` to
`datetime.now()` after we set it (and `ZipFile.writestr` timestamps every
entry with the current second), which would otherwise make every run of this
script -- and of `wiki_suite.render_xlsx` -- diff on every run regardless of
content; `_freeze_zip` below rewrites the saved archive so the pin holds.
"""
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wiki_suite import (COL_W, TC_COLS, TC_HEADER_ROW, _fill_change_log,
                        _fill_refs, _fill_stats, _fill_toc, _richify, _styles)

SIT_PATH = ROOT / "tools/reference-format-sit.xlsx"
LEGACY_PATH = ROOT / "tools/reference-format.xlsx"

PINNED_DATE = datetime(2026, 1, 1)
_ZIP_DATE_TIME = (2026, 1, 1, 0, 0, 0)


def _freeze_zip(path):
    """Rewrite the just-saved xlsx so it is byte-identical on every re-run:
    pin docProps/core.xml's <dcterms:modified> (openpyxl.writer.excel.
    save_workbook stamps it with datetime.now() right before writing,
    clobbering wb.properties.modified) and every zip entry's date_time
    (ZipFile.writestr defaults to the current local time)."""
    stamp = PINNED_DATE.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as zin:
        names = zin.namelist()
        infos = [zin.getinfo(n) for n in names]
        data = {n: zin.read(n) for n in names}
    core = data["docProps/core.xml"].decode("utf-8")
    core = re.sub(r"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                  rf"\g<1>{stamp}\g<2>", core)
    data["docProps/core.xml"] = core.encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            info.date_time = _ZIP_DATE_TIME
            zout.writestr(info, data[info.filename])

# ------------------------------------------------------------- example data
# A generic sign-in form: invented, not derived from any real screen.

EXP = dict(project_code="EXP-0001", project_name="Example Project",
           system_name="Example System", module_prefix="EXM",
           roles="Viewer, Reviewer, Approver", prepared_by="tc-copilot")

TC_1 = dict(
    id="TC-1.2.3.4-AC01-01",
    scenario=("**Scenario:** User signs in with valid credentials.\n\n"
              "**Given:** The user is on the sign-in screen.\n\n"
              "**When:** They enter a valid username and password and "
              "select Sign In.\n\n"
              "**Then:** They land on the home screen."),
    steps=("1. Open the sign-in screen.\n"
           "2. Enter the username and password.\n"
           "3. Select Sign In."),
    data="Username = demo.user\nPassword = Passw0rd!",
    expected=("1. The home screen displays.\n"
              "2. The welcome banner shows the signed-in user's name."),
)

TC_2 = dict(
    id="TC-1.2.3.4-AC01-02",
    scenario=("**Scenario:** User signs in with an invalid password.\n\n"
              "**Given:** The user is on the sign-in screen.\n\n"
              "**When:** They enter a valid username with an incorrect "
              "password and select Sign In.\n\n"
              "**Then:** They see an error and stay on the sign-in screen."),
    steps=("1. Open the sign-in screen.\n"
           "2. Enter the username and an incorrect password.\n"
           "3. Select Sign In."),
    data="Username = demo.user\nPassword = wrongpass",
    expected=('1. An "Invalid username or password" error message displays.\n'
              "2. The user remains on the sign-in screen."),
)


# ------------------------------------------------------------ sit workbook

def _build_sit(path):
    from openpyxl import Workbook

    st = _styles()
    tc_sheet_name = "C-TC-1 (Example Module)"
    meta = dict(
        module_name=f"{EXP['module_prefix']} - Example Module",
        test_type="SIT",
        version="v0.1",
        date=date(2026, 1, 1).strftime("%d %b %Y"),
        prepared_date="01 Jan 2026",
        revision_summary="Reference layout generated by tools/make_reference_workbooks.py",
        tabs=[("A - Table of Contents", "Table of Contents"),
              ("B - Proj Doc References", "Project Document References"),
              (tc_sheet_name, "Test Case"),
              ("Test Statistics", "Test Statistics"),
              ("Change Log", "Change Log")],
        docs=[("PRD", "Example Project - PRD v1")],
    )

    wb = Workbook()
    wb.properties.creator = "tc-copilot"
    wb.properties.created = wb.properties.modified = PINNED_DATE

    _fill_toc(wb.active, EXP, meta, st)
    wb.active.title = "A - Table of Contents"

    _fill_refs(wb.create_sheet("B - Proj Doc References"), meta, st)

    ws = wb.create_sheet(tc_sheet_name)
    ws["B2"] = "AGILE TEST SPECIFICATIONS - Test Cases"
    ws["B2"].font = st["font"](bold=True, size=12)
    ws["C3"] = '=CONCATENATE("Total TC = ",COUNTIF(A:A,"TC-*")+COUNTIF(A:A,"BR-*"))'
    ws["C3"].font = st["font"](bold=True)
    for r, label in ((4, "Project Code / Name"), (5, "System/Subsystem/Module"),
                     (6, "Test Type / Version No.")):
        ws.cell(row=r, column=1, value=label).font = st["font"](bold=True)
    ws["B4"] = "=CONCATENATE('A - Table of Contents'!$C$3,\"/ \",'A - Table of Contents'!$C$4)"
    ws["B5"] = "=CONCATENATE('A - Table of Contents'!$C$5,\"/ \",'A - Table of Contents'!$C$6)"
    ws["B6"] = "=CONCATENATE('A - Table of Contents'!$C$7,\"/ \",'A - Table of Contents'!$C$8)"
    for coord in ("B4", "B5", "B6"):
        ws[coord].font = st["font"]()
    c = ws.cell(row=7, column=4, value=EXP["roles"])
    c.font, c.fill, c.alignment = st["font"](bold=True), st["hdr_fill"], st["center"]
    c = ws.cell(row=7, column=6, value="Update during Test Execution")
    c.font, c.fill, c.alignment = st["font"](bold=True), st["exec_fill"], st["center"]
    for col, h in enumerate(TC_COLS, 1):
        c = ws.cell(row=TC_HEADER_ROW, column=col, value=h)
        c.font, c.alignment, c.border = st["font"](bold=True), st["center"], st["border"]
        c.fill = st["hdr_fill"] if col <= 5 else st["exec_fill"]
    ws.row_dimensions[TC_HEADER_ROW].height = 38
    for col, w in COL_W.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = f"A{TC_HEADER_ROW + 1}"

    r = TC_HEADER_ROW + 1
    ws.cell(row=r, column=1, value="Example Module - §1 (1.2.3.4)").font = st["blue"]
    r += 1
    ws.cell(row=r, column=1, value="<Pre-condition>").font = st["blue"]
    r += 1
    ws.cell(row=r, column=1, value="1. The user has an active account.").font = st["blue"]
    r += 1
    sub_title = "Sign In"
    for col in range(1, 13):
        c = ws.cell(row=r, column=col)
        c.fill, c.border = st["sect_fill"], st["border"]
    ws.cell(row=r, column=1, value=sub_title).font = st["font"](bold=True)
    ws.row_dimensions[r].height = 21
    r += 1
    for tc in (TC_1, TC_2):
        vals = (tc["id"], tc["scenario"], tc["steps"], tc["data"], tc["expected"])
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=_richify(v))
            c.font, c.alignment, c.border = st["font"](), st["top"], st["border"]
        for col in range(6, 13):
            ws.cell(row=r, column=col).border = st["border"]
        ws.row_dimensions[r].height = 80
        r += 1

    dashboards = [("Sign In", tc_sheet_name, [TC_1["id"], TC_2["id"]])]
    _fill_stats(wb.create_sheet("Test Statistics"), dashboards, st)
    _fill_change_log(wb.create_sheet("Change Log"), st, [])

    wb.save(path)
    _freeze_zip(path)


# --------------------------------------------------------- legacy workbook

def _build_legacy(path):
    from openpyxl import Workbook

    st = _styles()
    wb = Workbook()
    wb.properties.creator = "tc-copilot"
    wb.properties.created = wb.properties.modified = PINNED_DATE

    ws = wb.active
    ws.title = "TestCases"
    headers = ("Test Case ID", "Scenario", "Test Steps", "Field/Values",
              "Expected Results")
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font, c.fill, c.border = st["font"](bold=True), st["hdr_fill"], st["border"]
    widths = (22, 50, 40, 30, 50)
    for col, w in zip("ABCDE", widths):
        ws.column_dimensions[col].width = w

    r = 2
    for col in range(1, 6):
        c = ws.cell(row=r, column=col)
        c.fill, c.border = st["sect_fill"], st["border"]
    ws.cell(row=r, column=1, value="Sign In Screen").font = st["font"](bold=True)
    r += 1
    for col in range(1, 6):
        c = ws.cell(row=r, column=col)
        c.fill, c.border = st["sect_fill"], st["border"]
    ws.cell(row=r, column=1, value="Sign In Drawer").font = st["font"](bold=True)
    r += 1

    rows = [
        ("1.2.3.4-AC1-01", "User signs in with valid credentials.",
         "1. Open the sign-in screen.\n2. Enter valid credentials.\n"
         "3. Select Sign In.",
         "Username = demo.user\nPassword = Passw0rd!",
         "1. The home screen displays.\n2. The welcome banner shows the "
         "user's name."),
        ("1.2.3.4-AC1-02", "User signs in with an invalid password.",
         "1. Open the sign-in screen.\n2. Enter an incorrect password.\n"
         "3. Select Sign In.",
         "Username = demo.user\nPassword = wrongpass",
         '1. An "Invalid username or password" error message displays.\n'
         "2. The user remains on the sign-in screen."),
    ]
    for vals in rows:
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=v)
            c.font, c.alignment, c.border = st["font"](), st["top"], st["border"]
        ws.row_dimensions[r].height = 60
        r += 1

    wb.save(path)
    _freeze_zip(path)


BANNED_MODULE = None


def _load_banned():
    global BANNED_MODULE
    if BANNED_MODULE is None:
        import test_public_base as tpb
        BANNED_MODULE = tpb
    return BANNED_MODULE


def check():
    """Assert neither workbook contains a banned string (public-base scrub
    acceptance test, .superpowers/scrub-brief.md section A/D)."""
    tpb = _load_banned()
    hits = []
    for name in ("reference-format-sit.xlsx", "reference-format.xlsx"):
        path = ROOT / "tools" / name
        for sheet, coord, text in tpb._iter_cells(path):
            for word in tpb.BANNED_LITERAL:
                if word in text:
                    hits.append(f"{name}!{sheet}!{coord}: {word!r}")
            for label, rx in tpb._WB_RES:
                if rx.search(text):
                    hits.append(f"{name}!{sheet}!{coord}: {label} (word-boundary)")
    if hits:
        sys.exit("make_reference_workbooks --check: banned strings found:\n"
                  + "\n".join(hits))
    print("make_reference_workbooks --check: clean")


def main():
    if "--check" in sys.argv[1:]:
        check()
        return
    _build_sit(SIT_PATH)
    _build_legacy(LEGACY_PATH)
    print(f"wrote {SIT_PATH.relative_to(ROOT).as_posix()}")
    print(f"wrote {LEGACY_PATH.relative_to(ROOT).as_posix()}")
    check()


if __name__ == "__main__":
    main()
