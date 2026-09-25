#!/usr/bin/env python3
"""In-process read model for the wiki explorer (sub-project C).

Pure: imports and reads, never writes. Reuses the exact loaders the dashboard
already calls -- wiki.load_all, wiki_dashboard.collect, wiki_graph.build_model --
so the explorer can never disagree with `rtm`/`impact`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from wiki import resolve_ref, load_all
from wiki_dashboard import collect
from wiki_graph import build_model

_HEADER_KEYS = {"id", "title", "status", "version", "type"}


def _is_ref(v):
    return isinstance(v, str) and v.startswith("/") and v.endswith(".md") or (
        isinstance(v, str) and v.startswith("/") and ".md#" in v)


def structure_frontmatter(fm):
    """Classify each frontmatter key by the SHAPE of its value, never by kind.
    Header keys render in the header band, so they are omitted here."""
    fields = []
    for key, val in fm.items():
        if key in _HEADER_KEYS:
            continue
        if _is_ref(val):
            label = val.lstrip("/").rsplit("/", 1)[-1]
            fields.append({"key": key, "kind": "link", "ref": val, "label": label})
        elif isinstance(val, list) and val and all(_is_ref(v) for v in val):
            fields.append({"key": key, "kind": "links", "refs": list(val)})
        elif isinstance(val, list) and val and all(
                isinstance(v, dict) and "id" in v for v in val):
            # components carry `name` where ACs/BRs carry `text`; fold both
            # into the one display field so every itemized row has a body
            fields.append({"key": key, "kind": "itemized", "items": [
                {"id": v["id"], "text": v.get("text") or v.get("name"),
                 "status": v.get("status")}
                for v in val]})
        elif isinstance(val, dict):
            fields.append({"key": key, "kind": "group",
                           "fields": structure_frontmatter(val)})
        else:
            fields.append({"key": key, "kind": "value", "value": val})
    return fields


def _kind_of(rel):
    """First path segment is the vault kind (sources/stories/testcases/...)."""
    return rel.split("/", 1)[0]


def doc_facets(rel, fm, story_index):
    kind = _kind_of(rel)
    if kind == "stories":
        story = rel
    else:
        covers = fm.get("covers") or fm.get("derived_from") or []
        story = resolve_ref(covers[0])[0] if covers and _kind_of(
            resolve_ref(covers[0])[0]) == "stories" else None
    causes = [c.get("cause") for c in (fm.get("stale_because") or [])]
    if not causes and story in story_index:
        causes = story_index[story].get("stale_causes") or []
    asserted_by = fm.get("asserted_by") or (
        story_index.get(story, {}).get("asserted_by") if story else None)
    return {
        "kind": kind,
        "status": fm.get("status"),
        "origin_state": "proposed" if fm.get("origin") == "agent-proposed"
        else "asserted",
        "story": story,
        "asserted_by": asserted_by,
        "stale": fm.get("status") == "stale" or bool(causes),
        "staleness_causes": sorted(set(c for c in causes if c)),
    }


def explorer():
    """Assemble the one snapshot: tree (grouped by kind), docs (keyed by rel), graph (build_model).

    Returns dict with:
      - tree: list of {kind, label, count, items} groups, sorted by kind
      - docs: dict keyed by rel with {ref, kind, title, status, version, fields, body_md, facets}
      - graph: build_model output verbatim
    """
    concepts, manifest = load_all()
    stories_d, tcs, flows, terms, prd, figma, modules, resolutions, _cov = \
        collect(concepts, manifest)
    story_index = {rel: {"asserted_by": fm.get("asserted_by"),
                         "stale_causes": []}
                   for rel, fm in stories_d.items()}

    docs, groups = {}, {}
    for rel, (fm, body, _p) in concepts.items():
        kind = _kind_of(rel)
        docs[rel] = {
            "ref": rel, "kind": kind,
            "title": fm.get("title"), "status": fm.get("status"),
            "version": fm.get("version"),
            "type": fm.get("type"),
            "fields": structure_frontmatter(fm),
            "body_md": body,
            "facets": doc_facets(rel, fm, story_index),
        }
        groups.setdefault(kind, []).append(
            {"ref": rel, "title": fm.get("title"), "status": fm.get("status")})

    tree = [{"kind": k, "label": k.replace("_", " ").title(),
             "count": len(items), "items": sorted(items, key=lambda i: i["ref"])}
            for k, items in sorted(groups.items())]

    return {"tree": tree, "docs": docs,
            "graph": build_model(concepts, manifest)}
