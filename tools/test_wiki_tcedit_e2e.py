#!/usr/bin/env python3
"""End-to-end tests for `wiki tc edit` (run: py tools/test_wiki_tcedit_e2e.py).

The command renders, seals and commits, so it can never be pointed at this
checkout. The tests clone HEAD into a throwaway directory and drive THIS
checkout's tools/wiki.py at the clone through TC_ROOT_OVERRIDE (plus the two
spec-dir overrides, because the renderers look for specs beside their own
code). Every git write therefore lands in the clone.

Slow by nature (one clone, three renders): smoke runs it in the full tier only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import yaml

SIT_SPECS = sorted((ROOT / "tools/sit_specs").glob("*.yaml"))
UAT_SPECS = sorted((ROOT / "tools/uat_specs").glob("*.yaml"))
SCRATCH = None


def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd or SCRATCH, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _env():
    return dict(os.environ, TC_ROOT_OVERRIDE=str(SCRATCH),
                TC_SIT_SPEC_DIR=str(SCRATCH / "tools/sit_specs"),
                TC_UAT_SPEC_DIR=str(SCRATCH / "tools/uat_specs"))


def _edit(tc_id, field, text):
    """Run the real CLI against the scratch clone. Returns (rc, output)."""
    src = SCRATCH / "build/edits/test.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(text.encode("utf-8"))
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/wiki.py"), "tc", "edit", tc_id,
         "--field", field, "--from", "build/edits/test.txt", "--by", "tester"],
        cwd=SCRATCH, env=_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def _first_sit():
    """(tc id, spec path in the scratch, the spec as committed at HEAD) for the
    first SIT entry. The id comes from the manifest binding of the entry's
    scenario id - the same lookup the command uses."""
    import render_sit
    spec_path = SCRATCH / "tools/sit_specs" / SIT_SPECS[0].name
    spec = yaml.safe_load(SIT_SPECS[0].read_text(encoding="utf-8"))
    tc = spec["test_cases"][0]
    sc = spec["scenario_id"].format(ac=tc["ac"], seq=tc["seq"],
                                    ac_id=render_sit.ac_id_of(spec, tc["ac"]))
    manifest = json.loads((SCRATCH / "manifest.json").read_text(encoding="utf-8"))
    return Path(manifest["bindings"][sc]["tc"]).name, spec_path, spec


def test_sit_edit_lands_in_the_spec_renders_and_commits_once():
    tc_id, spec_path, spec = _first_sit()
    before_raw = spec_path.read_bytes()
    before_head = _git("rev-parse", "HEAD").strip()
    new = "1. Open the portal.\r\n2. Click **Login**.  \n"
    rc, out = _edit(tc_id, "steps", new)
    assert rc == 0, out
    after = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    want = dict(spec["test_cases"][0], steps="1. Open the portal.\n2. Click **Login**.")
    assert after["test_cases"][0] == want, after["test_cases"][0]
    assert after["test_cases"][1:] == spec["test_cases"][1:], "another entry changed"
    assert {k: v for k, v in after.items() if k != "test_cases"} == \
        {k: v for k, v in spec.items() if k != "test_cases"}
    assert spec_path.read_bytes() != before_raw
    tc_file = SCRATCH / spec["out"] / f"{tc_id}.md"
    assert "1. Open the portal.\n2. Click **Login**.\n" in \
        tc_file.read_text(encoding="utf-8"), "rendered file lacks the new text"
    assert _git("rev-list", "--count", f"{before_head}..HEAD").strip() == "1", \
        "an edit is exactly one commit"
    assert _git("log", "-1", "--format=%an <%ae>|%s").strip() == \
        f"tc-agent <tc-agent@internal>|tc edit({tc_id}): steps by tester"
    assert _git("status", "--porcelain").strip() == "", "tree not clean after edit"
    assert f"**TC edit (tester)**: {tc_id} steps" in \
        (SCRATCH / "log.md").read_text(encoding="utf-8")
    assert not (SCRATCH / "build/edits/test.txt").exists(), "transport file left behind"
    # One edit changes one test case. The forced render leaves every other
    # file of the story as it was (it would only differ in the wiki commit it
    # was rendered at), so one sealed hash moves and a compiled workbook marks
    # one row, not the whole story.
    touched = [n for n in _git("show", "--format=", "--name-only", "HEAD").splitlines()
               if n.startswith("testcases/") and not n.endswith("index.md")]
    assert touched == [f"{spec['out'].strip('/')}/{tc_id}.md"], touched
    was = json.loads(_git("show", f"{before_head}:manifest.json"))["tc_hashes"]
    now = json.loads((SCRATCH / "manifest.json").read_text(encoding="utf-8"))["tc_hashes"]
    assert sorted(r for r in now if now[r] != was.get(r)) == \
        [f"{spec['out'].strip('/')}/{tc_id}"], "one edit must change one sealed hash"


def test_edit_never_touches_confidence_or_remarks():
    tc_id, spec_path, spec = _first_sit()
    after = yaml.safe_load(spec_path.read_text(encoding="utf-8"))["test_cases"][0]
    assert after["confidence"] == spec["test_cases"][0]["confidence"]
    assert after.get("remarks") == spec["test_cases"][0].get("remarks")


def test_refusal_from_the_renderer_restores_the_spec_and_leaves_a_clean_tree():
    tc_id, spec_path, _spec = _first_sit()
    before_raw = spec_path.read_bytes()
    before_head = _git("rev-parse", "HEAD").strip()
    # a rule only the renderer knows: the refusal comes after the spec write
    rc, out = _edit(tc_id, "pre_extra", "1. a numbered extra")
    assert rc == 1, out
    assert "tc edit refused" in out and "pre_extra must NOT be numbered" in out, out
    assert spec_path.read_bytes() == before_raw, "spec not restored byte for byte"
    assert _git("rev-parse", "HEAD").strip() == before_head, "a refusal committed"
    assert _git("status", "--porcelain").strip() == "", "refusal left a dirty tree"


def test_cheap_refusals_write_nothing():
    tc_id, spec_path, _spec = _first_sit()
    before_raw = spec_path.read_bytes()
    for target, field, text, needle in (
            (tc_id, "confidence", "High", "is not editable on a SIT test case"),
            (tc_id, "ac", "HS-99", "is not editable on a SIT test case"),
            ("9.9-AC99-99", "steps", "1. x", "not found"),
            (tc_id, "priority", "P9", "is not one of"),
            (tc_id, "title", "", "cannot be empty"),
            (tc_id, "title", "two\nlines", "must be one line"),
            (tc_id, "pre_extra", "two\nlines", "pre_extra must be one line"),
            (tc_id, "steps", "x" * 20001, "the limit is 20000")):
        rc, out = _edit(target, field, text)
        assert rc == 1 and needle in out, (target, field, out)
    assert spec_path.read_bytes() == before_raw
    assert _git("status", "--porcelain").strip() == ""


def test_unchanged_text_is_a_no_op_not_a_commit():
    tc_id, spec_path, _spec = _first_sit()
    current = yaml.safe_load(spec_path.read_text(encoding="utf-8"))["test_cases"][0]["title"]
    before_head = _git("rev-parse", "HEAD").strip()
    rc, out = _edit(tc_id, "title", current)
    assert rc == 0 and "unchanged" in out, out
    assert _git("rev-parse", "HEAD").strip() == before_head


def test_retired_test_case_is_refused():
    tc_id, _spec_path, spec = _first_sit()
    tc_file = SCRATCH / spec["out"] / f"{tc_id}.md"
    raw = tc_file.read_bytes()
    tc_file.write_bytes(raw.replace(b"\nstatus: active\n", b"\nstatus: retired\n", 1))
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "is retired" in out, out
    finally:
        tc_file.write_bytes(raw)
    assert _git("status", "--porcelain").strip() == ""


def test_a_stale_sibling_is_refused_so_an_edit_never_clears_a_stale_flag():
    """The forced render rewrites EVERY test case of the story as active. An
    edit to one test case must not quietly resolve another one's staleness."""
    tc_id, _spec_path, spec = _first_sit()
    siblings = sorted(p for p in (SCRATCH / spec["out"]).glob("*.md")
                      if p.name not in ("index.md", f"{tc_id}.md"))
    if not siblings:
        print("[SKIP] stale sibling: the spec renders a single test case")
        return
    raw = siblings[0].read_bytes()
    siblings[0].write_bytes(raw.replace(b"\nstatus: active\n", b"\nstatus: stale\n", 1))
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "are stale" in out and siblings[0].stem in out, out
    finally:
        siblings[0].write_bytes(raw)
    assert _git("status", "--porcelain").strip() == ""


