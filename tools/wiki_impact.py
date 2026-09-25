#!/usr/bin/env python3
"""`wiki impact <ref>` — deterministic downstream impact analysis.

Answers "if I change this, what needs review?" BEFORE the change, using only
the links already in the wiki + manifest. No LLM, no writes, no commit — the
same determinism as `cascade`, asked ahead of time.

<ref> may be a concept or a fragment, in any of these forms:
    US-XXXX                          (story id)
    stories/US-XXXX                  (concept rel)
    stories/US-XXXX#BR-XXXX-04       (business-rule fragment)
    stories/US-XXXX#1.1.3.1.1-AC19   (acceptance-criterion fragment)
    sources/prd/4-1-1-1  /  prd#4-1-1-1   (PRD section, rel or id)

The traversal walks the dependency edges backwards (a thing that pins/covers/
derives-from the target is impacted by it) and reports each reached node with
its CASCADE VERDICT — the honest split the user cares about:

  * `cascade: stale`        a TC pinned the changed fragment; cascade WILL flag it.
  * `cascade: needs-review` a story pinned the changed source; cascade WILL flag it.
  * `downstream`            reachable, but cascade does NOT auto-flag it (the
                            dependency is coarser than a hash pin — a human must
                            judge whether the edit actually reaches this node).
  * `UNPINNED`              a TC references the target (covers/verifies_rules)
                            but never pinned it — a blind spot cascade misses.

Usage:
    py tools/wiki.py impact stories/US-XXXX#BR-XXXX-04
    py tools/wiki.py impact sources/prd/4-1-1-1 --json
"""
import json
import sys

from wiki import (ROOT, EDGE_KEYS, fragment_ids, load_manifest, read_concept,
                  resolve_ref, all_concepts)

# EDGE_KEYS where "source depends on target" (changing target impacts source).
# resolves/supersedes/superseded_by are resolution bookkeeping, not behavioural
# downstream, so they are excluded.
DEP_KEYS = {"derived_from", "defined_in", "illustrated_by", "module", "flow",
            "stories", "covers", "verifies_rules", "uses_terms", "journey"}

TYPE_ORDER = ["User Story", "Acceptance Criterion", "Business Rule", "Component",
              "Flow", "Test Case", "Glossary Term", "Module", "PRD Section",
              "Figma Page"]
FRAG_KIND = {"acceptance_criteria": "Acceptance Criterion",
             "business_rules": "Business Rule", "components": "Component",
             "branches": "Business Rule", "journey": "Journey Step"}


def _build_context():
    """One pass over the wiki: node types, display ids, fragment membership,
    source-id<->rel map, dependency edges, and the manifest pin sets."""
    concepts = {rel: fm for rel, fm, _b, _p in all_concepts() if fm}
    manifest = load_manifest()

    node_type, display, frag_of, src_id_to_rel = {}, {}, {}, {}
    for rel, fm in concepts.items():
        node_type[rel] = fm.get("type") or "?"
        display[rel] = fm.get("id") or rel
        if fm.get("type") in ("PRD Section", "Figma Page"):
            src_id_to_rel[fm["id"]] = rel
        for key, kind in FRAG_KIND.items():
            for e in fm.get(key) or []:
                if isinstance(e, dict) and "id" in e:
                    fref = f"{rel}#{e['id']}"
                    node_type[fref] = kind
                    display[fref] = e["id"]
                    frag_of.setdefault(rel, []).append(fref)

    # dependency edges: dependents[target] = [(source_rel, edge_key), ...]
    dependents = {}
    covers_edges = {}          # fragref -> set(tc_rel) via covers/verifies_rules
    for rel, fm in concepts.items():
        for key in EDGE_KEYS:
            if key not in DEP_KEYS:
                continue
            vals = fm.get(key)
            if isinstance(vals, str):
                vals = [vals]
            for v in vals or []:
                tgt, frag = resolve_ref(v)
                tref = tgt + (f"#{frag}" if frag else "")
                dependents.setdefault(tref, []).append((rel, key))
                if key in ("covers", "verifies_rules"):
                    covers_edges.setdefault(tref, set()).add(rel)
        for e in fm.get("journey") or []:
            if isinstance(e, dict) and e.get("ref"):
                tgt, frag = resolve_ref(e["ref"])
                tref = tgt + (f"#{frag}" if frag else "")
                dependents.setdefault(tref, []).append((rel, "journey"))

    # authoritative cascade edges from the manifest
    pins_by_tc, source_pins = {}, {}
    for _sc, b in manifest.get("bindings", {}).items():
        tc = b["tc"]
        pins = set(b.get("fragment_pins", {}))
        pins_by_tc[tc] = pins
        for fref in pins:
            dependents.setdefault(fref, []).append((tc, "pins"))
    for rel, fm in concepts.items():
        if fm.get("type") == "User Story":
            for sid in fm.get("source_pins") or {}:
                srel = src_id_to_rel.get(sid, sid)
                source_pins.setdefault(srel, set()).add(rel)

    return dict(concepts=concepts, node_type=node_type, display=display,
                frag_of=frag_of, src_id_to_rel=src_id_to_rel,
                dependents=dependents, covers_edges=covers_edges,
                pins_by_tc=pins_by_tc, source_pins=source_pins)


