#!/usr/bin/env python3
"""Public-base scrub sweep (plain-assert, run: py tools/test_public_base.py).

`master` must stay publishable to a PUBLIC GitHub repo: no organisation,
project, customer, person or internal-endpoint identifier anywhere in the
tracked tree, and no personal email address outside the fixed
`tc-agent@internal` identity. This is the acceptance test for the
public-base scrub (.superpowers/scrub-brief.md section D) kept live so a
later change can't reintroduce what the scrub removed.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {"node_modules", "build", ".git", ".superpowers"}

# Same literal set as the acceptance sweep in .superpowers/scrub-brief.md
# section D, plus a fix-round addition (independent wider-token sweep found
# leftovers the brief didn't name: a project acronym, a pilot story id, a
# local workspace path/username/location) -- built by concatenation so this
# file's own source never contains a banned string contiguously (this file
# is itself swept: the acceptance grep in section D does not exclude
# tools/, only node_modules / build / .git / .superpowers). A handful of
# short tokens from that same list are checked separately below with a
# word boundary -- they can legitimately occur inside unrelated words
# (grep -E without \b would false-positive on those), and for the same
# self-sweep reason their own labels are built by concatenation too,
# everywhere they are printed.
BANNED_LITERAL = ["R" + "SN", "SEN" + "SE", "DS" + "HM", "MIN" + "DEF",
                  "sya" + "bil", "sun" + "shine", "Sun" + "shine",
                  "qw" + "en", "ssc-" + "chat", "WR" + "M",
                  "Workshop " + "Resource", "Production " + "Monitoring",
                  "P101" + "0E", "app" + "llm",
                  "TC" + "N", "HUM" + "S", "1.1.2.2" + ".4",
                  "sunny-" + "playground", "P136" + "2286",
                  "Singa" + "pore"]
# Word-boundary-checked tokens (label, regex) -- see the comment above.
_WB_TOKENS = [("NC" + "S"), ("LR" + "U"), ("NS" + "N"), ("Na" + "vy"),
              ("ARM" + "Y")]
_WB_RES = [(label, re.compile(r"\b" + label + r"\b")) for label in _WB_TOKENS]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")
# tc-agent@internal is the platform's own auto-commit identity (config.yaml
# provenance.agent_git_email) -- not a personal address, and has no dotted
# TLD so EMAIL_RE would not even match it. Kept explicit for clarity.
ALLOWED_EMAILS = {"tc-agent@internal"}


def _walk_files():
    """Every TRACKED file, as `git ls-files` reports it. What would be
    published is exactly the tracked tree; ignored and untracked content
    (build/, node_modules/, other worktrees under .claude/worktrees/ that
    legitimately hold project content, a worktree's `.git` pointer file) is
    never pushed, so sweeping it would only produce false positives. Falls
    back to an os.walk with the same intent when git is unavailable."""
    import subprocess
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        for rel in out.decode("utf-8").split("\0"):
            if rel:
                yield ROOT / rel
        return
    except (OSError, subprocess.CalledProcessError):
        pass
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_DIRS and d != "worktrees"]
        for fn in filenames:
            if fn == ".git" and Path(dirpath) == ROOT:
                continue
            yield Path(dirpath) / fn


def _read_text(p):
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None      # binary or unreadable -- grep -I would skip it too


def test_no_banned_strings():
    hits = []
    for p in _walk_files():
        text = _read_text(p)
        if text is None:
            continue
        rel = p.relative_to(ROOT).as_posix()
        for word in BANNED_LITERAL:
            if word in text:
                hits.append(f"{rel}: {word!r}")
        for label, rx in _WB_RES:
            if rx.search(text):
                hits.append(f"{rel}: {label} (word-boundary)")
    assert not hits, "banned strings found:\n" + "\n".join(hits)


def test_no_personal_emails():
    hits = []
    for p in _walk_files():
        text = _read_text(p)
        if text is None:
            continue
        rel = p.relative_to(ROOT).as_posix()
        for m in EMAIL_RE.finditer(text):
            addr = m.group(0)
            if addr not in ALLOWED_EMAILS:
                hits.append(f"{rel}: {addr}")
    assert not hits, "personal-looking email addresses found:\n" + "\n".join(hits)


def _iter_cells(path):
    import openpyxl
    wb = openpyxl.load_workbook(path)   # default: rich text flattens to plain
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    yield ws.title, cell.coordinate, str(cell.value)


def test_reference_workbooks_clean():
    """The two tracked reference workbooks must contain none of the banned
    strings in any cell of any sheet. `grep -I` (section D) skips binaries,
    so this openpyxl walk is the only thing that can see inside .xlsx."""
    hits = []
    for name in ("reference-format-sit.xlsx", "reference-format.xlsx"):
        path = ROOT / "tools" / name
        assert path.exists(), f"missing {path}"
        for sheet, coord, text in _iter_cells(path):
            for word in BANNED_LITERAL:
                if word in text:
                    hits.append(f"{name}!{sheet}!{coord}: {word!r}")
            for label, rx in _WB_RES:
                if rx.search(text):
                    hits.append(f"{name}!{sheet}!{coord}: {label} (word-boundary)")
    assert not hits, "banned strings found in reference workbooks:\n" + "\n".join(hits)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"[PASS] {name}")
            except Exception as e:
                fails += 1
                print(f"[FAIL] {name}: {e}")
    sys.exit(1 if fails else 0)