def test_hand_edit_drift_on_the_story_is_refused():
    tc_id, _spec_path, spec = _first_sit()
    tc_file = SCRATCH / spec["out"] / f"{tc_id}.md"
    raw = tc_file.read_bytes()
    tc_file.write_bytes(raw + b"\nhand edit\n")
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "hand-edit drift" in out, out
    finally:
        tc_file.write_bytes(raw)


def test_dirty_tree_is_refused():
    tc_id, _spec_path, _spec = _first_sit()
    stray = SCRATCH / "stray.txt"
    stray.write_text("x", encoding="utf-8")
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "working tree is dirty" in out, out
    finally:
        stray.unlink()


def test_uat_edit_and_uat_data_refusal():
    if not UAT_SPECS:
        print("[SKIP] test_uat_edit_and_uat_data_refusal: no tools/uat_specs/*.yaml")
        return
    spec_path = SCRATCH / "tools/uat_specs" / UAT_SPECS[0].name
    spec = yaml.safe_load(UAT_SPECS[0].read_text(encoding="utf-8"))
    jid = next(iter(spec["entries"]))
    manifest = json.loads((SCRATCH / "manifest.json").read_text(encoding="utf-8"))
    tc_rel = manifest["bindings"][spec["scenario_id"].format(jid=jid)]["tc"]
    tc_id = Path(tc_rel).name
    rc, out = _edit(tc_id, "data", "**Field** = value")
    assert rc == 1 and "is not editable on a UAT test case" in out, out
    rc, out = _edit(tc_id, "title", "A reworded journey title")
    assert rc == 0, out
    after = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert after["entries"][jid] == dict(spec["entries"][jid],
                                         title="A reworded journey title")
    assert {k: v for k, v in after["entries"].items() if k != jid} == \
        {k: v for k, v in spec["entries"].items() if k != jid}
    assert "title: A reworded journey title\n" in \
        (SCRATCH / (tc_rel + ".md")).read_text(encoding="utf-8")
    assert _git("log", "-1", "--format=%s").strip() == \
        f"tc edit({tc_id}): title by tester"
    assert _git("status", "--porcelain").strip() == ""


