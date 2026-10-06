#!/usr/bin/env python3
"""Read model for the Workbook view: one compiled .xlsx drawn as JSON.

The app shows a workbook exactly as testers receive it, so this module reads
the FILE (openpyxl, rich text on) rather than re-deriving the sheet from the
wiki. Three things are layered on top of the parse:

  - formulas: a file never opened in Excel holds no cached values, so the
    functions tools/wiki_suite.py emits are evaluated here;
  - test case rows: a `TC-<id>` cell in column A of a C-TC sheet is mapped back
    to the test case's ref;
  - freshness: the sidecar written at compile time records each test case's
    sealed hash, compared here with the manifest's current one.

Pure: no writes, no commits. The parse is cached by path and mtime.
"""
import json
import re
import sys
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import load_all
from wiki_suite import TC_HEADER_ROW, _display_id

INVENTORY_DIR = ROOT / "build/inventory"
SUITES_DIR = ROOT / "suites"
STORIES_DIR = ROOT / "stories"
KINDS = ("sit", "uat", "osat", "mixed")
DEFAULT_COL_WIDTH = 8.43          # Excel's width for a column the file leaves unset
DEFAULT_FONT_SIZES = (10, 11)     # the exporter's Arial 10 and openpyxl's default 11

# <name>-latest.xlsx or <name>_<YYYYMMDD-HHMMSS>.xlsx (wiki_suite.inventory_paths)
_FILE_RE = re.compile(r"^(?P<name>.+?)(?:-latest|_(?P<ts>\d{8}-\d{6}))\.xlsx$")
# `wiki export` names default to <STORY>-sit, so the story can be recovered.
_STORY_IN_NAME = re.compile(r"^([A-Z0-9][A-Z0-9-]*?)-(?:sit|uat|osat)$")
_TC_ID_RE = re.compile(r"^(?:TC|BR)-\S+$")
_QUESTION_ID_RE = re.compile(r"^Q-\S+$")


class WorkbookNotFound(LookupError):
    """No such .xlsx under build/inventory/<kind>/ (or the path escapes it)."""


class WorkbookUnreadable(ValueError):
    """The file exists but openpyxl cannot read it (half-written, corrupt)."""


def _resolve(kind, file):
    """Same rule as /api/download: resolve first, then require an existing
    .xlsx inside build/inventory/ - here exactly at <kind>/<file>."""
    base = INVENTORY_DIR.resolve()
    if kind not in KINDS:
        raise WorkbookNotFound(f"{kind}/{file}")
    target = (base / str(kind) / str(file)).resolve()
    if (not target.is_relative_to(base)
            or target.parent.parent != base
            or not target.is_file()
            or target.suffix != ".xlsx"):
        raise WorkbookNotFound(f"{kind}/{file}")
    return target


# ------------------------------------------------------------------ formulas
# What tools/wiki_suite.py emits, and nothing more:
#   CONCATENATE(...)            B/C-TC header blocks, "Total TC = "
#   COUNTIF(range, "text*")     Total TC, per-status counts
#   COUNTA(range)               Test Statistics "Total TCs"
#   VLOOKUP(key, range, n, FALSE)   Test Statistics status column
#   IFERROR(expr, fallback)     Test Statistics percentages
#   cell references, + - * /    Test Statistics roll-ups
# Anything else raises _Unresolved and the cell is returned as formula text.

class _Unresolved(Exception):
    """A formula this model does not evaluate."""


class _ExcelError(Exception):
    """An Excel error value (#DIV/0!, #N/A, #REF!, #VALUE!) - what IFERROR catches."""


_TOKEN = re.compile(r"""\s*(?:
      (?P<num>\d+(?:\.\d+)?)
    | "(?P<str>(?:[^"]|"")*)"
    | (?P<bool>TRUE|FALSE)(?![A-Za-z0-9_(])
    | (?P<ref>(?:'(?:[^']|'')+'!|[A-Za-z0-9_.]+!)?
        \$?[A-Za-z]{1,3}(?:\$?\d+)?(?::\$?[A-Za-z]{1,3}(?:\$?\d+)?)?)(?![A-Za-z0-9_(])
    | (?P<name>[A-Za-z][A-Za-z0-9.]*)(?=\s*\()
    | (?P<op>[-+*/(),])
)""", re.X)
_REF = re.compile(
    r"^(?:'(?P<q>(?:[^']|'')+)'!|(?P<b>[A-Za-z0-9_.]+)!)?"
    r"\$?(?P<c1>[A-Za-z]{1,3})\$?(?P<r1>\d+)?"
    r"(?::\$?(?P<c2>[A-Za-z]{1,3})\$?(?P<r2>\d+)?)?$")
