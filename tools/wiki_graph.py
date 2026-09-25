#!/usr/bin/env python3
"""Shared traceability-graph machinery: one canonical model, scope filters,
and the graph-viewer bridge. Deterministic, LLM-free. Absorbs the old
tools/rtm_viewer.py and the model half of wiki_rtm.py.

The internal model uses upstream-pointing links (TC -covers-> AC,
Story -derived_from-> PRD). convert() flips the chain edges to their
downstream reading so the viewer's tree roots at PRD sections."""
import json
import subprocess
import sys

from wiki import ROOT, resolve_ref
from wiki_coverage import load_coverage

RTM = ROOT / "build/rtm"
GRAPHS = RTM / "graphs"
# The viewer is vendored in-tree (sub-project A). scripts/*.mjs resolve
# ../src/lib/validate.mjs and ../dist/viewer.html relative to themselves, so
# this must point at the workspace root, not at scripts/.
VIEWER_REPO = ROOT / "tools/app/web"

NODE_TYPE = {
    "Story": "UserStory", "AC": "ValidationRule", "BR": "BusinessRule",
    "TC": "TestCase", "Component": "Component", "PRD Section": "Page",
    "Figma Page": "State", "Term": "DBColumn", "Flow": "Action",
    "Module": "Module", "Resolution": "Resolution",
}
FLIP_TO_DOWNSTREAM = {
    "covers": "VERIFIED_BY", "verifies_rules": "VERIFIES",
    "derived_from": "SPECIFIES", "defined_in": "DEFINES",
    "module": "CONTAINS", "flow": "COVERED_BY",
}
SPINE = ("SPECIFIES", "HAS_AC", "VERIFIED_BY")

# Preset filter lenses the viewer shows as one-click chips (see graph-viewer
# presets). A preset is a filter overlay only; it never changes the active view.
TRACE_DESC = (
    "Requirements traceability, top to bottom: each PRD module section "
    "specifies user stories, every story carries its acceptance criteria, and "
    "each AC is verified by test cases. Switch VIEW to Tidy tree or Indented "
    "to read it as a hierarchy.")

# Lenses for the clean traceability graph (already only 4 node types).
TRACE_PRESETS = [
    {"name": "Full chain",
     "description": "PRD section -> story -> acceptance criterion -> test case."},
    {"name": "Coverage (Story -> AC -> TC)",
     "description": "Hide PRD sources; show what verifies each AC.",
     "nodeTypes": ["UserStory", "ValidationRule", "TestCase"],
     "edgeTypes": ["HAS_AC", "VERIFIED_BY"]},
    {"name": "Requirements (PRD -> Story -> AC)",
     "description": "Hide test cases; show the requirement structure.",
     "nodeTypes": ["Page", "UserStory", "ValidationRule"],
     "edgeTypes": ["SPECIFIES", "HAS_AC"]},
]

# Lenses for the full RTM graph. Default focuses the 270-node graph onto the
# traceability spine so it opens readable; other lenses reveal one edge family.
RTM_PRESETS = [
    {"name": "Traceability spine", "default": True,
     "description": "PRD section -> story -> acceptance criterion -> test case.",
     "nodeTypes": ["Page", "UserStory", "ValidationRule", "TestCase"],
     "edgeTypes": ["SPECIFIES", "HAS_AC", "VERIFIED_BY"]},
    {"name": "Business rules",
     "description": "Which test case verifies which business rule.",
     "nodeTypes": ["UserStory", "BusinessRule", "TestCase"],
     "edgeTypes": ["HAS_BR", "VERIFIES"]},
    {"name": "Coverage map",
     "description": "AC -> UI component -> test case coverage.",
     "nodeTypes": ["UserStory", "ValidationRule", "Component", "TestCase"],
     "edgeTypes": ["HAS_AC", "MAPS_TO", "EXERCISES"]},
    {"name": "Resolutions",
     "description": "Human assertions that shaped a rule, AC, or term.",
     "nodeTypes": ["Resolution", "ValidationRule", "BusinessRule", "DBColumn"],
     "edgeTypes": ["RESOLVES", "SUPERSEDES", "SUPERSEDED_BY"]},
    {"name": "Everything"},
]


