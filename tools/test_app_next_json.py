#!/usr/bin/env python3
"""Plain-assert tests for `wiki next --json` (run: py tools/test_app_next_json.py).
Matches the tools/smoke.py idiom -- no pytest in this repo.

Read-only: collect_next never writes, so these run against the real wiki.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki_next import collect_next
from testkit import SkipTest, need, skip_if_empty


def test_collect_next_shape():
    out = collect_next([])
    assert set(out) == {"banners", "rows", "phase"}, out.keys()
    assert isinstance(out["rows"], list) and out["rows"], "expected at least one row"
    for r in out["rows"]:
        assert set(r) == {"id", "state", "command", "skill", "scope", "arg", "also"}, r
        assert isinstance(r["id"], str) and r["id"]
        assert isinstance(r["state"], str) and r["state"]
        assert r["command"] is None or isinstance(r["command"], str)
        assert isinstance(r["skill"], str) and r["skill"]
        assert r["scope"] in ("story", "flow"), r
        assert isinstance(r["arg"], str) and r["arg"]


def test_flow_row_arg_is_the_file_stem_not_the_row_id():
    """actions.build's gate --flow keys on the flow's file stem (e.g.
    "example-module-e2e"), which is neither the row id (e.g.
    "FLOW-example-module") nor derivable from it -- the read model
    must carry it explicitly."""
    need("Flow")
    flow_rows = [r for r in collect_next([])["rows"] if r["scope"] == "flow"]
    assert flow_rows, "bundle has Flow concepts but next emitted no flow row"
    from wiki import read_concept
    for r in flow_rows:
        assert isinstance(r["arg"], str) and r["arg"]
        # The contract is "arg IS the file stem", not "arg differs from id":
        # a project may name flows/<id>.md after the id, and then the two
        # coincide legitimately. Check the stem resolves to this flow's file.
        fm, _ = read_concept(ROOT / "flows" / f"{r['arg']}.md")
        assert fm and fm.get("id") == r["id"], (r, fm)


def test_story_filter_narrows_rows():
    """Discover the story from the bundle: a hardcoded id only ever held on
    the branch it was written against."""
    story = next((r for r in collect_next([])["rows"] if r["scope"] == "story"), None)
    if story is None:
        raise SkipTest("bundle has no story row to filter on")
    out = collect_next(["--story", story["arg"]])
    assert [r["id"] for r in out["rows"]] == [story["id"]], out["rows"]


def test_brief_matches_full_rows():
    """--brief only skips the drift banner scan; rows must be identical."""
    assert collect_next(["--brief"])["rows"] == collect_next([])["rows"]


def test_json_flag_emits_parseable_json():
    r = subprocess.run([sys.executable, str(ROOT / "tools/wiki.py"), "next", "--json"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["rows"], "no rows in --json output"


def test_text_output_still_works():
    r = subprocess.run([sys.executable, str(ROOT / "tools/wiki.py"), "next"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "skill:" in r.stdout, r.stdout


def test_flow_command_names_a_file_that_exists():
    """The command `next` prints must be runnable as printed: the script it
    names has to exist. A hard-coded per-flow script name pointed at a file
    this bundle never had."""
    import re
    need("Flow")
    for r in collect_next([])["rows"]:
        if r["scope"] != "flow" or not r["command"]:
            continue
        for script in re.findall(r"py (tools/[\w./-]+\.py)", r["command"]):
            assert (ROOT / script).exists(), (script, r)


def test_flow_render_command_uses_the_flow_id_not_the_file_stem():
    """render_uat.py --flow and tools/uat_specs/<X>.yaml key on the FLOW ID.
    A flow whose file stem differs from its id (flows/<name>-e2e.md holding
    FLOW-<name>) must still print `--flow FLOW-<name>`. The synthetic half
    feeds collect_next such a flow and needs no project content."""
    import re
    import wiki_next
    fm = {"id": "FLOW-demo", "type": "Flow", "status": "aligned", "stories": [],
          "journey": [{"id": "J01"}]}
    real = wiki_next.all_concepts, wiki_next.load_manifest
    wiki_next.all_concepts = lambda: [("flows/demo-e2e.md", fm, "", None)]
    wiki_next.load_manifest = lambda: {"concepts": {}, "tc_hashes": {}}
    try:
        row = next(r for r in collect_next(["--brief"])["rows"] if r["scope"] == "flow")
    finally:
        wiki_next.all_concepts, wiki_next.load_manifest = real
    assert row["arg"] == "demo-e2e", row  # gate --flow keeps the file stem
    flag = re.search(r"--flow (\S+)", row["command"])
    assert flag and flag.group(1) == "FLOW-demo", row["command"]
    # live rows: the printed --flow value is the row's flow id, and a row that
    # tells the author to re-render existing UAT test cases names a spec file
    # that exists.
    if not any(r["scope"] == "flow" for r in collect_next([])["rows"]):
        print("[SKIP-REASON] no Flow concept in this checkout; live-row half skipped")
        return
    for r in collect_next([])["rows"]:
        if r["scope"] != "flow" or not r["command"]:
            continue
        m = re.search(r"render_uat\.py --flow (\S+)", r["command"])
        if not m:
            continue
        assert m.group(1) == r["id"], (m.group(1), r)
        if "--force" in r["command"]:
            assert (ROOT / "tools" / "uat_specs" / f"{m.group(1)}.yaml").exists(), r


if __name__ == "__main__":
    skip_if_empty("unit: next --json")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except SkipTest as e:
                print(f"[SKIP] {name}: {e}")
                continue
            print(f"[PASS] {name}")
    print("test_app_next_json OK")