_Range = namedtuple("_Range", "sheet r1 c1 r2 c2 single")


def _tokens(src):
    out, pos = [], 0
    while pos < len(src):
        if not src[pos:].strip():
            break
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise _Unresolved(src)
        out.append((m.lastgroup, m.group(m.lastgroup)))
        pos = m.end()
    return out


def _num(value):
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        raise _ExcelError("#VALUE!")


def _text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _same(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return _text(a).lower() == _text(b).lower()
    return a == b


def _matches(value, crit):
    """COUNTIF criterion: text with * and ? wildcards (case-insensitive), or a
    number. Comparison criteria ('>5') are not emitted and not evaluated."""
    if value is None or value == "":
        return False
    if isinstance(crit, str):
        if crit[:1] in "<>=":
            raise _Unresolved(crit)
        pat = "".join(".*" if ch == "*" else "." if ch == "?" else re.escape(ch)
                      for ch in crit)
        return re.fullmatch(pat, _text(value), re.I | re.S) is not None
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and value == crit)


class _Book:
    """Cell values of one loaded workbook, with formulas evaluated on demand."""

    def __init__(self, wb):
        self.grid, self.max_row = {}, {}
        for ws in wb.worksheets:
            self.grid[ws.title] = {
                (c.row, c.column): (c.value, c.data_type == "f")
                for row in ws.iter_rows() for c in row if c.value is not None}
            self.max_row[ws.title] = ws.max_row
        self.memo, self.active = {}, set()

    def value(self, sheet, row, col):
        key = (sheet, row, col)
        if key in self.memo:
            return self.memo[key]
        raw, is_formula = self.grid[sheet].get((row, col), (None, False))
        if is_formula:
            if key in self.active:
                raise _Unresolved("circular reference")
            self.active.add(key)
            try:
                val = _Parser(_tokens(str(raw)[1:]), self, sheet).parse()
            finally:
                self.active.discard(key)
        else:
            val = _plain_value(raw)
        self.memo[key] = val
        return val

    def range(self, text, sheet):
        from openpyxl.utils import column_index_from_string
        m = _REF.match(text)
        if not m:
            raise _Unresolved(text)
        title = (m.group("q") or "").replace("''", "'") or m.group("b") or sheet
        if title not in self.grid:
            raise _ExcelError("#REF!")
        c1 = column_index_from_string(m.group("c1").upper())
        r1 = int(m.group("r1")) if m.group("r1") else None
        if m.group("c2") is None:
            if r1 is None:
                raise _Unresolved(text)
            return _Range(title, r1, c1, r1, c1, True)
        c2 = column_index_from_string(m.group("c2").upper())
        r2 = int(m.group("r2")) if m.group("r2") else None
        if (r1 is None) != (r2 is None):
            raise _Unresolved(text)
        if r1 is None:                       # whole columns, e.g. A:A or $A:$N
            r1, r2 = 1, self.max_row[title]
        return _Range(title, r1, c1, min(r2, self.max_row[title]), c2, False)

    def values(self, rng):
        return [self.value(rng.sheet, r, c)
                for r in range(rng.r1, rng.r2 + 1)
                for c in range(rng.c1, rng.c2 + 1)]