def collect(concepts, manifest):
    stories, tcs, flows, terms, prd, figma, modules, resolutions = (
        {}, {}, {}, {}, {}, {}, {}, {})
    bucket = {"User Story": stories, "Test Case": tcs, "Flow": flows,
              "Glossary Term": terms, "PRD Section": prd, "Figma Page": figma,
              "Module": modules, "Resolution": resolutions}
    for rel, (fm, _body, _p) in concepts.items():
        if not fm:
            continue
        b = bucket.get(fm.get("type"))
        if b is not None:
            b[rel] = fm
    coverage = {}
    for rel, fm in tcs.items():
        for c in fm.get("covers") or []:
            tgt, frag = resolve_ref(c)
            coverage.setdefault(f"{tgt}#{frag}", []).append((rel, fm))
    return (stories, tcs, flows, terms, prd, figma, modules, resolutions,
            coverage)


def build_model(concepts, manifest):
    (stories, tcs, flows, terms, prd, figma, modules, resolutions,
     _coverage) = collect(concepts, manifest)
    nodes, links = [], []

    def state_of(fm):
        s = fm.get("status") or "active"
        return {"asserted": "aligned", "draft": "proposed",
                "in-alignment": "proposed"}.get(s, s)

    def add(rel, fm, ntype):
        nodes.append({"id": rel, "label": (fm.get("title") or rel)[:60],
                      "type": ntype, "state": state_of(fm)})

    for rel, fm in prd.items():
        add(rel, fm, "PRD Section")
    for rel, fm in figma.items():
        add(rel, fm, "Figma Page")
    for rel, fm in modules.items():
        add(rel, fm, "Module")
    for rel, fm in terms.items():
        add(rel, fm, "Term")
    for rel, fm in flows.items():
        add(rel, fm, "Flow")
    for rel, fm in resolutions.items():
        add(rel, fm, "Resolution")
    for rel, fm in stories.items():
        add(rel, fm, "Story")
        for ac in fm.get("acceptance_criteria") or []:
            nodes.append({"id": f"{rel}#{ac['id']}", "label": ac["id"],
                          "type": "AC",
                          "state": "voided" if ac.get("status") == "voided"
                          else state_of(fm)})
            links.append({"source": rel, "target": f"{rel}#{ac['id']}",
                          "type": "has_ac"})
        for br in fm.get("business_rules") or []:
            nodes.append({"id": f"{rel}#{br['id']}", "label": br["id"],
                          "type": "BR", "state": state_of(fm)})
            links.append({"source": rel, "target": f"{rel}#{br['id']}",
                          "type": "has_br"})
        for c in fm.get("components") or []:
            nodes.append({"id": f"{rel}#{c['id']}",
                          "label": c.get("name", c["id"]),
                          "type": "Component", "state": state_of(fm)})
        cmap, _disp, _cs = load_coverage(fm)
        for ac_id, comp_ids in cmap.items():
            for cid in comp_ids:
                links.append({"source": f"{rel}#{ac_id}",
                              "target": f"{rel}#{cid}", "type": "maps_to"})
    for rel, fm in tcs.items():
        add(rel, fm, "TC")
    story_maps = {srel: load_coverage(sfm)[0] for srel, sfm in stories.items()}
    for rel, fm in tcs.items():
        seen = set()
        for cref in fm.get("covers") or []:
            tgt, frag = resolve_ref(cref)
            for cid in story_maps.get(tgt, {}).get(frag, []):
                if (tgt, cid) not in seen:
                    seen.add((tgt, cid))
                    links.append({"source": rel, "target": f"{tgt}#{cid}",
                                  "type": "exercises"})
    node_ids = {n["id"] for n in nodes}
    for s, k, t in manifest.get("edges", []):
        if s in node_ids and t in node_ids:
            links.append({"source": s, "target": t, "type": k})
    links = [l for l in links
             if l["source"] in node_ids and l["target"] in node_ids]
    return {"nodes": nodes, "links": links,
            "meta": {"prd_version": manifest.get("adopted_prd_version"),
                     "counts": {"nodes": len(nodes), "links": len(links)}}}


