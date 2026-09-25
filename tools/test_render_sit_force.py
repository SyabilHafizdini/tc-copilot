#!/usr/bin/env python3
"""Plain-assert tests for the forced re-render's provenance-only skip
(run: py tools/test_render_sit_force.py). No pytest - matches tools/smoke.py.

`render_sit.py --force` must not rewrite a test case whose only difference
from the file on disk is its provenance (`generated_from.wiki_commit` and the
`wiki <sha>` token of the Traceability line): HEAD moves between the first
render and the forced one, and a rewrite would move every sealed hash.

Pure functions over synthetic spec/story dicts; nothing on disk is read or
written. A real double render at two different HEADs needs a story with a
confirmed coverage card and test model, which the content-free base does not
have - that end-to-end check is the project-branch pilot's job.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sit  # noqa: E402

SPEC = {"story": "/stories/US-FAKE.md", "module": "/modules/m.md",
        "figma": None, "out": "testcases/sit/m", "ac_prefix": "1.1",
        "scenario_id": "SC-{ac}-{seq:02d}", "generator_version": "1.0.0",
        "pre_common": "1. Logged in.", "post_default": "No change.",
        "test_cases": []}
STORY = {"id": "US-FAKE", "acceptance_criteria": [{"id": "1.1-AC1"}]}
GEN = {"prd_version": "1", "figma_hashes": {}, "wiki_commit": None,
       "generator_version": "1.0.0"}


def _tc(**kw):
    d = {"ac": "AC1", "seq": 1, "technique": "BVA", "priority": "P1",
         "area": "Area", "title": "t", "objective": "o",
         "steps": "1. Do it.", "expected": "1. It happened.",
         "coverage_items": ["BVA-01"]}
    d.update(kw)
    return d


def _build(tc, commit):
    return render_sit.build_tc(SPEC, STORY, tc, "1.1-AC01-01", "SC-AC1-01",
                               "1.1-AC1", GEN, commit)


def test_identical_except_provenance_is_a_provenance_only_change():
    prev_fm, prev_body = _build(_tc(), "aaaaaaa")
    new_fm, new_body = _build(_tc(), "bbbbbbb")
    assert prev_fm != new_fm and prev_body != new_body, "the commit must differ"
    assert "wiki aaaaaaa" in prev_body and "wiki bbbbbbb" in new_body, new_body
    assert prev_fm["generated_from"]["wiki_commit"] == "aaaaaaa", \
        "generated_from is per test case, never the shared dict mutated"
    assert GEN["wiki_commit"] is None, "the shared generated_from is untouched"
    assert render_sit.provenance_only_change(prev_fm, prev_body, new_fm, new_body)
    assert render_sit.provenance_only_change(prev_fm, prev_body,
                                             copy.deepcopy(prev_fm), prev_body)


def test_a_changed_expected_results_line_is_a_real_change():
    prev_fm, prev_body = _build(_tc(), "aaaaaaa")
    new_fm, new_body = _build(_tc(expected="1. It happened twice."), "bbbbbbb")
    assert not render_sit.provenance_only_change(prev_fm, prev_body, new_fm, new_body)
    # same commit, content changed: still a real change
    same_fm, same_body = _build(_tc(expected="1. It happened twice."), "aaaaaaa")
    assert not render_sit.provenance_only_change(prev_fm, prev_body, same_fm, same_body)


def test_a_changed_coverage_items_list_is_a_real_change():
    prev_fm, prev_body = _build(_tc(), "aaaaaaa")
    new_fm, new_body = _build(_tc(coverage_items=["BVA-01", "BVA-02"]), "bbbbbbb")
    assert prev_body.replace("aaaaaaa", "bbbbbbb") == new_body, "body is unchanged"
    assert not render_sit.provenance_only_change(prev_fm, prev_body, new_fm, new_body)


def test_a_missing_previous_frontmatter_is_a_real_change():
    new_fm, new_body = _build(_tc(), "bbbbbbb")
    assert not render_sit.provenance_only_change(None, new_body, new_fm, new_body)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_render_sit_force OK")