def _resolve_query(ref, ctx):
    """Map a user-supplied ref to a canonical node id, or exit with guidance."""
    rel, frag = resolve_ref(ref)
    if frag:
        node = f"{rel}#{frag}"
        if node not in ctx["node_type"]:
            sys.exit(f"unknown fragment '{node}'")
        return node
    if rel in ctx["node_type"]:
        return rel
    if rel in ctx["src_id_to_rel"]:                 # 'prd#4-1-1-1'
        return ctx["src_id_to_rel"][rel]
    for r, fm in ctx["concepts"].items():           # bare id, e.g. 'US-XXXX'
        if fm.get("id") == rel:
            return r
    sys.exit(f"unknown ref '{ref}' — expected a concept rel, a bare id, or rel#fragment")


def compute(ref):
    ctx = _build_context()
    seed = _resolve_query(ref, ctx)

    # forward impact BFS: dependents + concept->fragment containment
    reached, queue = set(), [seed]
    while queue:
        n = queue.pop()
        for dep, _key in ctx["dependents"].get(n, []):
            if dep not in reached:
                reached.add(dep)
                queue.append(dep)
        for fref in ctx["frag_of"].get(n, []):      # a concept contains its fragments
            if fref not in reached:
                reached.add(fref)
                queue.append(fref)
    reached.discard(seed)

    # Fragments the change would DIRECTLY alter — the only ones cascade stales a
    # TC from. A source/term/module change alters no fragment (cascade flags the
    # pinning STORY to needs-review instead), so changed_frags is empty and every
    # downstream TC is "review", not "stale". This is the honest cascade split.
    seed_type = ctx["node_type"].get(seed)
    if "#" in seed:
        changed_frags = {seed}
    elif seed_type == "User Story":
        changed_frags = set(ctx["frag_of"].get(seed, []))
    else:
        changed_frags = set()
    seed_is_source = seed_type in ("PRD Section", "Figma Page")

    def verdict(n):
        t = ctx["node_type"].get(n)
        if t == "Test Case":
            if ctx["pins_by_tc"].get(n, set()) & changed_frags:
                return "cascade: stale"
            if any(n in ctx["covers_edges"].get(f, set()) for f in changed_frags):
                return "UNPINNED"
            return "downstream"
        if t == "User Story" and seed_is_source and n in ctx["source_pins"].get(seed, set()):
            return "cascade: needs-review"
        return "downstream"

    items = [{"ref": n, "id": ctx["display"].get(n, n), "type": ctx["node_type"].get(n, "?"),
              "verdict": verdict(n)} for n in reached]
    items.sort(key=lambda x: (TYPE_ORDER.index(x["type"]) if x["type"] in TYPE_ORDER
                              else 99, x["id"]))
    return {"query": {"ref": seed, "id": ctx["display"].get(seed, seed),
                      "type": ctx["node_type"].get(seed, "?")}, "impact": items}


def cmd_impact(args):
    ref = next((a for a in args if not a.startswith("--")), None)
    if not ref:
        sys.exit("usage: wiki impact <ref> [--json]")
    result = compute(ref)
    from wiki import load_all
    from wiki_graph import build_model, emit, scope_from_verdicts
    _concepts, _manifest = load_all()
    _model = build_model(_concepts, _manifest)
    _seed = result["query"]["ref"]
    _verdicts = {it["ref"]: it["verdict"].replace("cascade: ", "")
                 for it in result["impact"]}
    _safe = _seed.replace("/", "_").replace("#", "-")
    emit(f"impact-{_safe}", scope_from_verdicts(_model, _seed, _verdicts),
         make_html="--graph" in args)
    if "--json" in args:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    q = result["query"]
    print(f"Impact of {q['ref']}  ({q['type']} {q['id']})\n")
    if not result["impact"]:
        print("  nothing downstream — no concept depends on this.")
        return
    by_type = {}
    for it in result["impact"]:
        by_type.setdefault(it["type"], []).append(it)
    tc_stale = tc_unpinned = 0
    for t in TYPE_ORDER:
        rows = by_type.get(t)
        if not rows:
            continue
        print(f"  {t} ({len(rows)})")
        for it in rows:
            tag = "" if it["verdict"] == "downstream" else f"   [{it['verdict']}]"
            print(f"    {it['id']}{tag}")
            tc_stale += it["verdict"] == "cascade: stale"
            tc_unpinned += it["verdict"] == "UNPINNED"
    total_tc = len(by_type.get("Test Case", []))
    print(f"\n  {len(result['impact'])} downstream nodes; "
          f"{total_tc} test cases ({tc_stale} auto-flagged by cascade, "
          f"{tc_unpinned} UNPINNED blind spots).")