class _Parser:
    def __init__(self, toks, book, sheet):
        self.toks, self.i, self.book, self.sheet = toks, 0, book, sheet

    def parse(self):
        val = self.expr()
        if self.i != len(self.toks):
            raise _Unresolved("trailing tokens")
        return val

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expr(self):
        left = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            right = self.term()
            left = _num(left) + _num(right) if op == "+" else _num(left) - _num(right)
        return left

    def term(self):
        left = self.factor()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            right = _num(self.factor())
            if op == "*":
                left = _num(left) * right
            elif right == 0:
                raise _ExcelError("#DIV/0!")
            else:
                left = _num(left) / right
        return left

    def factor(self):
        kind, val = self.take()
        if kind == "num":
            return float(val) if "." in val else int(val)
        if kind == "str":
            return val.replace('""', '"')
        if kind == "bool":
            return val == "TRUE"
        if kind == "ref":
            rng = self.book.range(val, self.sheet)
            if not rng.single:
                raise _Unresolved("a range used as a value")
            return self.book.value(rng.sheet, rng.r1, rng.c1)
        if kind == "name":
            return self.call(val.upper())
        if (kind, val) == ("op", "("):
            inner = self.expr()
            if self.take() != ("op", ")"):
                raise _Unresolved("unbalanced parenthesis")
            return inner
        if (kind, val) == ("op", "-"):
            return -_num(self.factor())
        raise _Unresolved(f"unexpected {val!r}")

    def call(self, name):
        """Split the arguments on top-level commas WITHOUT evaluating them, so
        IFERROR can evaluate its first argument and still fall back."""
        if self.take() != ("op", "("):
            raise _Unresolved(name)
        args, cur, depth = [], [], 0
        while True:
            tok = self.take()
            if tok == (None, None):
                raise _Unresolved("unbalanced parenthesis")
            if tok == ("op", "("):
                depth += 1
            elif tok == ("op", ")"):
                if depth == 0:
                    break
                depth -= 1
            elif tok == ("op", ",") and depth == 0:
                args.append(cur)
                cur = []
                continue
            cur.append(tok)
        args.append(cur)
        fn = _FUNCS.get(name)
        if fn is None:
            raise _Unresolved(name)
        return fn(self, args)

    def val(self, toks):
        return _Parser(toks, self.book, self.sheet).parse()

    def rng(self, toks):
        if len(toks) != 1 or toks[0][0] != "ref":
            raise _Unresolved("expected a range")
        return self.book.range(toks[0][1], self.sheet)


def _fn_concatenate(p, args):
    return "".join(_text(p.val(a)) for a in args)


def _fn_countif(p, args):
    if len(args) != 2:
        raise _Unresolved("COUNTIF")
    crit = p.val(args[1])
    return sum(1 for v in p.book.values(p.rng(args[0])) if _matches(v, crit))


def _fn_counta(p, args):
    return sum(1 for a in args for v in p.book.values(p.rng(a))
               if v is not None and v != "")


def _fn_vlookup(p, args):
    if len(args) != 4 or p.val(args[3]) is not False:
        raise _Unresolved("VLOOKUP without an exact-match FALSE")
    key, rng, idx = p.val(args[0]), p.rng(args[1]), int(_num(p.val(args[2])))
    for r in range(rng.r1, rng.r2 + 1):
        if _same(p.book.value(rng.sheet, r, rng.c1), key):
            return p.book.value(rng.sheet, r, rng.c1 + idx - 1)
    raise _ExcelError("#N/A")


def _fn_iferror(p, args):
    if len(args) != 2:
        raise _Unresolved("IFERROR")
    try:
        return p.val(args[0])
    except _ExcelError:
        return p.val(args[1])


_FUNCS = {"CONCATENATE": _fn_concatenate, "COUNTIF": _fn_countif,
          "COUNTA": _fn_counta, "VLOOKUP": _fn_vlookup, "IFERROR": _fn_iferror}


# ------------------------------------------------------------------ parse

def _plain_value(value):
    """A rich-text cell as its plain string; anything else unchanged."""
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    if isinstance(value, CellRichText):
        return "".join(p.text if isinstance(p, TextBlock) else str(p) for p in value)
    return value


def _fmt(value, number_format="General"):
    """A value as Excel displays it. A reference to an empty cell shows 0."""
    if value is None:
        return "0"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        if str(number_format).endswith("%"):
            m = re.search(r"\.(0+)%$", str(number_format))
            return f"{value * 100:.{len(m.group(1)) if m else 0}f}%"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
    return str(value)


def _hex(color):
    """'D9D9D9' for an explicit RGB colour; None for theme, indexed or unset."""
    if color is None or getattr(color, "type", None) != "rgb":
        return None
    rgb = color.rgb
    if not isinstance(rgb, str) or len(rgb) != 8 or rgb == "00000000":
        return None
    return rgb[2:].upper()


def _runs(value):
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    if value is None:
        return []
    if isinstance(value, CellRichText):
        return [{"text": p.text, "bold": bool(p.font and p.font.b)}
                if isinstance(p, TextBlock) else {"text": str(p), "bold": False}
                for p in value]
    return [{"text": _fmt(value), "bold": False}]


