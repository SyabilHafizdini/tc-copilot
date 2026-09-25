#!/usr/bin/env python3
"""In-process read models for the operator app.

Reads are imports, not subprocesses: wiki_dashboard.gather() already computes
per-story status, TC counts, staleness causes, coverage stats and W4 drift,
and wiki_next.collect_next() computes the next action per scope. Reusing them
means the app can never disagree with `wiki dashboard` or `wiki next`.

Pure: no writes, no commits, no side effects.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki_dashboard import gather
from wiki_next import collect_next, pending_cards, phase_from_stories
from wiki import load_all
from wiki_suite import select

INVENTORY_DIR = ROOT / "build/inventory"

# Export names default to "<STORY>-<kind>" (wiki export), so the leading story
# id can be recovered from the filename; an arbitrary suite name yields None.
_STORY_IN_NAME = re.compile(r"^([A-Z0-9][A-Z0-9-]*?)-(?:sit|uat|osat)(?:[-_]|$)")
_VALID_KINDS = frozenset(("sit", "uat", "osat"))


def _inventory():
    """List every downloadable workbook under build/inventory/**. Pure.

    Only includes files directly under sit/, uat/, or osat/ subdirectories.
    Files under other subdirectories or directly in build/inventory/ are skipped.
    """
    items = []
    if INVENTORY_DIR.exists():
        for p in sorted(INVENTORY_DIR.rglob("*.xlsx")):
            parent_name = p.parent.name
            # Only include files whose parent directory is a valid kind
            if parent_name not in _VALID_KINDS:
                continue
            m = _STORY_IN_NAME.match(p.stem)
            items.append({
                "file": p.relative_to(INVENTORY_DIR).as_posix(),
                "story": m.group(1) if m else None,
                "kind": parent_name,
                "mtime": datetime.fromtimestamp(
                    p.stat().st_mtime, timezone.utc).isoformat(),
            })
    return items


def state():
    """Everything the app's live state view needs, in one JSON-safe dict."""
    dashboard, _graph = gather()
    return {
        "project": dashboard["project"],
        "prd": dashboard["prd"],
        "stories": dashboard["stories"],
        "flows": dashboard["flows"],
        "gaps": dashboard["gaps"],
        "cards": dashboard["cards"],
        "change_reports": dashboard["change_reports"],
        "suites": dashboard["suites"],
        "totals": dashboard["totals"],
        "next": collect_next([]),
        "inventory": _inventory(),
    }


def _current_branch():
    """Pure read of .git/HEAD (no subprocess). Falls back to 'main' / short sha."""
    head = ROOT / ".git" / "HEAD"
    try:
        txt = head.read_text(encoding="utf-8").strip()
    except OSError:
        return "main"
    if txt.startswith("ref:"):
        return txt.split("/", 2)[-1]      # 'ref: refs/heads/<name>' -> '<name>'
    return txt[:12]                        # detached HEAD -> short sha


def _project_phase(stories):
    """Aggregate 4-phase tracker position, delegated to wiki_next so the CLI
    and the project card share one rule. Kept as a named function because
    projects() and the app tests both call it."""
    return phase_from_stories(stories)


def _next_view(nxt):
    """Map the first `wiki next` row to a ProjectCard.next {label, view}."""
    rows = nxt.get("rows") or []
    if not rows:
        return None
    r = rows[0]
    ref = r.get("id") or r.get("arg")
    view = {"kind": "story", "id": ref} if r.get("scope") == "story" \
        else {"kind": "dashboard"}
    return {"label": r.get("skill") or r.get("command") or "Next action",
            "view": view}


def projects():
    """Level-0 portfolio: one ProjectCard per project. The app is scoped to a
    single repo today, so this returns exactly the current repo.

    EXTENSION POINT (multi-project): a tester spans several products in their
    branch. A future version scans sibling git worktrees / branches and appends
    one card per checkout here; the ProjectCard shape and this function's return
    contract stay identical. Pure: reads gather() + collect_next() + .git/HEAD,
    never writes.
    """
    dashboard, _graph = gather()
    stories = dashboard["stories"]
    nxt = collect_next([])
    return {"projects": [{
        "id": ROOT.name,
        "product": dashboard["project"],
        "branch": _current_branch(),
        "phase": _project_phase(stories),
        "counts": {"stories": dashboard["totals"]["stories"],
                   "tcs": dashboard["totals"]["tcs"]},
        "next": _next_view(nxt),
    }]}


def inbox():
    """Pending cards (no human_response) parsed render-ready. Pure.

    The 'which cards are pending' rule lives in wiki_next.pending_cards() so
    the CLI banner and this view can never disagree; the shaping below is
    this surface's own concern."""
    cards = []
    for c in pending_cards():
        raw = c["card"]
        item = {"file": c["file"], "card_type": c["card_type"],
                "story": c["story"], "session": c["session"],
                "emitted_at": raw.get("emitted_at")}
        if c["card_type"] == "alignment":
            item["zones"] = raw.get("zones")
        elif c["card_type"] == "coverage":
            item["coverage_status"] = raw.get("coverage_status")
            item["map_corrections"] = raw.get("map_corrections")
            item["note"] = raw.get("note")
        cards.append(item)
    return {"cards": cards}


_SUITE_KINDS = {"sit", "uat", "osat", "mixed"}
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_PRIORITY_RE = re.compile(r"^P\d$")
_LIST_KEYS = ("include_modules", "exclude_modules",
              "include_flows", "exclude_flows")


def _validated_filters(f):
    """Filters -> a wiki_suite-shaped suite dict, or ValueError. Strict:
    unknown keys, bad slugs, bad priorities, wrong types are all rejected."""
    if not isinstance(f, dict):
        raise ValueError(f"filters must be an object, got {type(f).__name__}")
    allowed = {"kind", *_LIST_KEYS, "priorities"}
    extra = set(f) - allowed
    if extra:
        raise ValueError(f"unexpected filter keys: {sorted(extra)}")
    kind = f.get("kind", "sit")
    if kind not in _SUITE_KINDS:
        raise ValueError(f"invalid kind: {kind!r}")
    suite = {"kind": kind}
    for key in _LIST_KEYS:
        vals = f.get(key) or []
        if not isinstance(vals, list) or not all(
                isinstance(v, str) and _SLUG_RE.fullmatch(v) for v in vals):
            raise ValueError(f"invalid {key}: {vals!r}")
        suite[key] = vals
    prios = f.get("priorities") or []
    if not isinstance(prios, list) or not all(
            isinstance(v, str) and _PRIORITY_RE.fullmatch(v) for v in prios):
        raise ValueError(f"invalid priorities: {prios!r}")
    suite["priorities"] = prios
    return suite


def suite_preview(filters):
    """Resolved TC-count preview from validated filters. Pure: reuses
    wiki_suite.select over load_all(), so the count matches `suite compile`."""
    suite = _validated_filters(filters)
    concepts, _manifest = load_all()
    selected, retired, stale = select(suite, concepts)
    return {"count": len(selected),
            "ids": [fm["id"] for _rel, fm, _body in selected],
            "retired": len(retired), "stale": len(stale)}