def test_field_outside_the_kind_is_refused_before_any_write():
    tc_id, spec_path, _spec = _first_sit()
    before_raw = spec_path.read_bytes()
    for field in ("seq", "remarks", "confidence"):
        rc, out = _edit(tc_id, field, "x")
        assert rc == 1 and "is not editable on a SIT test case" in out, (field, out)
    assert spec_path.read_bytes() == before_raw
    assert _git("status", "--porcelain").strip() == ""


def test_edit_file_under_build_edits_is_deleted_on_refusal_and_outside_is_kept():
    tc_id, _spec_path, _spec = _first_sit()
    inside = SCRATCH / "build/edits/test.txt"
    rc, out = _edit(tc_id, "confidence", "High")
    assert rc == 1 and not inside.exists(), "edit file left behind after a refusal"
    outside = SCRATCH.parent / "outside.txt"
    outside.write_text("1. x", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/wiki.py"), "tc", "edit", tc_id,
         "--field", "confidence", "--from", str(outside), "--by", "tester"],
        cwd=SCRATCH, env=_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    assert r.returncode == 1 and outside.exists(), "a file outside build/edits was deleted"


def test_nul_character_is_refused():
    tc_id, spec_path, _spec = _first_sit()
    before_raw = spec_path.read_bytes()
    rc, out = _edit(tc_id, "steps", "1. a\x00b")
    assert rc == 1 and "NUL" in out, out
    assert spec_path.read_bytes() == before_raw
    assert _git("status", "--porcelain").strip() == ""