def _label_of(node):
    nid, ntype, text = node["id"], node["type"], node.get("label") or node["id"]
    if ntype == "TC":
        return nid.rsplit("/", 1)[-1]
    if ntype in ("AC", "BR"):
        return text
    if ntype in ("Story", "Flow", "Module", "Term", "Resolution"):
        tail = nid.rsplit("/", 1)[-1]
        return text if text == tail else f"{tail}: {text}"
    return text


def convert(model, spine=False):
    nodes = []
    for n in model["nodes"]:
        props = {"ref": n["id"], "wiki_type": n["type"]}
        if n.get("state"):
            props["state"] = n["state"]
        if n["type"] in ("TC", "Story", "Flow", "Module", "Term",
                         "Resolution") and n.get("label"):
            props["title"] = n["label"]
        nodes.append({"nodeId": n["id"],
                      "nodeType": NODE_TYPE.get(n["type"], n["type"]),
                      "displayLabel": _label_of(n), "properties": props})
    ids = {n["nodeId"] for n in nodes}
    edges, seen = [], set()
    for l in model["links"]:
        src, tgt, kind = l["source"], l["target"], l["type"]
        if kind in FLIP_TO_DOWNSTREAM:
            src, tgt, kind = tgt, src, FLIP_TO_DOWNSTREAM[kind]
        else:
            kind = kind.upper()
        if src not in ids or tgt not in ids or src == tgt:
            continue
        if spine and kind not in SPINE:
            continue
        key = (kind, src, tgt)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"edgeId": f"e{len(edges) + 1}", "edgeType": kind,
                      "fromNodeId": src, "toNodeId": tgt, "properties": {}})
    if spine:
        keep = {e["fromNodeId"] for e in edges} | {e["toNodeId"] for e in edges}
        nodes = [n for n in nodes if n["nodeId"] in keep]
    prd = (model.get("meta") or {}).get("prd_version")
    return {"meta": {"title": "tc-copilot Traceability"
                     + (" (chain)" if spine else ""),
                     "description": f"PRD v{prd}: {len(nodes)} nodes, "
                                    f"{len(edges)} edges"},
            "nodes": nodes, "edges": edges}


def validate(json_path):
    rc = subprocess.run(["node", str(VIEWER_REPO / "scripts/validate.mjs"),
                         str(json_path)], capture_output=True, text=True)
    print(rc.stdout.strip() or rc.stderr.strip())
    if rc.returncode:
        sys.exit(rc.returncode)


def bake(json_path, html_path):
    rc = subprocess.run(["node", str(VIEWER_REPO / "scripts/bake.mjs"),
                         str(json_path), "-o", str(html_path)],
                        capture_output=True, text=True)
    print(rc.stdout.strip() or rc.stderr.strip())
    if rc.returncode:
        sys.exit(rc.returncode)


def _subgraph(model, keep_ids, state_by_ref=None):
    keep_ids = set(keep_ids)
    nodes = []
    for n in model["nodes"]:
        if n["id"] in keep_ids:
            m = dict(n)
            if state_by_ref and m["id"] in state_by_ref:
                m["state"] = state_by_ref[m["id"]]
            nodes.append(m)
    links = [l for l in model["links"]
             if l["source"] in keep_ids and l["target"] in keep_ids]
    return {"nodes": nodes, "links": links, "meta": dict(model.get("meta") or {})}


def scope_rtm(model, spine=False):
    return model  # spine handled at convert time via emit(..., spine=...)


def scope_from_verdicts(model, seed_ref, verdict_by_ref):
    keep = {seed_ref} | set(verdict_by_ref)
    return _subgraph(model, keep, state_by_ref=verdict_by_ref)


