#!/usr/bin/env python3
"""Smoke test for the tc-copilot bundle.

Run: py tools/smoke.py            full run (~1 min)
     py tools/smoke.py --fast     skip xlsx compiles + Node graph bake (~15s)

Verifies the deterministic invariants without mutating the wiki:
  1. manifest rebuilds cleanly from frontmatter
  2. all index.md files regenerate
  3. lint has zero L errors
  4. the generation gate opens for every aligned story and the aligned journey flow
  5. re-rendering an unchanged wiki touches zero SIT/UAT TC files (byte-stability, spec §18-1)
  6. the confirmed coverage map renders and the golden SIT set is fully matched (missing=0)
  7. suite export compiles and writes only under build/

Exits non-zero on the first failure. Leaves the repo exactly as found
(uses git to detect and revert incidental writes under testcases/).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

FAST = "--fast" in sys.argv

# ---- what this bundle actually contains ------------------------------------
# Everything below is DISCOVERED, never named: smoke has to hold for whatever
# project this repo is checked out as, not just the one it was written
# against. A bundle that has none of a given thing [SKIP]s that step instead
# of failing — an empty base branch is a valid state, not a broken one.
#
# The rule, same as tools/testkit.py: skip on "this bundle has no such thing",
# never on "the assertion failed". Nothing here can mask a real regression in
# a populated bundle, because presence is what is being tested, not outcome.

# Every scope that has a SIT render spec — the driver is shared, so this is the
# whole SIT surface.
SIT_STORIES = sorted(p.stem for p in (ROOT / "tools/sit_specs").glob("*.yaml"))
# Per-flow UAT run-records (the reusable protocol is the tc-generate-uat skill).
UAT_RENDERERS = sorted(p.relative_to(ROOT).as_posix()
                       for p in (ROOT / "tools").glob("render_*_uat.py"))
SUITES = sorted(p.stem for p in (ROOT / "suites").glob("*.yaml")) \
    if (ROOT / "suites").exists() else []
FLOW_FILES = sorted(p for p in (ROOT / "flows").glob("*.md")
                    if p.name != "index.md") if (ROOT / "flows").exists() else []


def stories_with(token):
    """Story ids whose file carries `token` (e.g. 'coverage_status: confirmed').
    A grep, deliberately: smoke shells out to the CLI rather than importing the
    wiki, so it stays a black-box check of the shipped commands."""
    out = []
    for p in sorted((ROOT / "stories").glob("*.md")) if (ROOT / "stories").exists() else []:
        if p.name == "index.md":
            continue
        if token in p.read_text(encoding="utf-8"):
            out.append(p.stem)
    return out

def run(args, expect=0, name="", env=None):
    e = None
    if env:
        import os
        e = {**os.environ, **env}
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True, env=e)
    ok = (r.returncode == expect)
    print(f"[{'PASS' if ok else 'FAIL'}] {name or ' '.join(args)}")
    if not ok:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        sys.exit(1)
    return r.stdout + r.stderr

def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT,
                          capture_output=True, text=True).stdout

def rendered_line(out):
    """The 'rendered N, ...' summary line, wherever it falls among any
    SUPPRESSED preamble lines a renderer may print first."""
    return next((ln for ln in out.splitlines() if ln.startswith("rendered ")), None)

dirty_before = git("status", "--porcelain")
if dirty_before.strip():
    sys.exit("smoke: working tree not clean — commit or stash first.\n" + dirty_before)

run(["tools/wiki.py", "manifest", "--no-commit"], name="manifest rebuild")
run(["tools/wiki.py", "index", "--no-commit"], name="index regenerate")
run(["tools/wiki.py", "lint", "--no-commit"], name="lint (0 L errors)")

# gates: aligned stories open, others blocked
status = run(["tools/wiki.py", "status"], name="status")
for line in status.splitlines():
    parts = line.split()
    if not parts or not parts[0].startswith("US-"):
        continue
    sid, sstatus = parts[0], parts[1]
    run(["tools/wiki.py", "gate", "--story", sid],
        expect=0 if sstatus == "aligned" else 1,
        name=f"gate {sid} ({'open' if sstatus == 'aligned' else 'blocked'} expected)")

# flow gate: an aligned journey opens generation (expect OPEN), others blocked
if not FLOW_FILES:
    print("[SKIP] flow gate: bundle has no flows")
for _p in FLOW_FILES:
    _aligned = "status: aligned" in _p.read_text(encoding="utf-8")
    run(["tools/wiki.py", "gate", "--flow", _p.stem],
        expect=0 if _aligned else 1,
        name=f"gate flow {_p.stem} ({'open' if _aligned else 'blocked'} expected)")

# SIT byte-stability: re-render must touch nothing on an unchanged wiki
if not SIT_STORIES:
    print("[SKIP] SIT byte-stability: bundle has no tools/sit_specs/*.yaml")
else:
    for story in SIT_STORIES:
        out = run(["tools/render_sit.py", "--story", story],
                  name=f"re-render SIT (unchanged wiki): {story}")
        line = rendered_line(out)
        if not line or not line.startswith("rendered 0"):
            print("[FAIL] SIT byte-stability: renderer rewrote files on an unchanged wiki:", out)
            sys.exit(1)
    print("[PASS] SIT byte-stability: rendered 0, all TC files untouched")

# UAT byte-stability: the journey UAT re-render must also touch nothing
if not UAT_RENDERERS:
    print("[SKIP] UAT byte-stability: bundle has no tools/render_*_uat.py")
else:
    for _r in UAT_RENDERERS:
        out = run([_r], name=f"re-render UAT (unchanged wiki): {Path(_r).stem}")
        line = rendered_line(out)
        if not line or not line.startswith("rendered 0"):
            print("[FAIL] UAT byte-stability:", out)
            sys.exit(1)
    print("[PASS] UAT byte-stability")

# --- enforced fences: these must REFUSE, not merely be documented -----------
# These fences are the platform's core safety properties, so a bundle that
# cannot exercise one says so LOUDLY rather than passing quietly.
#
# The SIT and card fences are fixture-backed and run in EVERY bundle. The other
# two cannot be: the seal fence refuses when TC files are unsealed, and an
# empty bundle has no TC files to leave unsealed; the UAT fence needs a
# per-flow UAT run-record, which each project authors via tc-generate-uat.
# Both are content-dependent by construction, not by oversight -- faking
# content into the tracked wiki to satisfy them would be worse than saying so.
_fence_skips = []

# Self-contained: the spec and the draft story it points at both live under
# tools/fixtures/sit_specs_gate/, so this proves the fence in any bundle.
_fence_story = next((p.stem for p in
                     sorted((ROOT / "tools/fixtures/sit_specs_gate").glob("*.yaml"))), None)
if _fence_story is None:
    _fence_skips.append("SIT coverage fence (no fixture spec)")
else:
    out = run(["tools/render_sit.py", "--story", _fence_story], expect=1,
              env={"TC_SIT_SPEC_DIR": "tools/fixtures/sit_specs_gate"},
              name="coverage fence: render refuses unconfirmed coverage_status")
    assert "REFUSED" in out and "coverage_status" in out, out

if not UAT_RENDERERS:
    _fence_skips.append("UAT coverage fence (no tools/render_*_uat.py)")
else:
    out = run([UAT_RENDERERS[0]], expect=1,
              env={"TC_UAT_FIXTURE_DIR": "tools/fixtures/uat_flow_gate"},
              name="UAT coverage fence: render refuses an unconfirmed member story")
    assert "render UAT REFUSED" in out, out

if not SUITES:
    _fence_skips.append("seal fence (no suites/*.yaml, and no TC files to "
                        "leave unsealed)")
else:
    out = run(["tools/wiki.py", "suite", "compile", SUITES[0], "--no-commit"], expect=1,
              env={"TC_MANIFEST_OVERRIDE": "tools/fixtures/unsealed_manifest.json"},
              name="seal fence: suite compile refuses when TCs are not sealed")
    assert "not sealed" in out, out

# The card fences run in EVERY bundle: cmd_assert checks --card before it ever
# loads the story, so proving the refusal needs an id, not a real story. An
# id that cannot exist keeps this from touching project content at all.
#
# The wrong-scope card is SYNTHESISED here rather than read from build/cards/:
# build/ is git-ignored, so depending on a leftover there made this step pass
# only on a working copy that had already run a session -- a fresh clone
# would have failed it.
_story = "US-SMOKE-FENCE-PROBE"
out = run(["tools/wiki.py", "assert", "story", _story, "--by", "smoke",
           "--no-commit"], expect=1,
          name="card fence: assert story refuses without --card")
assert "--card <path> is required" in out, out

_wrong = ROOT / "build/cards/smoke-wrong-scope.json"
_wrong.parent.mkdir(parents=True, exist_ok=True)
# `story` is the field cmd_assert compares against (basename-wise); a value
# that cannot equal the story under test is the whole point of the fixture.
_wrong.write_text(json.dumps(
    {"id": "session-SMOKE-WRONG-SCOPE-001",
     "story": "stories/US-SMOKE-NOT-THIS-STORY",
     "human_response": None}),
    encoding="utf-8", newline="\n")
try:
    out = run(["tools/wiki.py", "assert", "story", _story, "--by", "smoke",
               "--card", _wrong.relative_to(ROOT).as_posix(), "--no-commit"],
              expect=1,
              name="card fence: assert story refuses a card for another scope")
    assert "wrong card" in out, out
finally:
    _wrong.unlink(missing_ok=True)

for _s in _fence_skips:
    print(f"[SKIP] {_s} -- NOT VERIFIED in this bundle")

run(["tools/wiki.py", "next"], name="next (advisor renders)")
run(["tools/wiki.py", "next", "--brief"], name="next --brief")

run(["tools/wiki.py", "rtm", "--no-commit"], name="rtm build (matrix/graph/gaps)")
for f in ("matrix.md", "graph.json", "gaps.md"):
    if not (ROOT / "build/rtm" / f).exists():
        print(f"[FAIL] rtm output missing: build/rtm/{f}")
        sys.exit(1)

# coverage-first invariants: confirmed map renders, and the golden SIT set is
# fully matched (eval_golden reports and exits 0 when the project has no
# golden workbook of its own — it is calibration, not a gate).
_confirmed = stories_with("coverage_status: confirmed")
if not _confirmed:
    print("[SKIP] coverage diagram: no story with coverage_status: confirmed")
# Every confirmed story, not a representative one: picking the first would
# silently stop checking the others as a project grows.
for _s in _confirmed:
    run(["tools/wiki.py", "coverage", "--story", _s, "--no-commit"],
        name=f"coverage diagram ({_s})")
run(["tools/eval_golden.py", "--strict"], name="golden eval (SIT missing=0)")
run(["tools/test_wiki_seal.py"], name="unit: unsealed-TC check")
run(["tools/test_wiki_triage.py"], name="unit: intake triage classifier")
run(["tools/test_docx_stream.py"], name="unit: docx PRD stream + chunking")
run(["tools/test_wiki_reference.py"], name="unit: reference material ingest")
run(["tools/test_wiki_l13.py"], name="unit: L13 provenance + W6 token coverage")
run(["tools/test_wiki_provenance.py"], name="unit: provenance backfill")


# ---- end-to-end: intake over a reference dump ------------------------------
# The design's end-to-end case: 17 files -> 20 questions (3 folder + 17 file,
# of which 6 are mandatory: 3 folders + 3 loose top-level files) -> all 17
# routed -> ingest-reference -> sources/prd/ untouched by the interface spec.
#
# The dump is SYNTHETIC and lives under a throwaway root in build/, driven
# through TC_ROOT_OVERRIDE. The repo's own PUT_FILES_HERE/ holds the user's
# files and is never read, moved or written here.
def _intake_end_to_end():
    import shutil as _sh
    sroot = ROOT / "build/_smoke_intake"
    if sroot.exists():
        _sh.rmtree(sroot)
    dump = sroot / "PUT_FILES_HERE"
    rels = ["interface-spec.docx", "test-cases.xlsx", "coverage-matrix.xlsx"]
    rels += [f"L/L/control/rule-{i}.yml" for i in range(1, 7)]
    rels += [f"L/L/data/rule-{i}.yml" for i in range(1, 7)]
    rels += ["L/L/control-config.yml", "L/L/data-config.yml"]
    assert len(rels) == 17, rels
    # Real .docx / .xlsx, not stubs: ingest-reference refuses a document whose
    # reader fails, so a fake one would prove nothing about the happy path.
    for rel in rels:
        p = dump / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".docx"):
            from docx import Document as _Docx
            _d = _Docx()
            _d.add_heading("Interface Specification", level=1)
            _d.add_paragraph("Field layout for the inbound file.")
            _d.save(str(p))
        elif rel.endswith(".xlsx"):
            import openpyxl as _xl
            _wb = _xl.Workbook()
            _ws = _wb.active
            _ws.title = "Cases"
            _ws.append(["ID", "Title"])
            _ws.append(["TC-1", rel])
            _wb.save(str(p))
        else:
            p.write_text(f"# {rel}\nkey: value\n", encoding="utf-8",
                         newline="\n")
    (sroot / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "adopted_prd_version": None,
                    "staged_prd_version": None, "id_config_frozen": False,
                    "counters": {}, "sources": {}, "concepts": {},
                    "bindings": {}, "tc_hashes": {}, "edges": []}),
        encoding="utf-8", newline="\n")
    env = {"TC_ROOT_OVERRIDE": str(sroot)}

    out = run(["tools/wiki.py", "triage", "--no-commit"],
              name="e2e intake: triage emits a card for 20 questions", env=env)
    assert "20 question(s)" in out, out
    cards = sorted((sroot / "build/cards").glob("triage-*.json"))
    assert len(cards) == 1, cards
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    qs = card["open_questions"]
    folders = [q for q in qs if q["kind"] == "folder"]
    files = [q for q in qs if q["kind"] == "file"]
    assert len(folders) == 3, [q["item"] for q in folders]
    assert len(files) == 17, len(files)
    assert {q["item"] for q in folders} == {"L/L", "L/L/control", "L/L/data"}, \
        [q["item"] for q in folders]
    mandatory = [q for q in qs
                 if q["kind"] == "folder" or "parent" not in q]
    assert len(mandatory) == 6, [q["item"] for q in mandatory]
    assert len({q["id"] for q in qs}) == 20, "question ids must be unique"
    print("[PASS] e2e intake: 3 folder + 17 file questions, 6 mandatory")

    # --apply without the card must refuse: the gate is the whole feature.
    run(["tools/wiki.py", "triage", "--apply", "--no-commit"], expect=1,
        name="e2e intake: --apply without a card refuses", env=env)
    assert len(list(dump.rglob("*.yml"))) == 14, "refusal must move nothing"

    # Answer it through the real verb. The interface spec is proposed `prd`
    # and corrected to `reference` -- an interface specification states no
    # acceptance criteria, so by the project's own rule it is not a PRD.
    spec_q = [q for q in files if q["item"] == "interface-spec.docx"][0]
    assert spec_q["proposed"] == "prd", spec_q
    answers = []
    for q in mandatory:
        value = "reference" if q["id"] == spec_q["id"] else "accept"
        answers += ["--answer", f"{q['id']}={value}"]
    run(["tools/wiki.py", "card", "revise", str(cards[0]), "--by", "smoke",
         *answers, "--no-commit"], name="e2e intake: card revise", env=env)

    out = run(["tools/wiki.py", "triage", "--apply", "--card", str(cards[0]),
               "--no-commit"], name="e2e intake: apply routes all 17", env=env)
    assert "moved 17 file(s)" in out, out
    for rel in rels:
        assert rel in out, (rel, out)
    assert not list(dump.rglob("*.yml")), sorted(dump.rglob("*"))
    assert (sroot / "inputs/reference/L/L/control/rule-1.yml").exists(), out
    assert (sroot / "inputs/reference/interface-spec.docx").exists(), out
    assert not (sroot / "inputs/prd").exists(), \
        "the interface spec must not reach inputs/prd/"
    print("[PASS] e2e intake: 17 files routed, every one reported by name")

    out = run(["tools/wiki.py", "ingest-reference", "--no-commit"],
              name="e2e intake: ingest-reference", env=env)
    assert "reference documents ingested: 17" in out, out
    concepts = sorted((sroot / "sources/reference").glob("*.md"))
    assert len(concepts) == 17, [c.name for c in concepts]
    assert not (sroot / "sources/prd").exists(), \
        "sources/prd/ must be untouched by the interface spec"
    m = json.loads((sroot / "manifest.json").read_text(encoding="utf-8"))
    assert len([k for k in m["sources"] if k.startswith("reference#")]) == 17, \
        sorted(m["sources"])
    assert m["adopted_prd_version"] is None, m
    print("[PASS] e2e intake: 17 reference concepts, sources/prd/ untouched")
    _sh.rmtree(sroot, ignore_errors=True)


_intake_end_to_end()


run(["tools/make_reference_workbooks.py", "--check"],
    name="reference workbooks: regenerated content has no banned string "
         "(public-base scrub)")
run(["tools/test_public_base.py"], name="unit: public-base banned-string sweep")
run(["tools/test_wiki_coverage_fence.py"], name="unit: UAT coverage fence")
run(["tools/test_rubric.py"], name="unit: rubric loader + validator")
run(["tools/test_wiki_rubric.py"], name="unit: test_model + C = N/T arithmetic")
run(["tools/test_render_sit_coverage_items.py"],
    name="unit: coverage_items links TCs to test-model items")
run(["tools/test_render_sit_force.py"],
    name="unit: forced re-render skips a provenance-only change")
run(["tools/test_eval_rubric.py"], name="unit: rubric scoring")
run(["tools/test_rubric_judge.py"], name="unit: judge verdicts, packs, gaps, patch")
run(["tools/test_wiki_export.py"], name="unit: draft/final export, workbook marks, gate")
run(["tools/test_rubric_carry.py"], name="unit: round-N verdict carry-forward")
run(["tools/test_rubric_diff.py"], name="unit: draft -> final diff")
run(["tools/test_pipeline_chain.py"], name="unit: draft-first pipeline chain (synthetic)")
run(["tools/test_wiki_testmodel.py"], name="unit: test-model scaffold, L14/W7, assert-confirm, next")
run(["tools/test_bundle_check.py"], name="unit: viewer bundle freshness")
run(["tools/test_graph_viewer_path.py"], name="unit: in-repo graph viewer path")
run(["tools/test_app_next_json.py"], name="unit: next --json")
run(["tools/test_wiki_next_banners.py"], name="unit: next banners + phase")
run(["tools/test_app_actions.py"], name="unit: app action allowlist")
run(["tools/test_wiki_session.py"], name="unit: wiki session revert")
run(["tools/test_app_sidecar.py"], name="unit: opencode sidecar supervisor")
run(["tools/test_app_read_models.py"], name="unit: app read models")
run(["tools/test_app_watcher.py"], name="unit: app change watcher")
app_http_out = run(["tools/test_app_server.py"], name="unit: app HTTP surface (skips without fastapi)")
if "[SKIP]" not in app_http_out:
    # /api/state, /api/explorer, and /api/inbox are the read-model endpoints
    # the app frontend depends on at boot; assert all three were actually
    # exercised and returned 200, not just that the file's exit code was 0.
    # No mutating action runs here -- the card-write integration lives in
    # test_wiki_card.py -- so smoke leaves the repo clean.
    assert "[PASS] test_state_endpoint_returns_the_read_model" in app_http_out, app_http_out
    assert "[PASS] test_explorer_endpoint_returns_the_snapshot" in app_http_out, app_http_out
    assert "[PASS] test_inbox_endpoint_returns_cards" in app_http_out, app_http_out
    print("[PASS] app HTTP surface: /api/state, /api/explorer, and /api/inbox all return 200")
    assert "[PASS] test_chat_health_returns_availability" in app_http_out, app_http_out
    print("[PASS] app HTTP surface: /api/chat/health returns 200")

import shutil as _shutil
if _shutil.which("bun"):
    # On Windows, `bun` on PATH resolves to a .CMD shim (npm global install),
    # and subprocess.run(["bun", ...]) without shell=True fails with
    # FileNotFoundError [WinError 2] because CreateProcess does not do the
    # PATHEXT/.cmd resolution cmd.exe does. Route through cmd /c there, same
    # workaround tools/opencode/state.ts uses in the opposite direction for
    # `py`.
    _bun = ["cmd", "/c", "bun"] if sys.platform == "win32" else ["bun"]
    r = subprocess.run(_bun + ["test"], cwd=ROOT / "tools/opencode",
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[FAIL] opencode plugin unit tests")
        print(r.stdout, r.stderr)
        sys.exit(1)
    print("[PASS] opencode plugin unit tests (bun test)")
    r = subprocess.run(_bun + ["selftest.ts"], cwd=ROOT / "tools/opencode",
                       capture_output=True, text=True)
    if r.returncode != 0 or "SELFTEST OK" not in r.stdout:
        print("[FAIL] opencode plugin selftest")
        print(r.stdout, r.stderr)
        sys.exit(1)
    print("[PASS] opencode plugin selftest (hook wiring)")
else:
    print("[SKIP] opencode plugin tests (bun not on PATH)")

if FAST:
    print("[SKIP] --fast: suite compiles, dashboard, story export, rtm --graph "
          "(xlsx rendering + Node graph bake — the slow ~80%)")
else:
    if not SUITES:
        print("[SKIP] suite compiles: bundle has no suites/*.yaml")
    for _name in SUITES:
        run(["tools/wiki.py", "suite", "compile", _name, "--no-commit"],
            name=f"suite compile {_name}")
    run(["tools/wiki.py", "dashboard", "--no-commit"], name="dashboard build")
    _exportable = SIT_STORIES or stories_with("status: aligned")
    if not _exportable:
        print("[SKIP] story export: bundle has no story to export")
    else:
        # The final export is gated on a current strict score, which a smoke
        # run must not manufacture. The DRAFT export is the ungated first cut;
        # it refuses a set that already has a round score (a graded set is not
        # a first cut), so accept either outcome and assert on the message.
        # The run overwrites <story>-draft.json - the project's real snapshot,
        # which --diff reads - so it is copied aside and restored whatever
        # happens; one the run created is removed.
        import tempfile as _tempfile
        _sid = _exportable[0]
        _snap = ROOT / "build/rubric" / f"{_sid}-draft.json"
        _had = _snap.exists()
        _keep = None
        if _had:
            _fd, _keep = _tempfile.mkstemp(prefix="smoke-draft-", suffix=".json")
            import os as _os
            _os.close(_fd)
            _shutil.copy2(_snap, _keep)
        _graded = any((ROOT / "build/rubric").glob(f"{_sid}-r*-score.json"))
        try:
            _r = subprocess.run([PY, "tools/wiki.py", "export", "--story", _sid,
                                 "--name", "smoke-suite", "--draft", "--no-commit"],
                                cwd=ROOT, capture_output=True, text=True)
            out = _r.stdout + _r.stderr
            if _r.returncode == 0:
                _ok, _what = "DRAFT r0" in out, "writes DRAFT r0"
            else:
                # only a scope with round scores can be refused as graded
                _ok, _what = _graded and "graded in round" in out, "refuses: graded set"
            print(f"[{'PASS' if _ok else 'FAIL'}] story draft export ({_sid}, {_what})")
            if not _ok:
                print(out)
                sys.exit(1)
        finally:
            if _keep:
                _shutil.copy2(_keep, _snap)    # leave the operator's build/ as found
                Path(_keep).unlink(missing_ok=True)
            else:
                _snap.unlink(missing_ok=True)

    # graphs: rtm --graph emits a valid viewer JSON with the new node types
    run(["tools/wiki.py", "rtm", "--graph", "--no-commit"],
        name="rtm --graph emits + validates viewer JSON")
    gj = ROOT / "build/rtm/graphs/rtm.json"
    data = json.loads(gj.read_text(encoding="utf-8"))
    types = {n["nodeType"] for n in data["nodes"]}
    # Business rules live inside stories and resolutions are authored per
    # decision, so an empty bundle emits a valid graph with neither. The
    # emit-and-validate step above is the part that holds for any bundle;
    # asserting on node TYPES needs a bundle that has some.
    if not data["nodes"]:
        print("[SKIP] rtm graph node types: bundle has no concepts to graph")
    else:
        assert "BusinessRule" in types, "rtm graph missing BusinessRule nodes"
        assert "Resolution" in types, "rtm graph missing Resolution nodes"
        print("[PASS] rtm graph has BusinessRule + Resolution nodes")

    # The vendored viewer suite. Guarded like the bun tests above: smoke never
    # becomes JS-runtime-dependent, and ~85s only belongs in the full run.
    if _shutil.which("npm") and (ROOT / "tools/app/web/node_modules").exists():
        _npm = ["cmd", "/c", "npm"] if sys.platform == "win32" else ["npm"]
        r = subprocess.run(_npm + ["test"], cwd=ROOT / "tools/app/web",
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("[FAIL] graph viewer unit tests")
            print(r.stdout, r.stderr)
            sys.exit(1)
        print("[PASS] graph viewer unit tests (npm test)")
    else:
        print("[SKIP] graph viewer unit tests (npm or tools/app/web/"
              "node_modules not present — run: cd tools/app/web && npm ci)")

    # Playwright visual gate: boots the app server and drives a real Chromium
    # browser -- tens of seconds, so it belongs in this full-only tier next to
    # the frontend suite above, not on --fast. Self-skips without its tooling.
    run(["tools/test_app_visual.py"],
        name="visual: operator app renders + styled (skips without playwright)")

dirty_after = git("status", "--porcelain")
extra = [ln for ln in dirty_after.splitlines() if ln.strip()]
if extra:
    print("[FAIL] smoke mutated tracked files:", extra)
    sys.exit(1)
print("[PASS] repo left clean (build/ is git-ignored)")
print("SMOKE OK")