def _resolve_formula(c, book, title):
    """Display text of a formula cell, or None when it cannot be resolved."""
    try:
        return _fmt(book.value(title, c.row, c.column), c.number_format)
    except Exception:       # a display fallback: the cell shows its formula text
        return None


def _cell(c, book, title):
    from openpyxl.cell.cell import MergedCell
    if isinstance(c, MergedCell):        # covered by a merge: drawn by its anchor
        return {"runs": [], "fill": None, "bold": False, "align": None,
                "valign": None, "wrap": False, "border": False}
    out = {
        "runs": [],
        "fill": _hex(c.fill.fgColor) if c.fill.fill_type == "solid" else None,
        "bold": bool(c.font.b),
        "align": c.alignment.horizontal,
        "valign": c.alignment.vertical,
        "wrap": bool(c.alignment.wrap_text),
        "border": any(getattr(c.border, side).style
                      for side in ("left", "right", "top", "bottom")),
    }
    if c.data_type == "f":
        shown = _resolve_formula(c, book, title)
        if shown is None:           # drawn muted, "calculated in Excel"
            out["runs"] = [{"text": str(c.value), "bold": False}]
            out["formula"] = str(c.value)
        else:
            out["runs"] = [{"text": shown, "bold": False}]
    else:
        out["runs"] = _runs(c.value)
    if out["runs"]:
        color = _hex(c.font.color)
        if color:
            out["color"] = color
        if c.font.sz and c.font.sz not in DEFAULT_FONT_SIZES:
            out["size"] = c.font.sz
    return out


