#!/usr/bin/env python3
"""Plain-assert tests for wiki_graph (run: py tools/test_wiki_graph.py).
Matches the tools/smoke.py idiom - no pytest in this repo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import load_all
import wiki_graph as wg
from testkit import SkipTest, need, skip_if_empty


def test_build_model_has_br_and_resolution_nodes():
    concepts, manifest = load_all()
    model = wg.build_model(concepts, manifest)
    types = {n["type"] for n in model["nodes"]}
    assert "BR" in types, "BusinessRule nodes missing from model"
    assert "Resolution" in types, "Resolution nodes missing from model"
    # BR nodes are story fragments: stories/US-X#BR-...
    br = [n for n in model["nodes"] if n["type"] == "BR"]
    assert all("#BR-" in n["id"] for n in br), "BR node ids must be story fragments"


def test_build_model_lands_dropped_edges():
    concepts, manifest = load_all()
    model = wg.build_model(concepts, manifest)
    kinds = [l["type"] for l in model["links"]]
    assert "verifies_rules" in kinds, "verifies_rules edges not in model"
    assert "resolves" in kinds, "resolves edges not in model"
    assert "has_br" in kinds, "story->BR has_br edges not in model"


def test_scope_from_verdicts_selects_seed_and_reached():
    concepts, manifest = load_all()
    model = wg.build_model(concepts, manifest)
    story = next(n["id"] for n in model["nodes"] if n["type"] == "Story")
    # pick any node reachable in the raw links from the story
    reached = next(l["target"] for l in model["links"]
                   if l["source"] == story and l["target"] != story)
    sub = wg.scope_from_verdicts(model, story, {reached: "stale"})
    ids = {n["id"] for n in sub["nodes"]}
    assert story in ids and reached in ids
    assert (len(ids) == 2)
    st = {n["id"]: n["state"] for n in sub["nodes"]}
    assert st[reached] == "stale", "verdict must overwrite node state"


def test_scope_coverage_is_one_story():
    concepts, manifest = load_all()
    model = wg.build_model(concepts, manifest)
    story = next(n["id"] for n in model["nodes"] if n["type"] == "Story")
    sub = wg.scope_coverage(model, story)
    kinds = {n["type"] for n in sub["nodes"]}
    assert "Story" in kinds
    # every AC/BR/Component node kept must belong to this story
    frags = [n for n in sub["nodes"] if n["type"] in ("AC", "BR", "Component")]
    assert all(n["id"].startswith(story + "#") for n in frags)


def _fixture_model():
    """A two-module project built in memory: each module is derived from its
    PRD's top-level section, each story from a subsection. No file is read,
    so this holds in a project that has no PRD of its own."""
    def story(sid):
        return {"type": "User Story", "id": sid, "title": sid,
                "status": "aligned",
                "acceptance_criteria": [{"id": "AC1", "text": "Fixture."}],
                "business_rules": [{"id": "BR-1", "text": "Fixture."}]}
    concepts, edges = {}, []
    for mod, prd in (("a", "rental-application"), ("b", "rental-payment")):
        top, sub = f"sources/prd/{prd}/1", f"sources/prd/{prd}/1-1"
        for rel, title in ((top, "1 Top"), (sub, "1.1 Sub")):
            concepts[rel] = ({"type": "PRD Section", "id": f"prd#{rel[12:]}",
                              "title": title, "prd": prd}, "", None)
        concepts[f"modules/{mod}"] = ({"type": "Module", "id": mod,
                                       "title": f"Module {mod}"}, "", None)
        concepts[f"stories/US-{mod}"] = (story(f"US-{mod}"), "", None)
        tc = f"testcases/sit/{mod}/1.1-AC01-01"
        concepts[tc] = ({"type": "Test Case", "id": f"{mod}-1", "title": "T",
                         "status": "active",
                         "covers": [f"/stories/US-{mod}.md#AC1"]}, "", None)
        edges += [[f"modules/{mod}", "derived_from", top],
                  [f"stories/US-{mod}", "module", f"modules/{mod}"],
                  [f"stories/US-{mod}", "derived_from", sub],
                  [tc, "covers", f"stories/US-{mod}#AC1"]]
    manifest = {"schema_version": 2, "edges": edges, "prds": {
        "rental-application": {"title": "A", "adopted_version": 1,
                            "staged_version": None},
        "rental-payment": {"title": "B", "adopted_version": 2,
                        "staged_version": None}}}
    return wg.build_model(concepts, manifest)


def test_scope_traceability_anchors_each_story_to_its_modules_prd_section():
    sub = wg.scope_traceability(_fixture_model())
    kinds = {n["type"] for n in sub["nodes"]}
    assert kinds == {"PRD Section", "Story", "AC", "TC"}, f"types: {kinds}"
    prd = sorted(n["id"] for n in sub["nodes"] if n["type"] == "PRD Section")
    # one anchor per module: the module's top-level section, never the
    # subsection the story itself cites
    assert prd == ["sources/prd/rental-application/1",
                   "sources/prd/rental-payment/1"], prd
    src = {l["source"] for l in sub["links"]}
    assert not src & set(prd), "PRD anchors must be roots (no outgoing edge)"
    assert {(l["source"], l["target"]) for l in sub["links"]
            if l["type"] == "derived_from"} == {
        ("stories/US-a", "sources/prd/rental-application/1"),
        ("stories/US-b", "sources/prd/rental-payment/1")}, sub["links"]
    assert {l["type"] for l in sub["links"]} == {"derived_from", "has_ac",
                                                 "covers"}


def test_scope_traceability_is_clean_four_level_tree():
    concepts, manifest = load_all()
    model = wg.build_model(concepts, manifest)
    sub = wg.scope_traceability(model)
    kinds = {n["type"] for n in sub["nodes"]}
    # only the four chain node types survive — no BR/Component/Term/Resolution
    assert kinds <= {"PRD Section", "Story", "AC", "TC"}, f"extra types: {kinds}"
    # The anchors are asserted on live content only when it has a PRD; the
    # fixture test above proves them in every project.
    need("PRD Section", "project has no PRD section to anchor a story to")
    # Internal links point child->parent (Story->PRD, TC->AC), so PRD anchors
    # are pure sinks here -> they become the tree ROOTS after convert() flips
    # derived_from to SPECIFIES. Module anchoring yields few anchors, not the
    # dozens of story-level derived_from subsections.
    src = {l["source"] for l in sub["links"]}
    prd = [n for n in sub["nodes"] if n["type"] == "PRD Section"]
    assert prd, "expected PRD anchor nodes"
    assert all(n["id"] not in src for n in prd), \
        "PRD anchors must be roots (no outgoing internal edge)"
    assert len(prd) <= 5, f"module anchoring should give few anchors, got {len(prd)}"
    # the chain is present: PRD->Story (derived_from), Story->AC, TC->AC (covers)
    ltypes = {l["type"] for l in sub["links"]}
    assert {"derived_from", "has_ac", "covers"} <= ltypes


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        try:
            fn()
        except SkipTest as e:
            print(f"[SKIP] {fn.__name__}: {e}")
            continue
        print(f"[PASS] {fn.__name__}")
    print(f"{len(fns)} ran")


if __name__ == "__main__":
    skip_if_empty("unit: wiki graph model")
    _run()
