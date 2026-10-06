#!/usr/bin/env python3
"""In-process read model for the test case review grid (GET /api/testcases).

Pure: imports and reads, never writes. Every cell comes from the workbook
export's own functions (wiki_suite.plan_sheets / sheet_common / tc_cells /
split_expected), so the grid and the exported sheet cannot diverge. The text
an editor opens with is the SPEC's text, resolved through
wiki_tcedit.spec_index - the same lookup `wiki tc edit` writes through.
"""
import copy
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import wiki
import wiki_doubts
import wiki_suite
import render_sit
import render_uat
import wiki_tcedit
from wiki import body_section, load_all, resolve_ref

LEVELS = ("sit", "uat")


def _stem(ref):
    return Path(resolve_ref(ref)[0]).name if ref else None


def _story_of(fm):
    for ref in fm.get("covers") or []:
        rel = resolve_ref(ref)[0]
        if rel.startswith("stories/"):
            return Path(rel).name
    return None


def _group_of(level, fm, concepts):
    """(key, label, kind) - the workbook's grouping: a run is a sheet; a test
    case with no run groups per flow (UAT) or per module."""
    if fm.get("run"):
        return f"run:{level}:{fm['run']}", fm["run"], "run"
    kind = "flow" if fm.get("flow") else "module"
    rel = resolve_ref(fm.get(kind) or "unassigned")[0]
    title = ((concepts.get(rel) or ({},))[0] or {}).get("title")
    return f"{kind}:{level}:{rel}", wiki_suite._plain(title or Path(rel).name), kind


def _doubts():
    """(question map for the AI Remarks cell, {doubt id: doubt}) - the same
    summaries `suite compile` hands to the workbook."""
    rows = wiki_doubts.collect_all()
    ctx = (rows, wiki_doubts._resolutions(wiki.ROOT), wiki_doubts._manifest(wiki.ROOT))
    summaries = [wiki_doubts.story_summary(s, _ctx=ctx)
                 for s in wiki_doubts.stories_with_doubts(_rows=rows)]
    by_id = {d["doubt"]: d for s in summaries for d in s.get("doubts") or []}
    return wiki_suite._question_map(summaries), by_id


def _parts(fm, doubts):
    out = {}
    parts = fm.get("confidence_parts") if isinstance(fm.get("confidence_parts"), dict) else {}
    for key, _label in wiki_suite.CONF_PARTS:
        p = parts.get(key) or {}
        d = doubts.get(f"{fm.get('scenario_id')}#{key}") or {}
        out[key] = {"level": p.get("level"),
                    # set only on a part a human confirmation lifted: the
                    # level it returns to if its text is reworded
                    "authored": p.get("authored"),
                    "remark": str(p.get("remark") or "").strip(),
                    "state": d.get("state"), "question": d.get("question"),
                    "resolution": d.get("resolution")}
    return out


def row_prds(fm):
    """The PRD ids a test case draws on, sorted - the keys of its
    generated_from.prd_versions. [] when it draws on none. Read from the test
    case's own frontmatter, a file the cache signature already covers."""
    return sorted(wiki_suite.tc_prds(fm))


def _row(level, rel, fm, body, concepts, common, qmap, doubts, index):
    cells = wiki_suite.tc_cells(fm, body, concepts, common, qmap)
    own, block = wiki_suite.split_expected(cells["expected"])
    hit = wiki_tcedit.resolve(fm, index)
    entry = hit[3] if hit else {}

    def src(field, rendered):
        """The spec's text when a spec entry renders this test case (it is
        what an edit replaces), else what the rendered file shows."""
        v = entry.get(field)
        return v if isinstance(v, str) else (rendered or "")

    def blank(v):
        """The export shows a `-` placeholder as an empty cell."""
        return "" if (v or "").strip() in wiki_suite.BLANK_DATA else v

    key, _label, _kind = _group_of(level, fm, concepts)
    spec = None
    if hit:
        try:
            spec = hit[1].resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            spec = hit[1].as_posix()
    return {
        "ref": rel, "id": fm["id"], "display_id": cells["id"], "level": level,
        "story": _story_of(fm), "flow": _stem(fm.get("flow")),
        "module": _stem(fm.get("module")), "run": fm.get("run"),
        "section": fm.get("section"), "order": fm.get("order"),
        "group": key, "status": fm.get("status"),
        "priority": src("priority", fm.get("priority")),
        "technique": fm.get("technique"), "covers": list(fm.get("covers") or []),
        "prds": row_prds(fm),
        "title": src("title", fm.get("title")),
        "objective": src("objective", body_section(body, "Objective")),
        "scenario": cells["scenario"], "chain": "\n".join(cells["chain"]),
        "steps": src("steps", body_section(body, "Steps")),
        "data": blank(src("data", body_section(body, "Test Data"))),
        "expected": src("expected", own), "element_block": block,
        "pre_extra": (entry.get("pre_extra") or "") if hit and level == "sit"
        else "\n".join(cells["extra"]),
        "post": src("post", body_section(body, "Postconditions")),
        "confidence": cells["confidence"], "parts": _parts(fm, doubts),
        "part_fields": {part: list(wiki_doubts.PART_TEXT[(level, part)])
                        for part, _l in wiki_suite.CONF_PARTS},
        "cells": {k: cells[k] for k in
                  ("scenario", "steps", "data", "expected", "remarks")},
        "editable": wiki_tcedit.editable_fields(fm, index), "spec": spec,
    }