def _parse(path):
    """The file as JSON-safe sheets, plus where its ids sit:
    tc_rows [(sheet index, row, display id)], questions {id: {sheet, row}}."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, rich_text=True)
        return _read_sheets(wb)
    except Exception as e:      # BadZipFile, KeyError, InvalidFileException, OSError...
        raise WorkbookUnreadable(
            f"cannot read {path.name}: {_why(e)}") from e


def _why(e):
    """An error in words that are safe to show: for an OS error (a file Excel
    holds open) only its type and strerror, never the path it carries."""
    if isinstance(e, OSError):
        return f"{type(e).__name__}: {e.strerror or 'cannot be opened'}"
    return f"{type(e).__name__}: {e}"


def _read_sheets(wb):
    from openpyxl.utils import column_index_from_string
    from openpyxl.utils.cell import coordinate_to_tuple
    book = _Book(wb)
    sheets, tc_rows, questions = [], [], {}
    for si, ws in enumerate(wb.worksheets):
        max_row, max_col = ws.max_row, ws.max_column
        widths = {}
        for letter, dim in ws.column_dimensions.items():
            if dim.width is None:
                continue
            lo = dim.min or column_index_from_string(letter)
            for col in range(lo, min(dim.max or lo, max_col) + 1):
                widths[col] = dim.width
        rows = []
        for r, cells in enumerate(
                ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col), 1):
            height = ws.row_dimensions[r].height if r in ws.row_dimensions else None
            rows.append({"height": height, "tc": None,
                         "cells": [_cell(c, book, ws.title) for c in cells]})
            first = _plain_value(cells[0].value)
            if not isinstance(first, str):
                continue
            if (ws.title.startswith("C-TC") and r > TC_HEADER_ROW
                    and _TC_ID_RE.match(first)):
                tc_rows.append((si, r, first))
            elif ws.title == "AI Doubts" and r > 1 and _QUESTION_ID_RE.match(first):
                questions.setdefault(first, {"sheet": ws.title, "row": r})
        sheets.append({
            "name": ws.title,
            "cols": [widths.get(c, DEFAULT_COL_WIDTH) for c in range(1, max_col + 1)],
            "frozen_rows": (coordinate_to_tuple(ws.freeze_panes)[0] - 1
                            if ws.freeze_panes else 0),
            "merges": sorted([m.min_row, m.min_col, m.max_row, m.max_col]
                             for m in ws.merged_cells.ranges),
            "rows": rows,
        })
    return {"sheets": sheets, "tc_rows": tc_rows, "questions": questions}


_CACHE = {}     # str(path) -> (mtime_ns, parsed)


def _parsed(path):
    stamp = path.stat().st_mtime_ns
    hit = _CACHE.get(str(path))
    if hit and hit[0] == stamp:
        return hit[1]
    parsed = _parse(path)
    _CACHE[str(path)] = (stamp, parsed)
    return parsed


# ------------------------------------------------------------------ freshness

def _sidecar(path):
    """The compile-time record beside the workbook, or None when it is absent
    or not the shape wiki_suite.write_sidecar writes (a hand-damaged sidecar
    means 'freshness unknown', never a crash)."""
    try:
        doc = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(doc, dict)
            or not isinstance(doc.get("compiled_at"), str)
            or not isinstance(doc.get("source"), dict)
            or not isinstance(doc.get("tcs"), dict)
            or not all(h is None or isinstance(h, str)
                       for h in doc["tcs"].values())):
        return None
    return doc


def _infer_source(name):
    """Source of a workbook compiled before sidecars existed, from its name."""
    if (SUITES_DIR / f"{name}.yaml").is_file():
        return {"type": "suite", "name": name}
    m = _STORY_IN_NAME.match(name)
    if m and (STORIES_DIR / f"{m.group(1)}.md").is_file():
        return {"type": "export", "name": name, "story": m.group(1)}
    return None


def _tc_fm(concepts, ref):
    hit = concepts.get(ref)
    return hit[0] if hit and hit[0] else None


def _is_changed(ref, recorded, concepts, manifest):
    fm = _tc_fm(concepts, ref)
    return (fm is None or fm.get("status") != "active"
            or (manifest.get("tc_hashes") or {}).get(ref) != recorded)


def _map_rows(parsed, sidecar, concepts, manifest, kind):
    """[(sheet index, row, {ref, id, changed})] for every TC row that resolves.

    With a sidecar the candidates are exactly the test cases it lists, in
    compile order. SIT `1.1-AC01-01` and UAT `UAT-1.1-AC01-01` both display as
    `TC-1.1-AC01-01`, so a display id can name two refs in a mixed workbook:
    they are handed out in order, which is the order the sheets hold them.
    Without a sidecar the candidates are the wiki's test cases of this kind and
    a row maps only when its display id names exactly one of them."""
    if sidecar is not None:
        refs = list(sidecar["tcs"])
    else:
        refs = sorted(rel for rel, (fm, _b, _p) in concepts.items()
                      if fm and fm.get("type") == "Test Case"
                      and (kind == "mixed" or fm.get("kind") == kind))
    by_display = {}
    for ref in refs:
        fm = _tc_fm(concepts, ref)
        tid = fm["id"] if fm and fm.get("id") else ref.rsplit("/", 1)[-1]
        by_display.setdefault(_display_id({"id": tid}), []).append((ref, tid))
    rows_per_id = {}
    for _si, _r, display in parsed["tc_rows"]:
        rows_per_id[display] = rows_per_id.get(display, 0) + 1
    # Never guess. An id is linked only when its candidates and its rows agree
    # in number, and, if it names more than one ref, only when the sidecar
    # promises its refs are in sheet/row order (`tcs_order`; absent from a
    # sidecar written before that promise existed).
    ordered = sidecar is not None and sidecar.get("tcs_order") == "sheet"
    linkable = {d for d, cands in by_display.items()
                if len(cands) == rows_per_id.get(d, 0)
                and (len(cands) == 1 or ordered)}
    out = []
    for si, r, display in parsed["tc_rows"]:
        if display not in linkable:
            continue
        ref, tid = by_display[display].pop(0)
        changed = sidecar is not None and _is_changed(
            ref, sidecar["tcs"][ref], concepts, manifest)
        out.append((si, r, {"ref": ref, "id": tid, "changed": changed}))
    return out


def _compiled_at(path, sidecar):
    if sidecar and isinstance(sidecar.get("compiled_at"), str):
        return sidecar["compiled_at"]
    m = _FILE_RE.match(path.name)
    if m and m.group("ts"):
        try:
            return datetime.strptime(m.group("ts"), "%Y%m%d-%H%M%S") \
                .astimezone().isoformat(timespec="seconds")
        except (ValueError, OverflowError, OSError):
            pass                    # not a real time: use the file's own
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) \
        .astimezone().isoformat(timespec="seconds")


def _versions(path):
    """Every compile of this workbook name: -latest first, then newest first."""
    m = _FILE_RE.match(path.name)
    if not m:
        return [{"file": path.name, "compiled_at": _compiled_at(path, _sidecar(path))}]
    name = m.group("name")
    stamped = sorted((p for p in path.parent.glob("*.xlsx")
                      if (mm := _FILE_RE.match(p.name)) and mm.group("name") == name
                      and mm.group("ts") and not p.name.startswith("~$")),
                     key=lambda p: p.name, reverse=True)
    latest = path.parent / f"{name}-latest.xlsx"
    return [{"file": p.name, "compiled_at": _compiled_at(p, _sidecar(p))}
            for p in ([latest] if latest.is_file() else []) + stamped]


def _describe(path, kind, concepts, manifest):
    """(parsed, mapped rows, header fields) for one workbook file."""
    m = _FILE_RE.match(path.name)
    name = m.group("name") if m else path.stem
    parsed = _parsed(path)
    sidecar = _sidecar(path)
    mapped = _map_rows(parsed, sidecar, concepts, manifest, kind)
    changed = ([ref for ref, h in sidecar["tcs"].items()
                if _is_changed(ref, h, concepts, manifest)] if sidecar else [])
    source = sidecar.get("source") if sidecar else None
    return parsed, mapped, {
        "name": name, "file": path.name, "kind": kind,
        "compiled_at": _compiled_at(path, sidecar),
        "source": source if isinstance(source, dict) else _infer_source(name),
        "freshness": ("unknown" if sidecar is None
                      else "changed" if changed else "fresh"),
        "changed_count": len(changed),
        "versions": _versions(path),
    }


def workbook(kind, file):
    """One workbook as the Workbook page draws it. Raises WorkbookNotFound /
    WorkbookUnreadable."""
    path = _resolve(kind, file)
    concepts, manifest = load_all()
    parsed, mapped, head = _describe(path, kind, concepts, manifest)
    # The parse is cached and shared between requests: copy only the row lists
    # and the rows that gain a `tc`; cells are never mutated.
    sheets = [dict(s, rows=list(s["rows"])) for s in parsed["sheets"]]
    tcs = {}
    for si, r, tc in mapped:
        sheets[si]["rows"][r - 1] = dict(sheets[si]["rows"][r - 1], tc=tc)
    for si, r, display in parsed["tc_rows"]:
        tcs.setdefault(display, {"sheet": sheets[si]["name"], "row": r})
    return {**head, "sheets": sheets,
            "links": {"tcs": tcs, "questions": dict(parsed["questions"])}}


def workbooks():
    """The inventory, one entry per workbook name, newest compile first. Each
    entry describes that name's -latest file (or its newest timestamped file)
    and says where every test case sits in it: `tcs` {ref: {sheet, row}}.

    A file that cannot be read is never dropped without a word: the name
    falls back to its next newest compile, and every file passed over is
    listed in `skipped` [{kind, file, error}]."""
    concepts, manifest = load_all()
    groups = {}
    for kind in KINDS:
        folder = INVENTORY_DIR / kind
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.xlsx")):
            m = _FILE_RE.match(p.name)
            if not m or p.name.startswith("~$"):     # ~$: Excel's lock file
                continue
            groups.setdefault((kind, m.group("name")), []).append(p)
    out, skipped = [], []
    for (kind, name), paths in groups.items():
        # -latest first, then the timestamped compiles, newest first
        order = sorted(paths, key=lambda p: (p.name != f"{name}-latest.xlsx",
                                             [-ord(ch) for ch in p.name]))
        for path in order:
            try:
                parsed, mapped, head = _describe(path, kind, concepts, manifest)
                stamp = path.stat().st_mtime
            except Exception as e:       # one bad file never hides the others
                why = str(e) if isinstance(e, WorkbookUnreadable) \
                    else f"cannot read {path.name}: {_why(e)}"
                skipped.append({"kind": kind, "file": path.name, "error": why})
                continue
            names = [s["name"] for s in parsed["sheets"]]
            head["tcs"] = {tc["ref"]: {"sheet": names[si], "row": r}
                           for si, r, tc in mapped}
            out.append((stamp, head))
            break
    out.sort(key=lambda item: item[0], reverse=True)
    return {"workbooks": [head for _mt, head in out], "skipped": skipped}
