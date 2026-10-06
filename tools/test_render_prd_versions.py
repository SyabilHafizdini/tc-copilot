#!/usr/bin/env python3
"""generated_from.prd_versions and the Traceability line
(run: py tools/test_render_prd_versions.py). Pure - nothing on disk."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import render_sit
import render_uat

TWO = {"schema_version": 2, "prds": {
    "rental-application": {"title": "Rental application", "adopted_version": 2,
                        "staged_version": None},
    "rental-payment": {"title": "Rental payment", "adopted_version": 1,
                    "staged_version": 2}}}
BOTH = {"id": "US-BOTH", "derived_from": ["/sources/prd/rental-payment/1-1.md",
                                          "/sources/prd/rental-application/1-1.md"]}
APP = {"id": "US-APP", "derived_from": ["/sources/prd/rental-application/1-2.md"]}
HUMAN = {"id": "US-HS", "provenance": "human-stated"}


def test_a_story_citing_both_prds_gets_both_in_prd_versions():
    gf = render_sit.provenance([BOTH], TWO, {}, "abc1234", "1.0.0")
    assert gf == {"prd_versions": {"rental-application": 2, "rental-payment": 1},
                  "figma_hashes": {}, "wiki_commit": "abc1234",
                  "generator_version": "1.0.0"}, gf
    assert list(gf) == ["prd_versions", "figma_hashes", "wiki_commit",
                        "generator_version"], "key order is part of the file format"
    assert "prd_version" not in gf


def test_the_adopted_version_is_used_never_the_staged_one():
    gf = render_sit.provenance([{"derived_from": ["/sources/prd/rental-payment/1-1.md"]}],
                               TWO, {}, "abc1234", "1.0.0")
    assert gf["prd_versions"] == {"rental-payment": 1}, gf


def test_a_story_citing_no_prd_yields_an_empty_map():
    gf = render_sit.provenance([HUMAN], TWO, {"page": "sha256:x"}, "abc1234", "1.0.0")
    assert gf["prd_versions"] == {} and gf["figma_hashes"] == {"page": "sha256:x"}, gf


def test_a_flow_collects_the_prds_of_all_its_stories():
    gf = render_sit.provenance([APP, HUMAN, BOTH, None], TWO, {}, "abc1234", "1.0.0")
    assert gf["prd_versions"] == {"rental-application": 2, "rental-payment": 1}, gf


def test_traceability_line_lists_each_prd():
    both = render_sit.provenance([BOTH], TWO, {}, "abc1234", "1.0.0")
    assert render_sit.trace_source(both) == \
        "PRD rental-application v2, rental-payment v1 · wiki abc1234"
    none = render_sit.provenance([HUMAN], TWO, {}, "abc1234", "1.0.0")
    assert render_sit.trace_source(none) == "no PRD · wiki abc1234"


def test_traceability_line_never_says_vNone():
    later = {"schema_version": 2, "prds": {"rental-payment": {
        "title": "P", "adopted_version": None, "staged_version": 1}}}
    story = {"derived_from": ["/sources/prd/rental-payment/1-1.md"]}
    gf = render_sit.provenance([story], later, {}, "abc1234", "1.0.0")
    assert gf["prd_versions"] == {"rental-payment": None}, gf
    assert render_sit.trace_source(gf, later) == \
        "PRD rental-payment (no adopted version) · wiki abc1234"
    gone = render_sit.provenance([story], {"schema_version": 2, "prds": {}}, {},
                                 "abc1234", "1.0.0")
    assert render_sit.trace_source(gone, {"schema_version": 2, "prds": {}}) == \
        "PRD rental-payment (unregistered) · wiki abc1234"
    assert "None" not in render_sit.trace_source(gf)


def test_a_forced_render_leaves_a_file_that_only_differs_in_its_wiki_commit():
    """write_test_case: the same text at a later commit is not a new file
    (its sealed hash, and every compiled workbook's view of it, must hold);
    any other difference is written."""
    import shutil
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp(prefix="render-same-"))
    try:
        path = d / "t.md"

        def render(commit, title="T", status="active"):
            gf = {"prd_versions": {}, "figma_hashes": {}, "wiki_commit": commit,
                  "generator_version": "1.0.0"}
            fm = {"type": "Test Case", "id": "t", "title": title,
                  "status": status, "generated_from": gf}
            body = ("# Steps\n\n1. Quote ' · wiki abc1234' in a step.\n\n"
                    f"# Traceability\n\n- Scenario: SC · "
                    f"{render_sit.trace_source(gf)}\n")
            return render_sit.write_test_case(path, fm, body)
        assert render("abc1234") is True, "a new file is written"
        first = path.read_bytes()
        assert render("abc1234") is False, "identical text: nothing to write"
        assert path.read_bytes() == first
        assert render("def5678") is False, "same text, later commit: left alone"
        assert path.read_bytes() == first and b"wiki_commit: abc1234" in first
        assert render("def5678", title="T2") is True, "changed text is written"
        second = path.read_bytes()
        assert b"wiki_commit: def5678" in second and b"wiki def5678\n" in second
        assert b"' \xc2\xb7 wiki abc1234' in a step" in second, \
            "only the Traceability tail carries the commit"
        assert render("0000000", title="T2", status="stale") is True, \
            "a status change is a change"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_uat_engine_uses_the_same_two_functions():
    assert render_uat.provenance is render_sit.provenance
    assert render_uat.trace_source is render_sit.trace_source


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_render_prd_versions OK")
