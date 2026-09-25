#!/usr/bin/env python3
"""Plain-assert tests for the explorer read model
(run: py tools/test_app_explorer_models.py). No pytest in this repo -- matches
tools/smoke.py and tools/test_app_read_models.py. Assert shape, not content."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
import explorer_models as em
from testkit import skip_if_empty


def test_structure_frontmatter_classifies_each_shape():
    fm = {
        "id": "US-X", "title": "T", "status": "aligned", "type": "User Story",
        "module": "/modules/m.md",
        "derived_from": ["/sources/prd/a.md", "/sources/prd/b.md"],
        "acceptance_criteria": [
            {"id": "AC1", "text": "do a thing", "status": "active"}],
        "generated_from": {"prd_version": 1},
        "priority": "P1",
    }
    fields = {f["key"]: f for f in em.structure_frontmatter(fm)}
    # header keys are lifted out
    for k in ("id", "title", "status", "type"):
        assert k not in fields, k
    assert fields["module"]["kind"] == "link"
    assert fields["module"]["ref"] == "/modules/m.md"
    assert fields["derived_from"]["kind"] == "links"
    assert fields["derived_from"]["refs"] == ["/sources/prd/a.md", "/sources/prd/b.md"]
    ac = fields["acceptance_criteria"]
    assert ac["kind"] == "itemized"
    assert ac["items"][0] == {"id": "AC1", "text": "do a thing", "status": "active"}
    assert fields["generated_from"]["kind"] == "group"
    assert fields["priority"] == {"key": "priority", "kind": "value", "value": "P1"}


def test_doc_facets_has_all_keys_for_a_tc():
    fm = {"id": "T-1", "type": "Test Case", "status": "stale",
          "origin": "agent-proposed",
          "covers": ["/stories/US-VHLD.md#AC1"],
          "stale_because": [{"cause": "prd_changed"}]}
    f = em.doc_facets("testcases/sit/x/T-1", fm, {})
    for k in ("kind", "status", "origin_state", "story", "asserted_by",
              "stale", "staleness_causes"):
        assert k in f, k
    assert f["kind"] == "testcases"
    assert f["status"] == "stale"
    assert f["origin_state"] == "proposed"
    assert f["story"] == "stories/US-VHLD"          # owning story from covers[0]
    assert f["stale"] is True
    assert f["staleness_causes"] == ["prd_changed"]


def test_doc_facets_marks_asserted_origin():
    fm = {"id": "US-X", "type": "User Story", "status": "aligned",
          "origin": "human-authored", "asserted_by": "syabz"}
    f = em.doc_facets("stories/US-X", fm, {})
    assert f["origin_state"] == "asserted"
    assert f["asserted_by"] == "syabz"
    assert f["story"] == "stories/US-X"             # a story owns itself


def test_explorer_snapshot_has_documented_keys():
    s = em.explorer()
    for key in ("tree", "docs", "graph"):
        assert key in s, key
    assert s["tree"] and isinstance(s["tree"], list)
    grp = s["tree"][0]
    assert set(grp) >= {"kind", "label", "count", "items"}


def test_explorer_docs_are_keyed_by_build_model_rel():
    s = em.explorer()
    node_ids = {n["id"] for n in s["graph"]["nodes"]}
    # every file-level graph node (no '#') has a matching doc
    file_nodes = {n for n in node_ids if "#" not in n}
    missing = [n for n in file_nodes if n not in s["docs"]]
    assert not missing, f"graph file-nodes without a doc: {missing[:5]}"


def test_explorer_graph_edges_match_build_model():
    """The correctness guarantee: the explorer cannot diverge from the RTM."""
    import wiki, wiki_graph
    concepts, manifest = wiki.load_all()
    expected = wiki_graph.build_model(concepts, manifest)["links"]
    got = em.explorer()["graph"]["links"]
    assert got == expected


def test_explorer_is_json_serialisable():
    json.dumps(em.explorer())


def test_explorer_does_not_mutate_the_repo():
    import subprocess
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout
    em.explorer()
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout
    assert before == after, f"explorer() mutated the tree:\n{after}"


def test_explorer_docs_expose_frontmatter_type():
    """Each doc carries its frontmatter `type` so the Explore badge can read it.
    Assert the KEY exists on every doc (shape, not a specific value)."""
    s = em.explorer()
    assert s["docs"], "no docs in snapshot"
    for rel, d in s["docs"].items():
        assert "type" in d, f"{rel} missing 'type' key"


if __name__ == "__main__":
    skip_if_empty("unit: app explorer models")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_explorer_models OK")