def test_yaml_parse_error_in_the_spec_is_a_refusal_not_a_traceback():
    tc_id, spec_path, _spec = _first_sit()
    raw = spec_path.read_bytes()
    spec_path.write_bytes(raw + b"\n  - : [unclosed\n")
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "tc edit refused" in out, out
        assert "Traceback" not in out, out
    finally:
        spec_path.write_bytes(raw)
    assert _git("status", "--porcelain").strip() == ""


def _uat_tc_file():
    if not UAT_SPECS:
        return None
    spec = yaml.safe_load(UAT_SPECS[0].read_text(encoding="utf-8"))
    jid = next(iter(spec["entries"]))
    manifest = json.loads((SCRATCH / "manifest.json").read_text(encoding="utf-8"))
    rel = manifest["bindings"][spec["scenario_id"].format(jid=jid)]["tc"]
    return SCRATCH / (rel + ".md")


def test_drift_in_another_story_is_refused_because_the_seal_is_repo_wide():
    """seal re-hashes EVERY test case, so a committed hand edit anywhere would be
    sealed into the tc edit commit, clearing W4 without release / revert."""
    other = _uat_tc_file()
    if other is None:
        print("[SKIP] drift elsewhere: no tools/uat_specs/*.yaml")
        return
    tc_id, _spec_path, _spec = _first_sit()
    raw = other.read_bytes()
    other.write_bytes(raw + b"\nhand edit elsewhere\n")
    _git("add", "-A")      # a COMMITTED hand edit: the tree is clean, W4 drift remains
    _git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "test: hand edit")
    head = _git("rev-parse", "HEAD").strip()
    try:
        rc, out = _edit(tc_id, "steps", "1. x")
        assert rc == 1 and "hand-edit drift" in out and other.stem in out, out
        assert _git("rev-parse", "HEAD").strip() == head, "an edit committed over drift"
    finally:
        other.write_bytes(raw)
        _git("add", "-A")
        _git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "test: hand edit undone")
    assert _git("status", "--porcelain").strip() == ""


def _hook(name, body):
    path = SCRATCH / ".git/hooks" / name
    path.write_bytes(("#!/bin/sh\n" + body + "\n").encode("utf-8"))
    return path


def test_refusal_after_the_render_restores_every_file_it_wrote():
    """A pre-commit hook fails the commit AFTER render, index, seal, log and
    git add have all run: the roll-back must undo every one of them,
    including a stale index.md that `index` regenerated."""
    tc_id, spec_path, spec = _first_sit()
    out_dir = SCRATCH / spec["out"]
    stale = [SCRATCH / "index.md", SCRATCH / "testcases/index.md"]
    originals = {p: p.read_bytes() for p in stale if p.exists()}
    for p in originals:
        p.write_bytes(originals[p] + b"\n<!-- stale -->\n")
    # A per-PRD index is one of the files `index` rewrites: a stale one must
    # come back too, or "Nothing was changed" is untrue and the next edit is
    # refused for a dirty tree.
    demo = SCRATCH / "sources/prd/zz-rollback-demo/index.md"
    made = [p for p in (demo.parent.parent, demo.parent) if not p.exists()]
    demo.parent.mkdir(parents=True, exist_ok=True)
    demo.write_bytes(b"# stale per-PRD index\n")
    originals[demo] = None
    _git("add", "-A")
    _git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "test: stale indexes")
    head = _git("rev-parse", "HEAD").strip()
    watched = [spec_path, SCRATCH / "manifest.json", SCRATCH / "log.md",
               out_dir / f"{tc_id}.md", *originals]
    before = {p: p.read_bytes() for p in watched}
    hook = _hook("pre-commit", "exit 1")
    try:
        rc, out = _edit(tc_id, "steps", "1. a change that renders")
        assert rc == 1 and "commit did not go through" in out, out
        assert "Nothing was changed" in out, out
    finally:
        hook.unlink()
    for p in watched:
        assert p.read_bytes() == before[p], f"{p.name} not restored byte for byte"
    assert _git("rev-parse", "HEAD").strip() == head
    assert _git("status", "--porcelain").strip() == "", "refusal left a dirty tree"
    assert demo.read_bytes() == b"# stale per-PRD index\n"
    for p in originals:      # put the scratch back as it was
        if originals[p] is None:
            p.unlink()
        else:
            p.write_bytes(originals[p])
    for d in reversed(made):
        shutil.rmtree(d, ignore_errors=True)
    _git("add", "-A")
    _git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "test: indexes back")