# ------------------------------------------------------------------ cache
# One cached payload, keyed on the (relative path, mtime_ns, size) of every
# file the build reads. Computing the key only scans directories and stats;
# no file is opened. The cached payload is never handed out: callers get a
# deep copy, so mutating a result cannot corrupt the next one.
# Stored as ONE immutable tuple (sig, payload) replaced in a single assignment,
# so a reader never sees a new signature with an old or missing payload.
_CACHE = None
_LOCK = threading.Lock()


def _scan(base, suffix):
    """Yield (DirEntry, stat) for every file under `base` ending in `suffix`
    (recursive, stat-only). An entry or directory that vanishes mid-walk (a
    `tc edit` rendering or rolling back) is skipped."""
    stack = [str(base)]
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.name.endswith(suffix):
                            yield e, e.stat()
                    except OSError:
                        continue
        except OSError:
            continue


def _signature(root=None):
    """Everything the build reads: concept and test case files (wiki.load_all),
    the SIT and UAT spec YAMLs (wiki_tcedit.spec_index and
    wiki_doubts.collect_all), the doubt registers, resolutions (part of the
    concept dirs), manifest.json and config.yaml."""
    root = Path(wiki.ROOT if root is None else root).resolve()
    sources = [(root / d, ".md") for d in wiki.CONCEPT_DIRS + ["testcases", "changereports"]]
    sources += [(Path(render_sit.SPEC_DIR), ".yaml"), (Path(render_uat.SPEC_DIR), ".yaml"),
                (root / "tools" / "sit_specs", ".yaml"),
                (root / "tools" / "uat_specs", ".yaml"),
                (root / wiki_doubts.REGISTER_DIR, ".yaml")]
    seen = {}
    for base, suffix in sources:
        base = base.resolve()
        try:
            prefix = base.relative_to(root).as_posix()
        except ValueError:
            prefix = None
        for e, st in _scan(base, suffix):
            if prefix is None:
                rel = Path(e.path).as_posix()
            else:
                rel = os.path.relpath(e.path, root).replace(os.sep, "/")
            seen[rel] = (rel, st.st_mtime_ns, st.st_size)
    for name in ("manifest.json", "config.yaml"):
        try:
            st = (root / name).stat()
            seen[name] = (name, st.st_mtime_ns, st.st_size)
        except OSError:
            seen[name] = (name, None, None)
    return tuple(sorted(seen.values()))


def testcases():
    """{rows, groups} for the grid. Rebuilt only when an input file changed,
    and built once when several callers miss together; the caller always gets
    its own copy."""
    global _CACHE
    sig = _signature()
    cached = _CACHE
    if cached is None or cached[0] != sig:
        with _LOCK:
            cached = _CACHE
            if cached is None or cached[0] != sig:
                cached = (sig, _build())
                _CACHE = cached
    return copy.deepcopy(cached[1])


def _build():
    """{rows, groups}: every Test Case concept, in workbook order
    (SIT then UAT, each sorted by wiki_suite.tc_sort_key)."""
    concepts, _manifest = load_all()
    index = wiki_tcedit.spec_index()
    qmap, doubts = _doubts()
    rows, groups, seen = [], [], {}
    for level in LEVELS:
        tcs = sorted(((rel, fm, body) for rel, (fm, body, _p) in concepts.items()
                      if fm and fm.get("type") == "Test Case"
                      and fm.get("kind") == level),
                     key=lambda t: wiki_suite.tc_sort_key(t[1]))
        # The export selects ACTIVE test cases, so a sheet's shared
        # pre-condition block is computed over those; a stale or retired row
        # borrows the block of the group it would sit in.
        common_of, common_by_group = {}, {}
        active = [t for t in tcs if t[1].get("status") == "active"]
        for _name, _mod, subs, _dash in wiki_suite.plan_sheets(active, concepts):
            sheet = [tc for _s, _f, tcl in subs for tc in tcl]
            common = wiki_suite.sheet_common(sheet)
            for rel, fm, _b in sheet:
                common_of[rel] = common
                common_by_group[_group_of(level, fm, concepts)[0]] = common
        for rel, fm, body in tcs:
            key, label, kind = _group_of(level, fm, concepts)
            common = common_of.get(rel, common_by_group.get(key, []))
            rows.append(_row(level, rel, fm, body, concepts, common, qmap,
                             doubts, index))
            if key not in seen:
                seen[key] = {"key": key, "label": label, "kind": kind,
                             "level": level, "sections": [],
                             "common": list(common_by_group.get(key, []))}
                groups.append(seen[key])
            sec = fm.get("section")
            if sec and sec not in seen[key]["sections"]:
                seen[key]["sections"].append(sec)
    return {"rows": rows, "groups": groups}