def scope_coverage(model, story_rel, state_by_ref=None):
    keep = {story_rel}
    for n in model["nodes"]:
        if n["id"].startswith(story_rel + "#"):   # this story's AC/BR/Component
            keep.add(n["id"])
    # TCs that exercise/cover/verify any kept fragment
    for l in model["links"]:
        if l["target"] in keep and l["type"] in ("exercises", "covers",
                                                  "verifies_rules"):
            keep.add(l["source"])
    return _subgraph(model, keep, state_by_ref=state_by_ref)


def scope_traceability(model):
    """Clean PRD -> Story -> AC -> Test Case hierarchy.

    Anchors each story to its MODULE's top-level PRD section (one root per
    module) instead of the story's granular derived_from subsections, so the
    view reads as a tree instead of a many-parent fan-in tangle. Keeps only
    Story / AC / TC nodes plus those PRD anchors; drops BR / Component / Term /
    Resolution / Flow. Deterministic (node order follows the full model)."""
    by_id = {n["id"]: n for n in model["nodes"]}
    module_of, anchor_of = {}, {}
    for l in model["links"]:
        if l["type"] == "module":
            module_of.setdefault(l["source"], l["target"])
        elif (l["type"] == "derived_from"
              and by_id.get(l["source"], {}).get("type") == "Module"):
            anchor_of.setdefault(l["source"], l["target"])
    keep, links = set(), []
    for n in model["nodes"]:
        if n["type"] in ("Story", "AC", "TC"):
            keep.add(n["id"])
    for n in model["nodes"]:               # PRD anchor + synthetic PRD->Story
        if n["type"] != "Story":
            continue
        anchor = anchor_of.get(module_of.get(n["id"]))
        if anchor and anchor in by_id:
            keep.add(anchor)
            links.append({"source": n["id"], "target": anchor,
                          "type": "derived_from"})   # -> SPECIFIES on convert
    for l in model["links"]:               # Story -has_ac-> AC, TC -covers-> AC
        if (l["type"] in ("has_ac", "covers")
                and l["source"] in keep and l["target"] in keep):
            links.append(l)
    nodes = [dict(n) for n in model["nodes"] if n["id"] in keep]
    return {"nodes": nodes, "links": links, "meta": dict(model.get("meta") or {})}


def scope_suite(model, tc_rels, suite_name):
    keep = set(tc_rels)
    for l in model["links"]:                       # TC -> AC/BR
        if l["source"] in keep and l["type"] in ("covers", "exercises",
                                                  "verifies_rules"):
            keep.add(l["target"])
    for l in model["links"]:                       # Story -has_ac/has_br-> frag
        if l["target"] in keep and l["type"] in ("has_ac", "has_br"):
            keep.add(l["source"])
    for l in model["links"]:                       # Story -module-> Module
        if l["source"] in keep and l["type"] == "module":
            keep.add(l["target"])
    sub = _subgraph(model, keep)
    suite_id = f"suite/{suite_name}"
    sub["nodes"].insert(0, {"id": suite_id, "label": suite_name,
                            "type": "Module", "state": "active"})
    for tc in tc_rels:
        sub["links"].append({"source": suite_id, "target": tc,
                             "type": "contains"})
    return sub


def emit(scope, model, *, make_html=False, spine=False,
         title=None, description=None, presets=None):
    GRAPHS.mkdir(parents=True, exist_ok=True)
    viewer = convert(model, spine=spine)
    if title:
        viewer["meta"]["title"] = title
    if description:
        viewer["meta"]["description"] = description
    if presets:
        viewer["presets"] = presets
    jpath = GRAPHS / f"{scope}.json"
    jpath.write_text(json.dumps(viewer, indent=1, ensure_ascii=False),
                     encoding="utf-8", newline="\n")
    print(f"graph[{scope}]: {len(viewer['nodes'])} nodes / "
          f"{len(viewer['edges'])} edges -> {jpath.relative_to(ROOT)}")
    hpath = None
    if make_html:
        validate(jpath)
        hpath = GRAPHS / f"{scope}.html"
        bake(jpath, hpath)
        print(f"graph[{scope}]: baked -> {hpath.relative_to(ROOT)}")
    return jpath, hpath