def test_a_commit_that_went_through_is_success_even_if_the_tree_is_dirty_after():
    tc_id, spec_path, _spec = _first_sit()
    head = _git("rev-parse", "HEAD").strip()
    hook = _hook("post-commit", "echo x > stray-from-hook.txt")
    stray = SCRATCH / "stray-from-hook.txt"
    try:
        rc, out = _edit(tc_id, "steps", "1. committed then dirty")
        assert rc == 0 and "saved by tester" in out, out
        assert _git("rev-list", "--count", f"{head}..HEAD").strip() == "1"
        assert "1. committed then dirty" in spec_path.read_text(encoding="utf-8"), \
            "a committed edit was rolled back"
    finally:
        hook.unlink()
        stray.unlink(missing_ok=True)
    assert _git("status", "--porcelain").strip() == ""


def test_non_refused_failure_after_the_spec_write_is_rolled_back():
    """OSError (a locked file, a full disk) is not a Refused. Driven in-process
    against the scratch clone: append_log raises after render, index and seal."""
    tc_id, spec_path, spec = _first_sit()
    out_dir = SCRATCH / spec["out"]
    head = _git("rev-parse", "HEAD").strip()
    watched = [spec_path, SCRATCH / "manifest.json", SCRATCH / "log.md",
               out_dir / f"{tc_id}.md"]
    before = {p: p.read_bytes() for p in watched}
    src = SCRATCH / "build/edits/inproc.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"1. never lands")
    code = (
        "import sys; sys.path.insert(0, %r); sys.argv = ['wiki.py']\n"
        "import wiki_tcedit\n"
        "def boom(*a, **k): raise PermissionError('log.md is locked')\n"
        "wiki_tcedit.append_log = boom\n"
        "wiki_tcedit.cmd_tc(['edit', %r, '--field', 'steps', '--from', %r, "
        "'--by', 'tester'])\n" % (str(ROOT / "tools"), tc_id, "build/edits/inproc.txt"))
    r = subprocess.run([sys.executable, "-c", code], cwd=SCRATCH, env=_env(),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = r.stdout + r.stderr
    assert r.returncode not in (0, None) and "restored" in out, out
    assert "Traceback" not in out, out
    for p in watched:
        assert p.read_bytes() == before[p], f"{p.name} not restored byte for byte"
    assert _git("rev-parse", "HEAD").strip() == head
    assert _git("status", "--porcelain").strip() == ""


if __name__ == "__main__":
    if not SIT_SPECS:
        print("[SKIP] test_wiki_tcedit_e2e: bundle has no tools/sit_specs/*.yaml "
              "to edit (this is the base branch's normal state)")
        sys.exit(0)
    tmp = Path(tempfile.mkdtemp(prefix="tcedit-"))
    SCRATCH = tmp / "repo"
    try:
        _git("clone", "-q", str(ROOT), str(SCRATCH), cwd=tmp)
        _git("config", "user.name", "tc-agent")
        _git("config", "user.email", "tc-agent@internal")
        # Hermetic: never inherit the machine's global commit.gpgsign.
        _git("config", "commit.gpgsign", "false")
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn) and all(a in name for a in sys.argv[1:]):
                fn()
                print(f"[PASS] {name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("test_wiki_tcedit_e2e OK")
