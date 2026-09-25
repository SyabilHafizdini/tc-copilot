# Draft-First Generation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the SIT/UAT workbook twice (a labelled draft right after the first seal, a graded final with a change log after round 2), and make round 2 re-read only the test cases whose sealed content changed.

**Architecture:** Every new behaviour keys on the manifest's sealed hashes: a per-scope `sealed_digest` over the active test cases is recorded in every score JSON, the draft snapshot and the changes file, and compared by `export`, `--diff` and `wiki next`. Carry-forward copies round N-1 verdicts for test cases whose hash is unchanged into a separate `.carried.json` the engine writes; the diff compares the draft snapshot with the current sealed set by id and field. `cmd_export` moves out of `wiki.py` into a new `tools/wiki_export.py` and gains `--draft`, `--flow`, and the final-export refusal.

**Tech Stack:** Python 3 via the `py` launcher, `openpyxl`, `PyYAML`. No pytest: every test file is a plain-assert script with a `__main__` loop, run by `tools/smoke.py`. Build outputs under git-ignored `build/`; tests redirect `rubric_judge.RUBRIC_BUILD` / `PACK_DIR` / `JUDGMENT_DIR` to a temp dir.

**Spec:** `docs/superpowers/specs/2026-09-25-draft-first-pipeline-design.md` (diagram: `2026-09-25-draft-first-pipeline.html`).

## Global Constraints

- Branch `master`. Commits authored by the repo's git identity (`tc-agent <tc-agent@internal>`, already configured). No AI attribution lines in any commit message.
- `tools/` stays LLM-free and deterministic; same inputs and same files give the same output.
- Never write `status: aligned`, `asserted_by`, `coverage_status: confirmed`, `test_model.status: confirmed` from tooling or tests.
- Never hand-edit `testcases/**`, `manifest.json`, `index.md`, `build/**`. Tests write only under a temp dir or under `build/`.
- Refusals exit non-zero via `sys.exit("<message>")` with the refusal reason and the next command, never a traceback.
- A `.carried.json` is written by the engine only; a fresh judge verdict for the same `(tc, dimension)` always wins over a carried one.
- `sealed_digest` is computed over **active** test cases of the scope only, by one helper (`wiki_rubric.sealed_digest`), everywhere.
- Config keys used: `rubric.threshold` (default 70), `rubric.version` (default `v1`), `ids.tc_format`, `ids.story_prefix` (default `US-`).
- Before calling any task done: `py tools/wiki.py lint` prints 0 errors, the task's test file passes, and `py tools/smoke.py --fast` prints `SMOKE OK` (clean tree required; master is content-free so content-dependent steps print `[SKIP]`).
- Spec deviation, recorded here: spec section 7's "smoke end-to-end case" cannot run against the tracked wiki without writing into a real story's `build/rubric/` round files, so it is realised as `tools/test_pipeline_chain.py`, a synthetic-data chain over redirected build dirs (Task 10), and smoke runs it on `--fast`.

## Review Focus

1. A **stale** test case in the scope: the score's digest and the export's selection must both use active cases only, or the final export refuses on a digest mismatch after any correction. Pinned in Task 2 (`test_sealed_digest_covers_active_cases_only`).
2. A round 1 score JSON written **before this change** (no `sealed_hash` on its records): round 2 packing must carry nothing and write full packs, never crash. Pinned in Task 6 (`test_carry_forward_is_empty_when_round_one_has_no_hashes`).
3. A judge who **re-bands a carried test case**: the fresh verdict wins with no duplicate error. Pinned in Task 6 (`test_fresh_verdict_wins_over_a_carried_one`).
4. A test case **retired between draft and final**: the diff lists it as removed with the retirement reason, never as "changed". Pinned in Task 7 (`test_a_retired_case_is_removed_with_its_reason`).
5. A **changes file from an older sealed set** (`to_digest` mismatch): the final export ignores it, writes the courtesy row, and still succeeds. Pinned in Task 5 (`test_final_export_ignores_a_stale_changes_file`).

---

## File structure

| File | Responsibility |
|---|---|
| `tools/wiki_rubric.py` (modify) | Pure helpers: `sealed_digest`, `tc_record`, `active_rels_from_manifest`, `DIFF_FIELDS`. |
| `tools/eval_rubric.py` (modify) | Score JSON gains `sealed_hash` per test case and `sealed_digest`; `--round N --pack` calls carry-forward for N ≥ 2; new `--diff`. |
| `tools/rubric_judge.py` (modify) | `score_rounds`, `rubric_state`, `draft_path`, `changes_path`, `carried_path`, `lens_verdicts`, `carry_forward`, `carried_counts`, `write_packs(exclude=)`, `load_judgments` merging carried files, `patch_tc_index`, `diff_records`, `write_changes`. |
| `tools/wiki_suite.py` (modify) | `render_xlsx(draft=, grade=, changes=)`, header marks in `_fill_toc`, `change_rows`, `_fill_change_log`. |
| `tools/wiki_export.py` (create) | `cmd_export` with `--story/--flow`, `--draft`, the final-export gate; `select_scope_tcs`, `write_draft_snapshot`, `draft_unchanged`, `export_gate`. |
| `tools/wiki.py` (modify) | Delete the old `cmd_export`; dispatch `export` to `wiki_export`. |
| `tools/wiki_next.py` (modify) | Delivery precedence after render; `scope_digest`, `rubric_state_for`, `draft_current`, `changes_current`, `delivery_next`; `flow_next` gets the flow's rel. |
| `tools/app/actions.py` (modify) | `_export` accepts boolean `draft`. |
| `tools/smoke.py` (modify) | Run the new test files; non-fast story export uses `--draft`. |
| `tools/test_wiki_rubric.py`, `tools/test_rubric_judge.py`, `tools/test_wiki_testmodel.py`, `tools/test_app_actions.py` (modify); `tools/test_wiki_export.py`, `tools/test_rubric_carry.py`, `tools/test_rubric_diff.py`, `tools/test_pipeline_chain.py` (create) | Tests. |
| Skills and docs (modify) | `tc-generate-sit`, `tc-generate-uat`, `tc-rubric` SKILL.md and guides; `docs/cli.md`, `docs/playbook.md`, `README.md`. |

Every new test file ends with this runner (copy verbatim, changing the final name):

```python
if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_<file> OK")
```

---

### Task 1: Sealed digest and test-case record helpers

**Files:**
- Modify: `tools/wiki_rubric.py` (append at end)
- Test: `tools/test_wiki_rubric.py` (append)

**Interfaces:**
- Produces: `sealed_digest(tc_hashes: dict, rels: iterable) -> str` (`"sha256:..."`); `tc_record(rel, fm, body, tc_hashes) -> dict` with keys `id, rel, hash, status, retirement_reason, title, technique, priority, coverage_items, covers, verifies_rules, sections`; `active_rels_from_manifest(manifest, scope_rel) -> list[str]`; `DIFF_FIELDS` tuple.

- [ ] **Step 1: Write the failing tests** (append to `tools/test_wiki_rubric.py`, before its `__main__` block)

```python
# ------------------------------------------------ sealed digest + records
from wiki_rubric import (DIFF_FIELDS, active_rels_from_manifest,  # noqa: E402
                         sealed_digest, tc_record)


def test_sealed_digest_is_order_independent_and_content_sensitive():
    h = {"testcases/sit/S/A": "sha256:1", "testcases/sit/S/B": "sha256:2"}
    d1 = sealed_digest(h, ["testcases/sit/S/A", "testcases/sit/S/B"])
    d2 = sealed_digest(h, ["testcases/sit/S/B", "testcases/sit/S/A"])
    assert d1 == d2 and d1.startswith("sha256:"), (d1, d2)
    h2 = dict(h, **{"testcases/sit/S/B": "sha256:3"})
    assert sealed_digest(h2, h) != d1, "a changed hash must change the digest"
    assert sealed_digest(h, ["testcases/sit/S/A"]) != d1, \
        "a different active set must change the digest"


def test_tc_record_captures_every_body_section_by_heading():
    body = ("# Objective\n\nSee it.\n\n# Steps\n\n1. Open.\n2. Look.\n\n"
            "# Expected Results\n\n1. Shown.\n")
    fm = {"id": "1-AC01-01", "status": "active", "title": "t",
          "technique": "UC", "priority": "P1", "coverage_items": ["SC-01"],
          "covers": ["/stories/US-1.md#AC01"],
          "retirement": {"reason": "superseded"}}
    rec = tc_record("testcases/sit/S/1-AC01-01", fm, body,
                    {"testcases/sit/S/1-AC01-01": "sha256:x"})
    assert rec["id"] == "1-AC01-01" and rec["hash"] == "sha256:x", rec
    assert rec["sections"] == {"Objective": "See it.",
                               "Steps": "1. Open.\n2. Look.",
                               "Expected Results": "1. Shown."}, rec["sections"]
    assert rec["retirement_reason"] == "superseded"
    assert rec["verifies_rules"] == [] and rec["covers"] == ["/stories/US-1.md#AC01"]
    for f in DIFF_FIELDS:
        assert f in rec, f


def test_active_rels_from_manifest_follows_covers_edges():
    m = {"concepts": {"testcases/sit/S/A": {"status": "active"},
                      "testcases/sit/S/B": {"status": "stale"},
                      "testcases/sit/S/C": {"status": "active"},
                      "stories/US-S": {"status": "aligned"}},
         "edges": [["testcases/sit/S/A", "covers", "stories/US-S#AC1"],
                   ["testcases/sit/S/B", "covers", "stories/US-S#AC1"],
                   ["testcases/sit/S/C", "covers", "stories/US-OTHER#AC1"]]}
    assert active_rels_from_manifest(m, "stories/US-S") == ["testcases/sit/S/A"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_wiki_rubric.py`
Expected: `ImportError: cannot import name 'DIFF_FIELDS'`

- [ ] **Step 3: Implement** (append to `tools/wiki_rubric.py`)

```python
# ------------------------------------------------ sealed digest + records
import hashlib
import re

# Frontmatter fields the draft -> final diff compares (spec 4.4). Body
# sections are compared by heading and need no listing here.
DIFF_FIELDS = ("title", "technique", "priority", "coverage_items", "covers",
               "verifies_rules")

_HEADING_SPLIT = re.compile(r"^# (.+?)[ \t]*$", re.MULTILINE)


def sealed_digest(tc_hashes, rels):
    """One hash over a scope's sealed test cases: sorted '<rel> <hash>' lines.
    Same active files with the same content -> same digest. Recorded in every
    score JSON, the draft snapshot and the changes file, and compared by
    export, --diff and `wiki next` (spec 5.3). ACTIVE rels only, by contract
    of every caller."""
    lines = sorted(f"{rel} {tc_hashes.get(rel) or ''}" for rel in rels)
    return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def tc_record(rel, fm, body, tc_hashes):
    """The diffable view of one rendered test case (spec 5.1). `sections`
    holds every `# Heading` of the body verbatim, so the diff never hardcodes
    the section list."""
    fm = fm or {}
    parts = _HEADING_SPLIT.split(body or "")
    sections = {parts[i].strip(): parts[i + 1].strip()
                for i in range(1, len(parts) - 1, 2)}
    return {"id": fm.get("id"), "rel": rel, "hash": tc_hashes.get(rel),
            "status": fm.get("status"),
            "retirement_reason": (fm.get("retirement") or {}).get("reason"),
            "title": fm.get("title") or "",
            "technique": fm.get("technique"), "priority": fm.get("priority"),
            "coverage_items": list(fm.get("coverage_items") or []),
            "covers": list(fm.get("covers") or []),
            "verifies_rules": list(fm.get("verifies_rules") or []),
            "sections": sections}


def active_rels_from_manifest(manifest, scope_rel):
    """Active test-case rels covering `scope_rel`, from the manifest alone
    (no concept read) - the same walk story_tc_stats in wiki.py does."""
    out = []
    for rel, entry in (manifest.get("concepts") or {}).items():
        if not rel.startswith("testcases/") or entry.get("status") != "active":
            continue
        if any(s == rel and k == "covers" and str(t).startswith(scope_rel + "#")
               for s, k, t in manifest.get("edges") or []):
            out.append(rel)
    return sorted(out)
```

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_wiki_rubric.py`
Expected: the three new `[PASS]` lines and `test_wiki_rubric OK`

- [ ] **Step 5: Commit**

```bash
git add tools/wiki_rubric.py tools/test_wiki_rubric.py
git commit -m "rubric: sealed_digest, tc_record and active_rels_from_manifest helpers (draft-first pipeline, task 1)"
```

---

### Task 2: Score JSON records sealed hashes and the scope digest

**Files:**
- Modify: `tools/eval_rubric.py` (`_tc_records` ~line 266, `score_scope` ~lines 297-460)
- Test: `tools/test_rubric_judge.py` (append)

**Interfaces:**
- Consumes: `wiki_rubric.sealed_digest`.
- Produces: every `_tc_records` record carries `rel`; `score_scope` result carries `sealed_digest` (str), each `test_cases[i]` carries `sealed_hash`, and a private `_tc_hashes` dict.

- [ ] **Step 1: Write the failing tests** (append to `tools/test_rubric_judge.py`)

```python
# ------------------------------------------------ sealed hash + digest
from wiki_rubric import sealed_digest  # noqa: E402


def _load_all_hashed():
    items = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary",
              "basis": ["S-AC1"], "feasible": True}]
    stale = dict(_tc_fm("TC-2"), status="stale")
    return ({"stories/US-S": (_story_fm(items), "", None),
             "testcases/sit/US-S/TC-1": (_tc_fm("TC-1"), BODY, None),
             "testcases/sit/US-S/TC-2": (stale, BODY, None)},
            {"tc_hashes": {"testcases/sit/US-S/TC-1": "sha256:aaa",
                           "testcases/sit/US-S/TC-2": "sha256:bbb"}})


def test_score_records_carry_the_sealed_hash_and_rel():
    res = score_scope("story", "US-S", load_all=_load_all_hashed)
    by = {r["id"]: r for r in res["test_cases"]}
    assert by["TC-1"]["sealed_hash"] == "sha256:aaa", by
    assert by["TC-2"]["sealed_hash"] == "sha256:bbb", by
    assert all(t.get("rel") for t in res["_tcs"]), "records need rel"
    assert res["_tc_hashes"] == _load_all_hashed()[1]["tc_hashes"]


def test_sealed_digest_covers_active_cases_only():
    """A stale case is still SCORED (it exists), but the digest identifies the
    active set an export would ship - otherwise every correction that stales
    one case would make the final export refuse on a digest mismatch."""
    res = score_scope("story", "US-S", load_all=_load_all_hashed)
    h = _load_all_hashed()[1]["tc_hashes"]
    assert res["sealed_digest"] == sealed_digest(h, ["testcases/sit/US-S/TC-1"]), res["sealed_digest"]
    assert {r["id"] for r in res["test_cases"]} == {"TC-1", "TC-2"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_rubric_judge.py`
Expected: `KeyError: 'sealed_hash'`

- [ ] **Step 3: Implement**

In `_tc_records`, after `rec["body"] = body or ""` add:

```python
        rec["rel"] = _rel
```

In `score_scope`: change `concepts, _manifest = load_all()` to `concepts, manifest = load_all()` and, directly after it:

```python
    tc_hashes = (manifest or {}).get("tc_hashes") or {}
```

Change the `per_tc.append(...)` to:

```python
        per_tc.append({"id": tc.get("id"), "bands": bands,
                       "score": score, "partial": partial,
                       "sealed_hash": tc_hashes.get(tc.get("rel"))})
```

In the returned dict add, after `"test_cases": per_tc,`:

```python
        "sealed_digest": sealed_digest(
            tc_hashes, [t["rel"] for t in tcs if t.get("status") == "active"]),
```

and to the private carriers add `"_tc_hashes": tc_hashes,`. Extend the `from wiki_rubric import (...)` inside `score_scope` with `sealed_digest`.

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_rubric_judge.py` then `py tools/test_eval_rubric.py`
Expected: both end with their `OK` line.

- [ ] **Step 5: Commit**

```bash
git add tools/eval_rubric.py tools/test_rubric_judge.py
git commit -m "rubric: score JSON records sealed_hash per test case and the active-set sealed_digest (task 2)"
```

---

### Task 3: Rubric state reader and build paths

**Files:**
- Modify: `tools/rubric_judge.py` (after `round_delta`, ~line 520)
- Test: `tools/test_rubric_judge.py` (append)

**Interfaces:**
- Produces: `draft_path(scope) -> Path`, `changes_path(scope, ext="json") -> Path`, `carried_path(scope, rnd, lens) -> Path`, `score_rounds(scope) -> {int: dict}`, `rubric_state(scope, digest, threshold, version) -> {"rounds": {N: {"score","partial","digest","rubric_version"}}, "highest": N|None, "improve_round_ran": bool, "current": {"round": N, "score": s}|None}`.

- [ ] **Step 1: Write the failing tests**

```python
# ------------------------------------------------ rubric_state
def _score_file(d, scope, n, score, digest, partial=False, version="v1"):
    (d / f"{scope}-r{n}-score.json").write_text(json.dumps(
        {"score": score, "partial": partial, "sealed_digest": digest,
         "rubric_version": version, "rubric_hash": HASH}), encoding="utf-8")


def test_rubric_state_picks_the_highest_current_round_at_threshold():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 70.77, "sha256:old")
        _score_file(d, "US-S", 2, 93.44, "sha256:cur")
        st = rj.rubric_state("US-S", "sha256:cur", 70, "v1")
        assert st["highest"] == 2 and st["improve_round_ran"] is True, st
        assert st["current"] == {"round": 2, "score": 93.44}, st
        assert set(st["rounds"]) == {1, 2}
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_rubric_state_regression_restore_falls_back_to_round_one():
    """Round 2 regressed and round 1's spec was restored: the sealed set is
    round 1's content again, so round 1 is the current score."""
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 80.0, "sha256:r1")
        _score_file(d, "US-S", 2, 75.0, "sha256:r2")
        st = rj.rubric_state("US-S", "sha256:r1", 70, "v1")
        assert st["current"] == {"round": 1, "score": 80.0}, st
        assert st["improve_round_ran"] is True
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_rubric_state_has_no_current_when_partial_below_threshold_or_other_rubric():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        _score_file(d, "US-S", 1, 95.0, "sha256:cur", partial=True)
        _score_file(d, "US-S", 2, 60.0, "sha256:cur")
        _score_file(d, "US-S", 3, 99.0, "sha256:cur", version="v0")
        st = rj.rubric_state("US-S", "sha256:cur", 70, "v1")
        assert st["current"] is None and st["highest"] == 3, st
        assert rj.rubric_state("US-NONE", "x", 70, "v1")["rounds"] == {}
        assert rj.draft_path("US-S") == d / "US-S-draft.json"
        assert rj.changes_path("US-S", "md") == d / "US-S-changes.md"
        assert rj.carried_path("US-S", 2, "A").name == "US-S-r2-A.carried.json"
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_rubric_judge.py`
Expected: `AttributeError: module 'rubric_judge' has no attribute 'rubric_state'`

- [ ] **Step 3: Implement** (add after `round_delta`)

```python
# ------------------------------------------------------ rubric state
def draft_path(scope):
    return RUBRIC_BUILD / f"{scope}-draft.json"


def changes_path(scope, ext="json"):
    return RUBRIC_BUILD / f"{scope}-changes.{ext}"


def carried_path(scope, rnd, lens):
    return JUDGMENT_DIR / f"{scope}-r{rnd}-{lens}.carried.json"


def score_rounds(scope):
    """{N: score JSON} for every <scope>-r<N>-score.json present."""
    out = {}
    pat = re.compile(rf"^{re.escape(scope)}-r(\d+)-score\.json$")
    for p in RUBRIC_BUILD.glob(f"{scope}-r*-score.json"):
        m = pat.match(p.name)
        if m:
            out[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
    return out


def rubric_state(scope, digest, threshold, version):
    """The one reading of a scope's grade that export, --diff and `wiki next`
    share (spec 4.2, 4.5). `current` is the highest round whose score is
    non-PARTIAL, at or above `threshold`, under rubric `version`, and computed
    on exactly the sealed set `digest` identifies."""
    rounds = score_rounds(scope)
    current = None
    for n in sorted(rounds):
        s = rounds[n]
        if (not s.get("partial") and s.get("score") is not None
                and s["score"] >= threshold
                and s.get("rubric_version") == version
                and s.get("sealed_digest") == digest):
            current = {"round": n, "score": s["score"]}
    return {"rounds": {n: {"score": s.get("score"),
                           "partial": bool(s.get("partial")),
                           "digest": s.get("sealed_digest"),
                           "rubric_version": s.get("rubric_version")}
                       for n, s in rounds.items()},
            "highest": max(rounds) if rounds else None,
            "improve_round_ran": 2 in rounds,
            "current": current}
```

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_rubric_judge.py`
Expected: `test_rubric_judge OK`

- [ ] **Step 5: Commit**

```bash
git add tools/rubric_judge.py tools/test_rubric_judge.py
git commit -m "rubric: rubric_state - the shared current-score reading, plus draft/changes/carried paths (task 3)"
```

---

### Task 4: Workbook marks and the Change Log sheet

**Files:**
- Modify: `tools/wiki_suite.py` (`_fill_toc` ~line 253, `render_xlsx` ~line 465)
- Test: `tools/test_wiki_export.py` (create)

**Interfaces:**
- Produces: `render_xlsx(tcs, title, xlsx_path, concepts=None, manifest=None, test_type="SIT", draft=False, grade=None, changes=None)`; `change_rows(changes, dash_of, draft=False) -> list[(dashboard, tc_display_id, description)]`.
- `grade` = `{"round": int, "score": float, "threshold": int, "version": str}`; `changes` = the changes JSON dict of spec 5.2.

- [ ] **Step 1: Write the failing tests** (create `tools/test_wiki_export.py`)

```python
#!/usr/bin/env python3
"""Plain-assert tests for the two-delivery export: workbook marks, the Change
Log sheet, the draft snapshot and the final-export gate
(run: py tools/test_wiki_export.py). No pytest - matches tools/smoke.py.

Everything writes under a throwaway directory; the wiki is never read."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
from wiki_suite import change_rows, render_xlsx  # noqa: E402

BODY = ("# Objective\n\nSee the page.\n\n# Preconditions\n\n1. Signed in.\n\n"
        "# Test Data\n\n**Amount** = 100\n\n# Steps\n\n1. Open the **Page**.\n\n"
        "# Expected Results\n\n1. The **Page** is shown.\n\n# Postconditions\n\n"
        "-\n\n# Traceability\n\n- AC01\n")
STORY = {"type": "User Story", "id": "US-9", "title": "Nine",
         "description": "PRD §5.1", "module": "/modules/m.md",
         "acceptance_criteria": [{"id": "AC01", "text": "Shown."}]}
MODULE = {"type": "Module", "id": "m", "title": "Mod", "description": "§5"}


def _tc(tid, title="Open the page"):
    fm = {"type": "Test Case", "id": tid, "title": title, "kind": "sit",
          "status": "active", "technique": "UC", "priority": "P1",
          "module": "/modules/m.md", "covers": ["/stories/US-9.md#AC01"],
          "coverage_items": ["SC-01"]}
    return (f"testcases/sit/US-9/{tid}", fm, BODY)


CONCEPTS = {"stories/US-9": (STORY, ""), "modules/m": (MODULE, "")}


def _tmpdir():
    return Path(tempfile.mkdtemp(prefix="wx-"))


def _sheet(path, name):
    from openpyxl import load_workbook
    return load_workbook(path)[name]


def test_draft_workbook_is_marked_in_the_header_and_change_log():
    d = _tmpdir()
    try:
        out = d / "d.xlsx"
        render_xlsx([_tc("9-AC01-01")], "Nine", out, concepts=CONCEPTS,
                    manifest={}, draft=True)
        toc = _sheet(out, "A - Table of Contents")
        assert toc["B1"].value.startswith("DRAFT (ungraded, round 0) - "), toc["B1"].value
        assert toc["C8"].value == "DRAFT r0", toc["C8"].value
        assert "not yet graded" in toc["C18"].value, toc["C18"].value
        log = _sheet(out, "Change Log")
        assert log["C2"].value == "Draft round 0 - no changes yet.", log["C2"].value
    finally:
        shutil.rmtree(d)


def test_final_workbook_carries_the_grade_and_the_change_rows():
    d = _tmpdir()
    try:
        out = d / "f.xlsx"
        changes = {"to": {"round": 2, "score": 93.44},
                   "rounds": [{"round": 1, "score": 70.77}, {"round": 2, "score": 93.44}],
                   "delta": 22.67, "regression_restored": False, "rubric_version": "v1",
                   "changes": [
                       {"tc": "9-AC01-01", "kind": "changed", "field": "Test Data",
                        "old": "a", "new": "b", "closes": "G3.1"},
                       {"tc": "9-AC01-01", "kind": "changed", "field": "Expected Results",
                        "old": "a", "new": "b", "closes": "G3.1"},
                       {"tc": "9-AC01-02", "kind": "added", "title": "Rejects zero",
                        "closes": "G1.19, G2.2"},
                       {"tc": "9-AC01-03", "kind": "removed", "reason": "superseded"}]}
        render_xlsx([_tc("9-AC01-01"), _tc("9-AC01-02", "Rejects zero")], "Nine", out,
                    concepts=CONCEPTS, manifest={},
                    grade={"round": 2, "score": 93.44, "threshold": 70, "version": "v1"},
                    changes=changes)
        toc = _sheet(out, "A - Table of Contents")
        assert toc["C8"].value == "r2 · rubric 93.44", toc["C8"].value
        assert "Graded round 2: score 93.44 (threshold 70), rubric v1" == toc["C18"].value, toc["C18"].value
        log = _sheet(out, "Change Log")
        rows = [(log.cell(r, 1).value, log.cell(r, 2).value, log.cell(r, 3).value)
                for r in range(2, 6)]
        assert rows[0] == ("", "", "Graded round 2: 93.44 (round 1: 70.77, +22.67), rubric v1"), rows[0]
        assert rows[1] == ("Nine", "TC-9-AC01-01", "Changed Test Data, Expected Results (closes G3.1)"), rows[1]
        assert rows[2] == ("Nine", "TC-9-AC01-02", "Added - Rejects zero (closes G1.19, G2.2)"), rows[2]
        assert rows[3] == ("", "TC-9-AC01-03", "Removed - superseded"), rows[3]
    finally:
        shutil.rmtree(d)


def test_final_workbook_without_changes_writes_the_courtesy_row():
    d = _tmpdir()
    try:
        out = d / "f.xlsx"
        render_xlsx([_tc("9-AC01-01")], "Nine", out, concepts=CONCEPTS, manifest={},
                    grade={"round": 2, "score": 80.0, "threshold": 70, "version": "v1"})
        log = _sheet(out, "Change Log")
        assert log["C2"].value == "No draft snapshot - change log not available.", log["C2"].value
    finally:
        shutil.rmtree(d)


def test_change_rows_reports_a_restored_round_one():
    rows = change_rows({"to": {"round": 1, "score": 80.0},
                        "rounds": [{"round": 1, "score": 80.0}, {"round": 2, "score": 75.0}],
                        "delta": -5.0, "regression_restored": True,
                        "rubric_version": "v1", "changes": []}, {})
    assert rows[0][2] == ("Graded round 1: 80.0 (round 2 regressed to 75.0, -5.0; "
                          "round 1 kept), rubric v1"), rows[0]
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_wiki_export.py`
Expected: `ImportError: cannot import name 'change_rows'`

- [ ] **Step 3: Implement**

In `_fill_toc`, replace the B1 assignment and the two literal strings:

```python
    ws["B1"] = meta.get("title_prefix", "") + "AGILE TEST SPECIFICATIONS - Table of Contents"
```

and in the Revision History row (row 18) replace `"Generated by tc-copilot (wiki export)"` with `meta.get("revision_summary", "Generated by tc-copilot (wiki export)")`.

Add before `render_xlsx`:

```python
def change_rows(changes, dash_of, draft=False):
    """Rows (Dashboard, Test Case ID, Description of Change) for the Change
    Log sheet. `dash_of` maps display id -> sub-story title."""
    if draft:
        return [("", "", "Draft round 0 - no changes yet.")]
    if not changes:
        return [("", "", "No draft snapshot - change log not available.")]
    to = changes.get("to") or {}
    rounds = {r["round"]: r["score"] for r in changes.get("rounds") or []}
    delta = changes.get("delta")
    sign = f"{delta:+}" if isinstance(delta, (int, float)) else ""
    if changes.get("regression_restored"):
        head = (f"Graded round {to.get('round')}: {to.get('score')} (round 2 "
                f"regressed to {rounds.get(2)}, {sign}; round 1 kept), "
                f"rubric {changes.get('rubric_version', '')}")
    elif to.get("round") and to["round"] - 1 in rounds:
        head = (f"Graded round {to['round']}: {to.get('score')} (round "
                f"{to['round'] - 1}: {rounds[to['round'] - 1]}, {sign}), "
                f"rubric {changes.get('rubric_version', '')}")
    else:
        head = (f"Graded round {to.get('round')}: {to.get('score')}, "
                f"rubric {changes.get('rubric_version', '')}")
    rows = [("", "", head)]
    grouped = {}          # tc -> (kind, fields, closes, extra) in first-seen order
    for c in changes.get("changes") or []:
        tid = c["tc"]
        disp = tid if tid.startswith("TC-") else f"TC-{tid[4:] if tid.startswith('UAT-') else tid}"
        g = grouped.setdefault(disp, {"kind": c["kind"], "fields": [], "closes": [],
                                      "title": c.get("title", ""), "reason": c.get("reason", "")})
        if c.get("field") and c["field"] not in g["fields"]:
            g["fields"].append(c["field"])
        for cl in (c.get("closes") or "").split(","):
            cl = cl.strip()
            if cl and cl not in g["closes"]:
                g["closes"].append(cl)
    for disp, g in grouped.items():
        closes = f" (closes {', '.join(g['closes'])})" if g["closes"] else ""
        if g["kind"] == "added":
            desc = f"Added - {g['title']}{closes}"
        elif g["kind"] == "removed":
            desc = f"Removed - {g['reason'] or 'not in the current set'}"
        else:
            desc = f"Changed {', '.join(g['fields'])}{closes}"
        rows.append((dash_of.get(disp, ""), disp, desc))
    return rows


def _fill_change_log(ws, st, rows):
    for col, h in enumerate(("Dashboard", "Test Case ID", "Description of Change"), 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font, c.fill, c.border = st["font"](bold=True), st["hdr_fill"], st["border"]
    for col, w in (("A", 30), ("B", 26), ("C", 70)):
        ws.column_dimensions[col].width = w
    for r, (dash, tid, desc) in enumerate(rows, 2):
        for col, v in enumerate((dash, tid, desc), 1):
            c = ws.cell(row=r, column=col, value=v)
            c.font, c.border, c.alignment = st["font"](), st["border"], st["top"]
```

In `render_xlsx`: change the signature to `def render_xlsx(tcs, title, xlsx_path, concepts=None, manifest=None, test_type="SIT", draft=False, grade=None, changes=None):`. After `meta = dict(...)` add:

```python
    if draft:
        meta.update(version="DRAFT r0", title_prefix="DRAFT (ungraded, round 0) - ",
                    revision_summary=("DRAFT first cut - rendered and sealed, not yet "
                                      "graded against the ISO/IEC/IEEE 29119-4 rubric. "
                                      "A final workbook with a Change Log follows."))
    elif grade:
        meta.update(version=f"r{grade['round']} · rubric {grade['score']}",
                    revision_summary=(f"Graded round {grade['round']}: score "
                                      f"{grade['score']} (threshold {grade['threshold']}), "
                                      f"rubric {grade['version']}"))
```

Replace the Change Log block (from `log = wb.create_sheet("Change Log")` to just before `wb.save`) with:

```python
    dash_of = {}
    for _mrel, _mod_fm, subs in groups:
        for _srel, sfm, tcl in subs:
            for _r, fm, _b in tcl:
                dash_of[_display_id(fm)] = _plain((sfm or {}).get("title") or title)
    _fill_change_log(wb.create_sheet("Change Log"), st,
                     change_rows(changes, dash_of, draft=draft))
```

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_wiki_export.py`
Expected: four `[PASS]` lines, `test_wiki_export OK`

- [ ] **Step 5: Commit**

```bash
git add tools/wiki_suite.py tools/test_wiki_export.py
git commit -m "export: DRAFT and graded header marks, Change Log sheet rows from the changes file (task 4)"
```

---

### Task 5: `wiki export` in its own module: `--draft`, `--flow`, the final gate

**Files:**
- Create: `tools/wiki_export.py`
- Modify: `tools/wiki.py` (delete `cmd_export` ~lines 1868-1900; dispatch line `elif cmd == "export":`)
- Test: `tools/test_wiki_export.py` (append)

**Interfaces:**
- Consumes: `wiki_rubric.sealed_digest`, `tc_record`; `rubric_judge.rubric_state`, `draft_path`, `changes_path`; `wiki_suite.render_xlsx`, `inventory_paths`, `tc_sort_key`.
- Produces: `select_scope_tcs(concepts, kind, scope) -> (scope_rel, scope_fm, [(rel, fm, body)])`; `write_draft_snapshot(scope, kind, tcs, manifest, workbook_rel, seal_commit, rubric_version, path) -> dict`; `draft_unchanged(path, digest) -> dict|None`; `export_gate(scope, kind, digest, cfg) -> (current|None, refusal_text|None)`; `cmd_export(args)`.

- [ ] **Step 1: Write the failing tests** (append to `tools/test_wiki_export.py`)

```python
# ------------------------------------------------ snapshot + gate
import wiki_export as wx  # noqa: E402

CFG = {"rubric": {"threshold": 70, "version": "v1"}}


def test_select_scope_tcs_keeps_active_cases_of_the_scope_in_sort_order():
    retired = dict(_tc("9-AC01-02")[1], status="retired")
    other = dict(_tc("8-AC01-01")[1], covers=["/stories/US-8.md#AC01"])
    concepts = dict(CONCEPTS)
    concepts["testcases/sit/US-9/9-AC01-02"] = (_tc("9-AC01-02")[1], BODY)
    concepts["testcases/sit/US-9/9-AC01-01"] = (_tc("9-AC01-01")[1], BODY)
    concepts["testcases/sit/US-9/9-AC01-03"] = (retired, BODY)
    concepts["testcases/sit/US-8/8-AC01-01"] = (other, BODY)
    rel, sfm, tcs = wx.select_scope_tcs(concepts, "story", "US-9")
    assert rel == "stories/US-9" and sfm["title"] == "Nine"
    assert [fm["id"] for _r, fm, _b in tcs] == ["9-AC01-01", "9-AC01-02"], tcs


def test_draft_snapshot_records_digest_and_every_case():
    d = _tmpdir()
    try:
        tcs = [_tc("9-AC01-01"), _tc("9-AC01-02")]
        manifest = {"tc_hashes": {"testcases/sit/US-9/9-AC01-01": "sha256:1",
                                  "testcases/sit/US-9/9-AC01-02": "sha256:2"}}
        snap = wx.write_draft_snapshot("US-9", "story", tcs, manifest,
                                       "build/inventory/sit/x.xlsx", "abc123", "v1",
                                       d / "US-9-draft.json")
        on_disk = json.loads((d / "US-9-draft.json").read_text(encoding="utf-8"))
        assert on_disk == snap
        assert set(snap["test_cases"]) == {"9-AC01-01", "9-AC01-02"}
        assert snap["test_cases"]["9-AC01-01"]["hash"] == "sha256:1"
        assert snap["seal_commit"] == "abc123" and snap["score"] is None
        from wiki_rubric import sealed_digest
        assert snap["sealed_digest"] == sealed_digest(manifest["tc_hashes"],
                                                      [r for r, _f, _b in tcs])
        assert wx.draft_unchanged(d / "US-9-draft.json", snap["sealed_digest"]) == snap
        assert wx.draft_unchanged(d / "US-9-draft.json", "sha256:other") is None
        assert wx.draft_unchanged(d / "missing.json", snap["sealed_digest"]) is None
    finally:
        shutil.rmtree(d)


def _scores(d, *rounds):
    for n, score, digest, partial in rounds:
        (d / f"US-9-r{n}-score.json").write_text(json.dumps(
            {"score": score, "partial": partial, "sealed_digest": digest,
             "rubric_version": "v1"}), encoding="utf-8")


def test_export_gate_refuses_ungraded_round_one_only_and_stale_scores():
    old = rj.RUBRIC_BUILD
    d = _tmpdir()
    try:
        rj.RUBRIC_BUILD = d
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur is None and "has not been graded" in err and "--draft" in err, err
        _scores(d, (1, 80.0, "sha256:cur", False))
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur is None and "improve round has not run" in err, err
        _scores(d, (1, 80.0, "sha256:cur", False), (2, 90.0, "sha256:old", False))
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur == {"round": 1, "score": 80.0} and err is None, (cur, err)
        _scores(d, (1, 80.0, "sha256:old1", False), (2, 90.0, "sha256:old", False))
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur is None and "different sealed set" in err and "--round 2" in err, err
        _scores(d, (2, 90.0, "sha256:cur", True))
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur is None and "PARTIAL" in err, err
        _scores(d, (2, 60.0, "sha256:cur", False))
        cur, err = wx.export_gate("US-9", "story", "sha256:cur", CFG)
        assert cur is None and "below the threshold" in err, err
    finally:
        rj.RUBRIC_BUILD = old
        shutil.rmtree(d)


def test_final_export_ignores_a_stale_changes_file():
    """A changes file computed on an older sealed set must not decorate the
    final workbook with the wrong change log."""
    stale = {"to_digest": "sha256:older", "changes": []}
    assert wx.changes_for("sha256:cur", stale) is None
    fresh = {"to_digest": "sha256:cur", "changes": []}
    assert wx.changes_for("sha256:cur", fresh) == fresh
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_wiki_export.py`
Expected: `ModuleNotFoundError: No module named 'wiki_export'`

- [ ] **Step 3: Create `tools/wiki_export.py`**

```python
#!/usr/bin/env python3
"""`wiki export`: one scope (story or flow) -> the org workbook, twice.

  --draft   right after the first seal: marked DRAFT round 0 in the header,
            a snapshot kept for the later diff, no rubric gate BECAUSE the
            workbook says so (spec 4.1).
  (final)   refuses unless a non-PARTIAL, at-threshold score exists for the
            currently sealed set and the improve round ran (spec 4.2). Fills
            the Change Log sheet from build/rubric/<scope>-changes.json.

Zero LLM calls. Writes under build/ and commits as tc-agent.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime

from wiki import (ROOT, agent_commit, all_concepts, arg_after, load_config,
                  load_manifest, refuse_if_unsealed, resolve_ref)
from wiki_rubric import sealed_digest, tc_record

_KIND = {"story": ("stories", "sit", "SIT", "--story"),
         "flow": ("flows", "uat", "UAT", "--flow")}


def scope_of(args):
    if "--story" in args:
        return "story", arg_after(args, "--story")
    if "--flow" in args:
        return "flow", arg_after(args, "--flow")
    sys.exit("export: one of --story <id> or --flow <stem> is required")


def select_scope_tcs(concepts, kind, scope):
    """(scope_rel, scope_fm, [(rel, fm, body)]) - ACTIVE test cases whose
    `covers` resolve to the scope, in workbook order."""
    from wiki_suite import tc_sort_key
    scope_rel = f"{_KIND[kind][0]}/{scope}"
    if scope_rel not in concepts:
        sys.exit(f"export: no concept for {scope!r} ({scope_rel}.md)")
    sfm = concepts[scope_rel][0]
    tcs = []
    for rel, entry in concepts.items():
        fm, body = entry[0], entry[1]
        if fm and fm.get("type") == "Test Case" and fm.get("status") == "active":
            if any(resolve_ref(c)[0] == scope_rel for c in fm.get("covers") or []):
                tcs.append((rel, fm, body))
    tcs.sort(key=lambda t: tc_sort_key(t[1]))
    return scope_rel, sfm, tcs


def head_commit():
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def write_draft_snapshot(scope, kind, tcs, manifest, workbook_rel, seal_commit,
                         rubric_version, path):
    h = manifest.get("tc_hashes") or {}
    snap = {"scope": scope, "kind": kind,
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "workbook": workbook_rel, "seal_commit": seal_commit,
            "sealed_digest": sealed_digest(h, [rel for rel, _f, _b in tcs]),
            "rubric_version": rubric_version, "score": None,
            "test_cases": {fm["id"]: tc_record(rel, fm, body, h)
                           for rel, fm, body in tcs}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return snap


def draft_unchanged(path, digest):
    """The existing snapshot when it describes exactly this sealed set."""
    if not path.exists():
        return None
    snap = json.loads(path.read_text(encoding="utf-8"))
    return snap if snap.get("sealed_digest") == digest else None


def changes_for(digest, changes):
    """The changes dict only when it was computed on this sealed set."""
    if changes and changes.get("to_digest") == digest:
        return changes
    return None


def export_gate(scope, kind, digest, cfg):
    """(current score, None) when the final export may proceed, else
    (None, refusal text). The prose rule '--round 2 --strict is the export
    gate' promoted into the CLI (spec 4.2)."""
    from rubric_judge import rubric_state
    rc = cfg.get("rubric") or {}
    threshold, version = rc.get("threshold", 70), rc.get("version", "v1")
    flag = _KIND[kind][3]
    st = rubric_state(scope, digest, threshold, version)
    hint = (f"  A first cut without the gate is: py tools/wiki.py export "
            f"{flag} {scope} --name <n> --draft")
    if not st["rounds"]:
        return None, (f"export refused: {scope} has not been graded.\n"
                      f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1 --pack\n{hint}")
    if not st["improve_round_ran"]:
        return None, (f"export refused: {scope} has a round 1 score only - the "
                      f"improve round has not run.\n"
                      f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1   "
                      f"(merge; then the improver patch, --apply-patch, render "
                      f"--force, seal, --round 2 --pack)\n{hint}")
    if st["current"]:
        return st["current"], None
    hi = st["highest"]
    r = st["rounds"][hi]
    if r["rubric_version"] != version:
        why = (f"The latest score (round {hi}) was computed under rubric "
               f"{r['rubric_version']}; config.yaml says {version}.")
        nxt = f"py tools/eval_rubric.py {flag} {scope} --round {hi} --pack   (re-judge under the current rubric)"
    elif r["digest"] != digest:
        why = (f"The latest score (round {hi}, {r['score']}) was computed on a "
               f"different sealed set.")
        nxt = (f"py tools/eval_rubric.py {flag} {scope} --round {hi}   (re-merge on "
               f"the current set; if round 1 was restored after a regression, --round 1)")
    elif r["partial"]:
        why = f"The latest score (round {hi}) is PARTIAL - a judge lens is missing."
        nxt = (f"run the missing lens from build/rubric/packs/, then "
               f"py tools/eval_rubric.py {flag} {scope} --round {hi}")
    else:
        why = (f"The latest score (round {hi}, {r['score']}) is below the "
               f"threshold {threshold}.")
        nxt = (f"py tools/eval_rubric.py {flag} {scope} --round {hi} --strict   "
               f"(the set does not pass; the draft stays the deliverable)")
    return None, (f"export refused: {scope} has no score on the currently sealed "
                  f"set.\n  {why}\n  Next: {nxt}\n{hint}")


def _write_md(md_ts, md_latest, name, scope, manifest, tcs, label):
    md = ["<!-- generated by wiki export — reproducible from manifest + wiki; do not edit -->",
          f"# Inventory: {name}", "",
          f"- scope: {scope} · PRD v{manifest.get('adopted_prd_version')} · "
          f"TCs: {len(tcs)} · {label}", ""]
    for _rel, fm, _body in tcs:
        md.append(f"- **{fm['id']}** — {fm['title']} "
                  f"(covers {', '.join(fm.get('covers') or [])})")
    md_ts.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(md_ts, md_latest)


def cmd_export(args):
    refuse_if_unsealed("export")
    kind, scope = scope_of(args)
    _dir, kind_dir, test_type, flag = _KIND[kind]
    draft = "--draft" in args
    name = arg_after(args, "--name") if "--name" in args else f"{scope}-{kind_dir}"
    cfg = load_config()
    rubric_version = (cfg.get("rubric") or {}).get("version", "v1")
    concepts = {rel: (fm, body) for rel, fm, body, _ in all_concepts()}
    manifest = load_manifest()
    _scope_rel, sfm, tcs = select_scope_tcs(concepts, kind, scope)
    if not tcs:
        sys.exit(f"export refused: {scope} has no active test cases.\n"
                 f"  Next: render the scope, then py tools/wiki.py seal")
    digest = sealed_digest(manifest.get("tc_hashes") or {},
                           [rel for rel, _f, _b in tcs])
    from rubric_judge import changes_path, draft_path
    from wiki_suite import inventory_paths, render_xlsx
    title = sfm.get("title") or scope

    if draft:
        prior = draft_unchanged(draft_path(scope), digest)
        if prior:
            sys.exit(f"export refused: draft for {scope} already exported on "
                     f"{prior['exported_at']} ({prior['workbook']}); the sealed set "
                     f"has not changed.\n"
                     f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1 --pack")
        _o, xlsx_ts, md_ts, xlsx_latest, md_latest = inventory_paths(f"{name}-draft", kind_dir)
        render_xlsx(tcs, title, xlsx_ts, concepts=concepts, manifest=manifest,
                    test_type=test_type, draft=True)
        shutil.copyfile(xlsx_ts, xlsx_latest)
        rel_ts = xlsx_ts.relative_to(ROOT).as_posix()
        write_draft_snapshot(scope, kind, tcs, manifest, rel_ts, head_commit(),
                             rubric_version, draft_path(scope))
        _write_md(md_ts, md_latest, f"{name}-draft", scope, manifest, tcs,
                  "DRAFT round 0 - ungraded")
        print(f"exported DRAFT r0: {len(tcs)} TCs -> {rel_ts} (+ {xlsx_latest.name})\n"
              f"  snapshot: {draft_path(scope).relative_to(ROOT).as_posix()}\n"
              f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1 --pack")
        agent_commit(f"export({name}-draft): {len(tcs)} TCs [draft r0]")
        return

    current, err = export_gate(scope, kind, digest, cfg)
    if err:
        sys.exit(err)
    changes = None
    cp = changes_path(scope)
    if cp.exists():
        changes = changes_for(digest, json.loads(cp.read_text(encoding="utf-8")))
    grade = {"round": current["round"], "score": current["score"],
             "threshold": (cfg.get("rubric") or {}).get("threshold", 70),
             "version": rubric_version}
    _o, xlsx_ts, md_ts, xlsx_latest, md_latest = inventory_paths(name, kind_dir)
    render_xlsx(tcs, title, xlsx_ts, concepts=concepts, manifest=manifest,
                test_type=test_type, grade=grade, changes=changes)
    shutil.copyfile(xlsx_ts, xlsx_latest)
    _write_md(md_ts, md_latest, name, scope, manifest, tcs,
              f"graded r{current['round']} {current['score']}")
    rel_ts = xlsx_ts.relative_to(ROOT).as_posix()
    note = "" if changes else "\n  (no current change log - run --diff first to fill the Change Log sheet)"
    print(f"exported {len(tcs)} TCs, rubric r{current['round']} {current['score']} "
          f"-> {rel_ts} (+ {xlsx_latest.name}){note}")
    agent_commit(f"export({name}): {len(tcs)} TCs, rubric r{current['round']} "
                 f"{current['score']}")
```

In `tools/wiki.py`: delete the whole `def cmd_export(args): ...` function (it ends at `agent_commit(f"export({name}): {len(tcs)} TCs")`) and change the dispatch to:

```python
    elif cmd == "export":
        from wiki_export import cmd_export
        cmd_export(args)
```

Also update the usage text near line 53 of `wiki.py` (the docstring line for `export`) to:

```
  export --story <id> | --flow <stem> [--name <n>] [--draft]
                        draft: DRAFT r0 workbook + diff snapshot right after seal;
                        final: refuses without a current strict score, fills Change Log
```

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_wiki_export.py` and `py tools/wiki.py export` (with no scope)
Expected: `test_wiki_export OK`; the second prints `export: one of --story <id> or --flow <stem> is required` and exits 1.

- [ ] **Step 5: Commit**

```bash
git add tools/wiki_export.py tools/wiki.py tools/test_wiki_export.py
git commit -m "export: move to wiki_export.py; --draft first cut with snapshot, --flow scopes, final export refuses without a current strict score (task 5)"
```

---

### Task 6: Round N carry-forward of unchanged verdicts

**Files:**
- Modify: `tools/rubric_judge.py` (`load_judgments` ~line 81, `write_packs` ~line 260, new functions after `carried_path`)
- Modify: `tools/eval_rubric.py` (`main`, the `--pack` and merge section ~lines 640-690)
- Test: `tools/test_rubric_carry.py` (create)

**Interfaces:**
- Consumes: `score_path`, `judgment_path`, `carried_path`, `load_judgments`, records with `rel` and `_tc_hashes` from Task 2.
- Produces: `lens_verdicts(scope, rnd, lens) -> list[dict]`; `carry_forward(scope, rnd, tcs, tc_hashes, rubric_hash, judge_dims) -> {lens: [tc ids]}`; `carried_counts(scope, rnd) -> {lens: int}`; `write_packs(..., exclude=None)`; `load_judgments(..., judgment_dir=None, current_hashes=None)` also reading `.carried.json`.

- [ ] **Step 1: Write the failing tests** (create `tools/test_rubric_carry.py`)

```python
#!/usr/bin/env python3
"""Plain-assert tests for round-N carry-forward of unchanged verdicts
(run: py tools/test_rubric_carry.py). No pytest - matches tools/smoke.py.
Everything under a throwaway build dir."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402

HASH = "sha256:test"
JUDGE_DIMS = {"T1.4", "T1.5", "T1.7", "T1.8", "T2.5", "T2.6"}


def _v(tc, dim, band, rationale="because", gap=""):
    return {"tc": tc, "dimension": dim, "band": band,
            "rationale": rationale, "gap": gap}


def _judgment(d, scope, rnd, lens, verdicts):
    (d / "judgments").mkdir(parents=True, exist_ok=True)
    (d / "judgments" / f"{scope}-r{rnd}-{lens}.json").write_text(json.dumps(
        {"rubric_hash": HASH, "scope": scope, "round": rnd, "lens": lens,
         "verdicts": verdicts}), encoding="utf-8")


def _score(d, scope, rnd, hashes):
    (d / f"{scope}-r{rnd}-score.json").write_text(json.dumps(
        {"score": 80.0, "rubric_hash": HASH, "partial": False,
         "test_cases": [{"id": t, "sealed_hash": h} for t, h in hashes.items()]}),
        encoding="utf-8")


def _tcs(hashes):
    return [{"id": t, "rel": f"testcases/sit/S/{t}", "status": "active",
             "title": t, "technique": "BVA", "coverage_items": ["BVA-01"],
             "covers": [], "verifies_rules": [], "body": ""}
            for t in hashes]


class _Redirect:
    def __enter__(self):
        self.d = Path(tempfile.mkdtemp(prefix="carry-"))
        self.old = (rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR)
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = \
            self.d, self.d / "packs", self.d / "judgments"
        return self.d

    def __exit__(self, *a):
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = self.old
        shutil.rmtree(self.d)


def test_carry_forward_copies_verdicts_only_for_unchanged_hashes():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-1", "T1.5", 4),
                                      _v("TC-2", "T1.4", 2), _v("TC-2", "T1.5", 2)])
        _judgment(d, "US-S", 1, "D", [_v("scope", "T2.5", 3), _v("scope", "T2.6", 3)])
        cur = {"testcases/sit/S/TC-1": "sha256:a",       # unchanged
               "testcases/sit/S/TC-2": "sha256:b2",      # patched
               "testcases/sit/S/TC-3": "sha256:c"}       # added by the patch
        carried = rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0, "TC-3": 0}),
                                   cur, HASH, JUDGE_DIMS)
        assert carried == {"A": ["TC-1"]}, carried
        cf = json.loads(rj.carried_path("US-S", 2, "A").read_text(encoding="utf-8"))
        assert cf["round"] == 2 and cf["lens"] == "A"
        assert {(v["tc"], v["dimension"], v["carried_from"]) for v in cf["verdicts"]} \
            == {("TC-1", "T1.4", 1), ("TC-1", "T1.5", 1)}, cf
        assert not rj.carried_path("US-S", 2, "D").exists(), "lens D is never carried"
        assert not rj.carried_path("US-S", 2, "B").exists(), "no round-1 B file -> nothing"


def test_carry_forward_is_empty_when_round_one_has_no_hashes():
    """A round-1 score written before sealed_hash existed carries nothing and
    must not crash: full packs, as before."""
    with _Redirect() as d:
        (d / "US-S-r1-score.json").write_text(json.dumps(
            {"score": 80.0, "rubric_hash": HASH,
             "test_cases": [{"id": "TC-1"}]}), encoding="utf-8")
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3)])
        assert rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                                {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS) == {}
        assert rj.carry_forward("US-S", 1, [], {}, HASH, JUDGE_DIMS) == {}, "round 1 never carries"


def test_carry_forward_refuses_an_invalid_previous_verdict_file():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.7", 3)])   # T1.7 is lens B's
        try:
            rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}),
                             {"testcases/sit/S/TC-1": "sha256:a"}, HASH, JUDGE_DIMS)
        except SystemExit as e:
            assert "REFUSED" in str(e), e
        else:
            raise AssertionError("an invalid round-1 verdict must never be carried")


def test_packs_exclude_carried_cases_and_say_so():
    with _Redirect() as d:
        result = {"scope": "US-S", "rubric_version": "v1", "rubric_hash": HASH,
                  "standard": "s", "coverage": {}, "t25_ceiling": 4,
                  "model_warnings": [], "unknown_item_refs": []}
        from rubric import load_rubric
        rub = load_rubric("v1")
        fm = {"acceptance_criteria": [], "business_rules": [],
              "test_model": {"items": [{"id": "BVA-01", "technique": "BVA",
                                        "kind": "boundary", "basis": []}]}}
        tcs = _tcs({"TC-1": 0, "TC-2": 0})
        rj.write_packs(result, tcs, fm, rub, 2, {}, exclude={"A": {"TC-1"}, "B": {"TC-1", "TC-2"}})
        a = (d / "packs" / "US-S-r2-A.md").read_text(encoding="utf-8")
        assert "Carried forward from round 1: 1 test case(s)" in a, a
        assert "### TC-2" in a and "### TC-1" not in a, a
        b = (d / "packs" / "US-S-r2-B.md").read_text(encoding="utf-8")
        assert "Nothing to judge for this lens this round" in b and "### TC-" not in b, b
        c = (d / "packs" / "US-S-r2-C.md").read_text(encoding="utf-8")
        assert "### TC-1" in c and "### TC-2" in c, "lens C had nothing excluded"
        dd = (d / "packs" / "US-S-r2-D.md").read_text(encoding="utf-8")
        assert "| TC-1 |" in dd and "| TC-2 |" in dd, "lens D always sees the whole set"


def test_load_judgments_merges_carried_verdicts_and_marks_the_lens_present():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a", "TC-2": "sha256:b"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 3), _v("TC-2", "T1.4", 2)])
        cur = {"testcases/sit/S/TC-1": "sha256:a", "testcases/sit/S/TC-2": "sha256:b2"}
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0, "TC-2": 0}), cur, HASH, JUDGE_DIMS)
        _judgment(d, "US-S", 2, "A", [_v("TC-2", "T1.4", 4)])
        per_tc, _ps, notes, present = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1", "TC-2"], JUDGE_DIMS,
            current_hashes={"TC-1": "sha256:a", "TC-2": "sha256:b2"})
        assert per_tc == {"TC-1": {"T1.4": 3}, "TC-2": {"T1.4": 4}}, per_tc
        assert notes[("TC-1", "T1.4")].get("carried_from") == 1, notes
        assert "A" in present
        assert rj.carried_counts("US-S", 2) == {"A": 1}


def test_fresh_verdict_wins_over_a_carried_one():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        _judgment(d, "US-S", 2, "A", [_v("TC-1", "T1.4", 4, rationale="re-read")])
        per_tc, _ps, notes, _pr = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:a"})
        assert per_tc == {"TC-1": {"T1.4": 4}}, "a fresh read is always allowed and wins"
        assert "carried_from" not in notes[("TC-1", "T1.4")]


def test_carried_verdict_is_dropped_when_the_hash_moved_since():
    with _Redirect() as d:
        _score(d, "US-S", 1, {"TC-1": "sha256:a"})
        _judgment(d, "US-S", 1, "A", [_v("TC-1", "T1.4", 2)])
        rj.carry_forward("US-S", 2, _tcs({"TC-1": 0}), {"testcases/sit/S/TC-1": "sha256:a"},
                         HASH, JUDGE_DIMS)
        # the file changed AFTER the carry (e.g. a forced re-render): honest reading
        per_tc, _ps, _n, present = rj.load_judgments(
            "US-S", 2, HASH, ["TC-1"], JUDGE_DIMS, current_hashes={"TC-1": "sha256:zzz"})
        assert per_tc == {}, per_tc
        assert "A" in present, "the lens ran; its verdict just no longer applies"


def test_carried_file_with_a_bad_verdict_is_a_hard_refusal():
    with _Redirect() as d:
        (d / "judgments").mkdir()
        rj.carried_path("US-S", 2, "A").write_text(json.dumps(
            {"rubric_hash": HASH, "scope": "US-S", "round": 2, "lens": "A",
             "verdicts": [dict(_v("TC-1", "T1.4", 3), carried_from="one")]}),
            encoding="utf-8")
        try:
            rj.load_judgments("US-S", 2, HASH, ["TC-1"], JUDGE_DIMS)
        except SystemExit as e:
            assert "carried_from" in str(e), e
        else:
            raise AssertionError("a malformed carried verdict must be refused")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric_carry OK")
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_rubric_carry.py`
Expected: `AttributeError: module 'rubric_judge' has no attribute 'carry_forward'`

- [ ] **Step 3: Implement in `tools/rubric_judge.py`**

Rewrite `load_judgments` so the per-verdict validation is shared between the fresh and the carried file. Replace the whole function with:

```python
def load_judgments(scope, rnd, rubric_hash, tc_ids, judge_dims,
                   judgment_dir=None, current_hashes=None):
    """Read every lens file for (scope, round), fresh and carried.

    Returns (per_tc, per_scope, notes, present_lenses):
      per_tc    {tc_id: {dim: band}}
      per_scope {dim: band}
      notes     {(tc_or_scope, dim): {"rationale", "gap", "lens", "band"
                 [, "carried_from"]}}
      present   set of lens letters whose fresh OR carried file existed

    A malformed or mismatched file is a hard refusal listing every problem.
    A MISSING file is not an error: its dimensions stay NOT ASSESSED and the
    score is marked PARTIAL, which is the honest reading of "no judge ran".

    Carried file (<scope>-r<N>-<L>.carried.json, written by carry_forward):
    same envelope, every verdict carries `carried_from: <round>`. A fresh
    verdict for the same (tc, dimension) WINS - a judge re-reading an
    untouched case is always allowed. When `current_hashes` ({tc_id: hash})
    is given, a carried verdict whose test case no longer has the sealed
    hash recorded in round `carried_from`'s score JSON is DROPPED with a
    printed note: it describes content that no longer exists.
    """
    jdir = judgment_dir or JUDGMENT_DIR
    per_tc, per_scope, notes, present = {}, {}, {}, set()
    errs, seen = [], set()
    tc_ids = set(tc_ids)
    prev_hash_cache = {}

    def _prev_hash(from_round, tc):
        if from_round not in prev_hash_cache:
            p = score_path(scope, from_round)
            recs = (json.loads(p.read_text(encoding="utf-8")).get("test_cases")
                    if p.exists() else None) or []
            prev_hash_cache[from_round] = {r.get("id"): r.get("sealed_hash") for r in recs}
        return prev_hash_cache[from_round].get(tc)

    for lens, spec in LENSES.items():
        files = ((jdir / f"{scope}-r{rnd}-{lens}.json", False),
                 (jdir / f"{scope}-r{rnd}-{lens}.carried.json", True))
        for p, carried in files:
            if not p.exists():
                continue
            present.add(lens)
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errs.append(f"{p.name}: not valid JSON ({e})")
                continue
            if not isinstance(data, dict):
                errs.append(f"{p.name}: top level must be an object")
                continue
            if data.get("rubric_hash") != rubric_hash:
                errs.append(f"{p.name}: rubric_hash {data.get('rubric_hash')!r} "
                            f"does not match the current rubric {rubric_hash!r} "
                            f"- verdicts under another rubric are not comparable")
            if data.get("scope") != scope:
                errs.append(f"{p.name}: scope {data.get('scope')!r} is not {scope!r}")
            if data.get("lens") not in (lens, spec["name"]):
                errs.append(f"{p.name}: lens {data.get('lens')!r} is not "
                            f"{lens!r} / {spec['name']!r}")
            verdicts = data.get("verdicts")
            if not isinstance(verdicts, list):
                errs.append(f"{p.name}: verdicts must be a list")
                continue
            for i, v in enumerate(verdicts):
                where = f"{p.name} verdicts[{i}]"
                if not isinstance(v, dict):
                    errs.append(f"{where}: must be an object")
                    continue
                dim, band, tc = v.get("dimension"), v.get("band"), v.get("tc")
                if dim not in spec["dims"]:
                    errs.append(f"{where}: dimension {dim!r} is not judged by lens "
                                f"{lens} (it judges {spec['dims']})")
                    continue
                if dim not in judge_dims:
                    errs.append(f"{where}: dimension {dim!r} is not a judge "
                                f"dimension in the rubric")
                    continue
                if not (isinstance(band, int) and not isinstance(band, bool)
                        and 0 <= band <= 4):
                    errs.append(f"{where}: band {band!r} must be an integer 0-4")
                    continue
                rationale = v.get("rationale")
                if not (isinstance(rationale, str) and rationale.strip()):
                    errs.append(f"{where}: rationale is required (a band with no "
                                f"reason is not auditable)")
                    continue
                from_round = v.get("carried_from")
                if carried and not (isinstance(from_round, int)
                                    and not isinstance(from_round, bool)
                                    and 1 <= from_round < rnd):
                    errs.append(f"{where}: carried_from must be an earlier round "
                                f"number, got {from_round!r}")
                    continue
                tier2 = dim.startswith("T2.")
                if tier2:
                    key = SCOPE_TC
                    if tc not in (None, SCOPE_TC):
                        errs.append(f"{where}: a Tier 2 verdict applies to the "
                                    f"whole scope; tc must be null or 'scope'")
                        continue
                    if carried:
                        errs.append(f"{where}: a Tier 2 verdict is never carried")
                        continue
                else:
                    key = tc
                    if tc not in tc_ids:
                        errs.append(f"{where}: tc {tc!r} is not an active test "
                                    f"case of {scope}")
                        continue
                if (key, dim) in seen:
                    if carried:
                        continue            # the fresh verdict already won
                    errs.append(f"{where}: duplicate verdict for ({key}, {dim})")
                    continue
                if carried and current_hashes is not None:
                    if current_hashes.get(tc) != _prev_hash(from_round, tc):
                        print(f"  carried verdict dropped: {tc} {dim} changed since "
                              f"round {from_round}")
                        continue
                seen.add((key, dim))
                if tier2:
                    per_scope[dim] = band
                else:
                    per_tc.setdefault(key, {})[dim] = band
                note = {"rationale": rationale.strip(),
                        "gap": (v.get("gap") or "").strip(),
                        "lens": lens, "band": band}
                if carried:
                    note["carried_from"] = from_round
                notes[(key, dim)] = note
    if errs:
        detail = "\n".join(f"    - {e}" for e in errs)
        sys.exit(f"eval_rubric REFUSED: judge verdicts for {scope} round {rnd} "
                 f"are not acceptable.\n{detail}\n"
                 f"  A rejected verdict is never silently dropped (spec 6.3).\n"
                 f"  Next: fix the file(s) under build/rubric/judgments/ and "
                 f"re-run.")
    return per_tc, per_scope, notes, present
```

Add after `carried_path`:

```python
def lens_verdicts(scope, rnd, lens):
    """Raw verdict dicts of (scope, rnd, lens): the fresh file first, then
    carried ones not already present. Validation is load_judgments' job."""
    out, seen = [], set()
    for p in (judgment_path(scope, rnd, lens), carried_path(scope, rnd, lens)):
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for v in (data.get("verdicts") if isinstance(data, dict) else None) or []:
            if isinstance(v, dict):
                key = (v.get("tc"), v.get("dimension"))
                if key not in seen:
                    seen.add(key)
                    out.append(v)
    return out


def carry_forward(scope, rnd, tcs, tc_hashes, rubric_hash, judge_dims):
    """Round rnd >= 2: for lenses A, B, C copy round rnd-1's verdicts for
    every test case whose sealed hash is unchanged since that round into
    <scope>-r<rnd>-<L>.carried.json. Returns {lens: sorted carried tc ids}.
    Lens D (set-level) is never carried. Nothing is carried when round rnd-1
    has no score, or its records carry no sealed_hash (scored before this
    existed). An INVALID round rnd-1 verdict file is a refusal: carrying a
    rejected verdict would launder it (spec 4.3)."""
    if rnd < 2:
        return {}
    prev = score_path(scope, rnd - 1)
    if not prev.exists():
        return {}
    prev_recs = json.loads(prev.read_text(encoding="utf-8")).get("test_cases") or []
    prev_hash = {r.get("id"): r.get("sealed_hash") for r in prev_recs
                 if r.get("sealed_hash")}
    if not prev_hash:
        return {}
    cur_hash = {tc.get("id"): tc_hashes.get(tc.get("rel")) for tc in tcs}
    unchanged = {t for t, h in cur_hash.items() if h and prev_hash.get(t) == h}
    load_judgments(scope, rnd - 1, rubric_hash, [r.get("id") for r in prev_recs],
                   judge_dims)
    JUDGMENT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for lens in ("A", "B", "C"):
        keep = [{**v, "carried_from": rnd - 1}
                for v in lens_verdicts(scope, rnd - 1, lens)
                if v.get("tc") in unchanged]
        if not keep:
            continue
        carried_path(scope, rnd, lens).write_text(json.dumps(
            {"rubric_hash": rubric_hash, "scope": scope, "round": rnd,
             "lens": lens, "verdicts": keep}, indent=2) + "\n", encoding="utf-8")
        out[lens] = sorted({v["tc"] for v in keep})
    return out


def carried_counts(scope, rnd):
    """{lens: number of test cases with a carried verdict} for the round."""
    out = {}
    for lens in ("A", "B", "C"):
        p = carried_path(scope, rnd, lens)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            ids = {v.get("tc") for v in data.get("verdicts") or [] if isinstance(v, dict)}
            if ids:
                out[lens] = len(ids)
    return out
```

In `write_packs`, change the signature to `def write_packs(result, tcs, fm, rub, rnd, mech_by_tc, lenses=None, exclude=None):` and replace the final `else:` branch (the one that loops `for tc in tcs: lines.append(_tc_block(...))`) with:

```python
        else:
            skip = set((exclude or {}).get(lens) or set())
            shown = [tc for tc in tcs if tc.get("id") not in skip]
            if skip:
                lines.append(f"Carried forward from round {rnd - 1}: {len(skip)} "
                             f"test case(s) unchanged since their last verdict - "
                             f"do not band them; band only the {len(shown)} below.\n")
            if skip and not shown:
                lines.append("Nothing to judge for this lens this round; every "
                             "verdict is carried. Do not write a judgment file.\n")
            for tc in shown:
                lines.append(_tc_block(tc, ac_text, br_text, model_by_id,
                                       mech_by_tc.get(tc.get("id"), {}),
                                       dims, include))
```

- [ ] **Step 4: Wire `tools/eval_rubric.py` `main`**

Extend the import line to `from rubric_judge import (LENSES, apply_patch, carried_counts, carry_forward, load_judgments, round_delta, score_path, write_gaps, write_packs)`. After `tc_ids = [...]` and before `load_judgments(...)` add:

```python
    tc_hashes = base.get("_tc_hashes") or {}
    current_hashes = {tc.get("id"): tc_hashes.get(tc.get("rel"))
                      for tc in base.get("_tcs") or []}
    carried = {}
    if "--pack" in argv and rnd >= 2:
        carried = carry_forward(scope, rnd, base.get("_tcs") or [], tc_hashes,
                                base["rubric_hash"], judge_dims)
```

Change the merge call to `load_judgments(scope, rnd, base["rubric_hash"], tc_ids, judge_dims, current_hashes=current_hashes)`. After `result["judges_missing"] = ...` add `result["carried"] = carried_counts(scope, rnd)`. Change the `write_packs(...)` call to pass `exclude=carried`. After the `judges missing` print block add:

```python
    if result["carried"]:
        print("  carried forward: " + ", ".join(
            f"{lens} {n}" for lens, n in sorted(result["carried"].items()))
              + f" test case(s) unchanged since round {rnd - 1}")
```

- [ ] **Step 5: Run to verify they pass**

Run: `py tools/test_rubric_carry.py`, `py tools/test_rubric_judge.py`
Expected: both `OK`.

- [ ] **Step 6: Commit**

```bash
git add tools/rubric_judge.py tools/eval_rubric.py tools/test_rubric_carry.py
git commit -m "rubric: round N packs carry forward A/B/C verdicts for test cases whose sealed hash is unchanged; fresh verdict wins (task 6)"
```

---

### Task 7: Deterministic diff, `eval_rubric --diff`

**Files:**
- Modify: `tools/rubric_judge.py` (new functions after `carried_counts`)
- Modify: `tools/eval_rubric.py` (`main`, before the `--apply-patch` branch)
- Test: `tools/test_rubric_diff.py` (create)

**Interfaces:**
- Consumes: `wiki_rubric.tc_record`, `DIFF_FIELDS`, `sealed_digest`; `rubric_state`, `draft_path`, `changes_path`, `patch_path`.
- Produces: `patch_tc_index(scope, kind, patch, cfg) -> {tc_id: [{"op","field","closes"}]}`; `diff_records(old, new, cause=None) -> (changes, counts)`; `write_changes(scope, kind, snapshot, current, state, cause, to_digest, threshold, version) -> (json_path, md_path)`; CLI `py tools/eval_rubric.py --story <id> --diff`.

- [ ] **Step 1: Write the failing tests** (create `tools/test_rubric_diff.py`)

```python
#!/usr/bin/env python3
"""Plain-assert tests for the draft -> final diff
(run: py tools/test_rubric_diff.py). No pytest - matches tools/smoke.py."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
from wiki_rubric import tc_record  # noqa: E402

CFG = {"ids": {"tc_format": "{story_num}-AC{ac_num:02d}-{seq:02d}",
               "story_prefix": "US-"}}


def _rec(tid, body, status="active", reason=None, **fm):
    f = {"id": tid, "status": status, "title": "t", "technique": "UC",
         "priority": "P1", "coverage_items": ["SC-01"], "covers": [],
         "retirement": {"reason": reason} if reason else None}
    f.update(fm)
    return tc_record(f"testcases/sit/S/{tid}", f, body, {f"testcases/sit/S/{tid}": "sha256:" + str(hash(body + status))})


B1 = "# Test Data\n\n**A** = 1\n\n# Expected Results\n\n1. Ok.\n"
B2 = "# Test Data\n\n**A** = 2\n\n# Expected Results\n\n1. Ok.\n"


def test_patch_tc_index_maps_story_ops_to_ids_and_flow_ops_by_tc():
    patch = {"patches": [
        {"op": "set", "ac": "AC6", "seq": 1, "field": "data", "closes": "G3.1"},
        {"op": "add", "closes": "G1.19, G2.2",
         "test_case": {"ac": "AC20", "seq": 3, "title": "x"}}]}
    idx = rj.patch_tc_index("US-1.2.3.4", "story", patch, CFG)
    assert set(idx) == {"1.2.3.4-AC06-01", "1.2.3.4-AC20-03"}, idx
    assert idx["1.2.3.4-AC06-01"] == [{"op": "set", "field": "data", "closes": "G3.1"}]
    fidx = rj.patch_tc_index("f-e2e", "flow",
                             {"patches": [{"op": "set", "tc": "UAT-1-AC01-01",
                                           "field": "steps", "closes": "G3.2"}]}, CFG)
    assert fidx == {"UAT-1-AC01-01": [{"op": "set", "field": "steps", "closes": "G3.2"}]}
    assert rj.patch_tc_index("US-1", "story", None, CFG) == {}


def test_diff_classifies_added_changed_removed_and_unchanged():
    old = {"1-AC01-01": _rec("1-AC01-01", B1), "1-AC01-02": _rec("1-AC01-02", B1),
           "1-AC01-03": _rec("1-AC01-03", B1)}
    new = {"1-AC01-01": _rec("1-AC01-01", B1),                      # unchanged
           "1-AC01-02": _rec("1-AC01-02", B2, priority="P2"),       # changed
           "1-AC01-04": _rec("1-AC01-04", B1, title="new one")}     # added; 03 gone
    cause = {"1-AC01-02": [{"op": "set", "field": "data", "closes": "G3.1"}],
             "1-AC01-04": [{"op": "add", "field": None, "closes": "G1.2"}]}
    changes, counts = rj.diff_records(old, new, cause)
    assert counts == {"added": 1, "changed": 1, "removed": 1, "unchanged": 1}, counts
    kinds = {(c["tc"], c["kind"], c.get("field")) for c in changes}
    assert ("1-AC01-04", "added", None) in kinds
    assert ("1-AC01-03", "removed", None) in kinds
    assert ("1-AC01-02", "changed", "priority") in kinds
    assert ("1-AC01-02", "changed", "Test Data") in kinds, kinds
    td = next(c for c in changes if c["tc"] == "1-AC01-02" and c["field"] == "Test Data")
    assert td["old"] == "**A** = 1" and td["new"] == "**A** = 2" and td["closes"] == "G3.1", td
    pr = next(c for c in changes if c["tc"] == "1-AC01-02" and c["field"] == "priority")
    assert pr["closes"] == "G3.1" and pr["op"] is None, "no op names priority; scope-level closes"
    added = next(c for c in changes if c["kind"] == "added")
    assert added["title"] == "new one" and added["closes"] == "G1.2"


def test_a_retired_case_is_removed_with_its_reason():
    old = {"1-AC01-01": _rec("1-AC01-01", B1)}
    new = {"1-AC01-01": _rec("1-AC01-01", B1, status="retired", reason="superseded")}
    changes, counts = rj.diff_records(old, new)
    assert counts["removed"] == 1 and counts["changed"] == 0, counts
    assert changes == [{"tc": "1-AC01-01", "kind": "removed", "reason": "superseded"}], changes


def test_write_changes_emits_json_and_markdown_with_the_score_header():
    old_b = rj.RUBRIC_BUILD
    d = Path(tempfile.mkdtemp(prefix="diff-"))
    try:
        rj.RUBRIC_BUILD = d
        snapshot = {"sealed_digest": "sha256:d0", "score": None,
                    "exported_at": "2026-09-25T10:00:00+08:00",
                    "test_cases": {"1-AC01-01": _rec("1-AC01-01", B1)}}
        current = {"1-AC01-01": _rec("1-AC01-01", B2)}
        state = {"rounds": {1: {"score": 70.77}, 2: {"score": 93.44}},
                 "highest": 2, "improve_round_ran": True,
                 "current": {"round": 2, "score": 93.44}}
        jp, mp = rj.write_changes("US-1", "story", snapshot, current, state,
                                  {}, "sha256:d2", 70, "v1")
        doc = json.loads(jp.read_text(encoding="utf-8"))
        assert doc["to_digest"] == "sha256:d2" and doc["to"]["round"] == 2
        assert doc["delta"] == 22.67 and doc["regression_restored"] is False, doc
        assert doc["counts"]["changed"] == 1 and doc["from"]["label"] == "draft r0"
        md = mp.read_text(encoding="utf-8")
        assert "70.77" in md and "93.44" in md and "## Changed" in md and "Test Data" in md, md
        assert "-**A** = 1" in md and "+**A** = 2" in md, "section diffs are unified lines"
        # regression restore: current round below the highest
        state2 = dict(state, current={"round": 1, "score": 70.77},
                      rounds={1: {"score": 70.77}, 2: {"score": 60.0}})
        doc2 = json.loads(rj.write_changes("US-1", "story", snapshot, current, state2,
                                           {}, "sha256:d1", 70, "v1")[0].read_text(encoding="utf-8"))
        assert doc2["regression_restored"] is True and doc2["to"]["round"] == 1, doc2
    finally:
        rj.RUBRIC_BUILD = old_b
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric_diff OK")
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_rubric_diff.py`
Expected: `AttributeError: module 'rubric_judge' has no attribute 'patch_tc_index'`

- [ ] **Step 3: Implement in `tools/rubric_judge.py`** (after `carried_counts`)

```python
# ------------------------------------------------------ draft -> final diff
# Improver patch field names -> the record field / body heading they change.
PATCH_FIELD_TO_RECORD = {"data": "Test Data", "expected": "Expected Results",
                         "steps": "Steps", "pre_extra": "Preconditions",
                         "post": "Postconditions", "objective": "Objective",
                         "title": "title", "technique": "technique",
                         "priority": "priority", "coverage_items": "coverage_items",
                         "extra_covers": "covers", "rules": "verifies_rules"}


def patch_tc_index(scope, kind, patch, cfg):
    """{tc_id: [{"op", "field", "closes"}]} from an improver patch. A story
    op names (ac, seq); the id follows config ids.tc_format. A flow op joins
    only when it carries a `tc` key (spec 4.4 step 3)."""
    ids = cfg.get("ids") or {}
    fmt = ids.get("tc_format", "{story_num}-AC{ac_num:02d}-{seq:02d}")
    prefix = ids.get("story_prefix", "US-")
    story_num = scope[len(prefix):] if scope.startswith(prefix) else scope
    idx = {}
    for p in (patch or {}).get("patches") or []:
        if not isinstance(p, dict):
            continue
        tid = p.get("tc")
        if not tid and kind == "story":
            entry = p.get("test_case") if p.get("op") == "add" else p
            entry = entry if isinstance(entry, dict) else {}
            m = re.search(r"AC(\d+)", str(entry.get("ac", "")))
            if m and entry.get("seq") is not None:
                tid = fmt.format(story_num=story_num, ac_num=int(m.group(1)),
                                 seq=int(entry["seq"]))
        if tid:
            idx.setdefault(tid, []).append({"op": p.get("op", "set"),
                                            "field": p.get("field"),
                                            "closes": p.get("closes", "")})
    return idx


def _closes_of(ops):
    tags = []
    for op in ops:
        for c in re.split(r",\s*", op.get("closes") or ""):
            if c and c not in tags:
                tags.append(c)
    return ", ".join(tags)


def diff_records(old, new, cause=None):
    """Compare two {tc_id: tc_record} maps (spec 4.4). Returns (changes,
    counts). A case absent from `new`, or present but not active, is
    removed; equal hashes are unchanged; otherwise one change per field."""
    from wiki_rubric import DIFF_FIELDS
    cause = cause or {}
    changes = []
    counts = {"added": 0, "changed": 0, "removed": 0, "unchanged": 0}
    for tid in sorted(set(old) | set(new)):
        o, n = old.get(tid), new.get(tid)
        ops = cause.get(tid) or []
        closes = _closes_of(ops)
        if o is None:
            counts["added"] += 1
            changes.append({"tc": tid, "kind": "added",
                            "title": (n or {}).get("title", ""), "closes": closes})
        elif n is None or n.get("status") != "active":
            counts["removed"] += 1
            changes.append({"tc": tid, "kind": "removed",
                            "reason": (n or {}).get("retirement_reason")
                            or "not in the current set"})
        elif o.get("hash") == n.get("hash"):
            counts["unchanged"] += 1
        else:
            fields = [(f, o.get(f), n.get(f)) for f in DIFF_FIELDS
                      if o.get(f) != n.get(f)]
            heads = sorted(set(o.get("sections") or {}) | set(n.get("sections") or {}))
            for h in heads:
                ov = (o.get("sections") or {}).get(h)
                nv = (n.get("sections") or {}).get(h)
                if ov != nv:
                    fields.append((h, ov, nv))
            if not fields:
                fields.append(("(file)", o.get("hash"), n.get("hash")))
            counts["changed"] += 1
            for f, ov, nv in fields:
                op = next((x for x in ops if x.get("field")
                           and PATCH_FIELD_TO_RECORD.get(x["field"], x["field"]) == f),
                          None)
                changes.append({"tc": tid, "kind": "changed", "field": f,
                                "old": ov, "new": nv,
                                "closes": op["closes"] if op else closes,
                                "op": op})
    return changes, counts


def _unified(old, new, cap=40):
    import difflib
    a = (old or "").splitlines() if isinstance(old, str) else [json.dumps(old)]
    b = (new or "").splitlines() if isinstance(new, str) else [json.dumps(new)]
    lines = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=1)
             if not ln.startswith(("---", "+++"))]
    if len(lines) > cap:
        lines = lines[:cap] + [f"... {len(lines) - cap} more line(s)"]
    return lines


def write_changes(scope, kind, snapshot, current, state, cause, to_digest,
                  threshold, version):
    """build/rubric/<scope>-changes.json + .md (spec 5.2)."""
    changes, counts = diff_records(snapshot.get("test_cases") or {}, current, cause)
    rounds = sorted((n, r.get("score")) for n, r in (state.get("rounds") or {}).items())
    cur, hi = state.get("current"), state.get("highest")
    delta = None
    if len(rounds) >= 2 and rounds[-1][1] is not None and rounds[-2][1] is not None:
        delta = round(rounds[-1][1] - rounds[-2][1], 2)
    doc = {"scope": scope, "kind": kind,
           "from": {"label": "draft r0", "digest": snapshot.get("sealed_digest"),
                    "score": snapshot.get("score"),
                    "exported_at": snapshot.get("exported_at")},
           "to": {"label": f"round {cur['round']}" if cur else "ungraded",
                  "digest": to_digest, "score": cur["score"] if cur else None,
                  "round": cur["round"] if cur else None},
           "to_digest": to_digest,
           "rounds": [{"round": n, "score": s} for n, s in rounds],
           "delta": delta,
           "regression_restored": bool(cur and hi and cur["round"] < hi),
           "rubric_version": version, "threshold": threshold,
           "counts": counts, "changes": changes}
    RUBRIC_BUILD.mkdir(parents=True, exist_ok=True)
    jp, mp = changes_path(scope, "json"), changes_path(scope, "md")
    jp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    L = [f"# Changes · {scope} · draft r0 -> {doc['to']['label']}", "",
         f"- scores: " + ", ".join(f"round {n} {s}" for n, s in rounds)
         + (f" · delta {delta:+}" if delta is not None else "")
         + f" · threshold {threshold} · rubric {version}",
         f"- current: {doc['to']['label']}"
         + (" (round 2 regressed; round 1 kept)" if doc["regression_restored"] else ""),
         f"- {counts['added']} added, {counts['changed']} changed, "
         f"{counts['removed']} removed, {counts['unchanged']} unchanged", ""]
    L += ["## Added", ""]
    L += [f"- **{c['tc']}** - {c['title']}" + (f" (closes {c['closes']})" if c["closes"] else "")
          for c in changes if c["kind"] == "added"] or ["- none"]
    L += ["", "## Changed", ""]
    by_tc = {}
    for c in changes:
        if c["kind"] == "changed":
            by_tc.setdefault(c["tc"], []).append(c)
    for tid, cs in by_tc.items():
        L.append(f"### {tid}")
        for c in cs:
            L.append(f"- **{c['field']}**" + (f" (closes {c['closes']})" if c["closes"] else "")
                     + (" - cause: not recorded" if not c.get("op") and not c["closes"] else ""))
            L.append("```diff")
            L += _unified(c["old"], c["new"])
            L.append("```")
        L.append("")
    if not by_tc:
        L.append("- none")
    L += ["", "## Removed", ""]
    L += [f"- **{c['tc']}** - {c['reason']}" for c in changes if c["kind"] == "removed"] or ["- none"]
    mp.write_text("\n".join(L) + "\n", encoding="utf-8")
    return jp, mp
```

- [ ] **Step 4: Add `--diff` to `tools/eval_rubric.py` `main`** (insert right after the `rnd < 1` check, before the `--apply-patch` branch)

```python
    if "--diff" in argv:
        from rubric_judge import (changes_path, draft_path, patch_path,
                                  patch_tc_index, rubric_state, write_changes)
        from wiki import load_all, load_config, resolve_ref
        from wiki_rubric import sealed_digest, tc_record
        dp = draft_path(scope)
        if not dp.exists():
            sys.exit(f"eval_rubric --diff refused: no draft snapshot for {scope}.\n"
                     f"  A diff needs a 'from' side - the draft export writes it.\n"
                     f"  Next: py tools/wiki.py export --{kind} {scope} --name <n> --draft")
        snapshot = json.loads(dp.read_text(encoding="utf-8"))
        concepts, manifest = load_all()
        rel = f"{_KIND_DIR[kind]}/{scope}"
        if rel not in concepts:
            sys.exit(f"eval_rubric: no concept for {scope!r}")
        tc_hashes = manifest.get("tc_hashes") or {}
        current = {}
        for crel, (fm, body, _p) in concepts.items():
            if fm and fm.get("type") == "Test Case" and any(
                    resolve_ref(c)[0] == rel for c in fm.get("covers") or []):
                current[fm["id"]] = tc_record(crel, fm, body, tc_hashes)
        digest = sealed_digest(tc_hashes, [r["rel"] for r in current.values()
                                           if r["status"] == "active"])
        cfg = load_config()
        rc = cfg.get("rubric") or {}
        state = rubric_state(scope, digest, rc.get("threshold", 70), rc.get("version", "v1"))
        pp = patch_path(scope, 1)
        patch = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
        jp, mp = write_changes(scope, kind, snapshot, current, state,
                               patch_tc_index(scope, kind, patch, cfg), digest,
                               rc.get("threshold", 70), rc.get("version", "v1"))
        doc = json.loads(jp.read_text(encoding="utf-8"))
        c = doc["counts"]
        print(f"{scope}: {c['added']} added, {c['changed']} changed, "
              f"{c['removed']} removed, {c['unchanged']} unchanged "
              f"(draft r0 -> {doc['to']['label']})")
        print(f"  -> {mp.relative_to(ROOT).as_posix()}\n  -> {jp.relative_to(ROOT).as_posix()}")
        if state["current"] is None:
            print("  NOTE: no current strict score on this sealed set - the final "
                  "export will refuse until one exists")
        return 0
```

Add to the usage text: `"       py tools/eval_rubric.py --story <ID> --diff        (draft snapshot -> current sealed set)\n"`.

- [ ] **Step 5: Run to verify they pass**

Run: `py tools/test_rubric_diff.py`; then `py tools/eval_rubric.py --story US-NONE --diff`
Expected: `test_rubric_diff OK`; the CLI prints `eval_rubric --diff refused: no draft snapshot for US-NONE.` and exits 1.

- [ ] **Step 6: Commit**

```bash
git add tools/rubric_judge.py tools/eval_rubric.py tools/test_rubric_diff.py
git commit -m "rubric: --diff compares the draft snapshot with the sealed set by id and field, joined to patch ops (task 7)"
```

---

### Task 8: `wiki next` delivery precedence

**Files:**
- Modify: `tools/wiki_next.py` (`rubric_score_exists` ~line 116, `story_next` ~line 123, `flow_next` ~line 178, `collect_next` ~line 298)
- Modify: `tools/test_wiki_testmodel.py` (`test_next_routes_an_ungraded_story_to_tc_rubric` ~line 171)
- Test: `tools/test_wiki_testmodel.py` (append)

**Interfaces:**
- Consumes: `wiki_rubric.active_rels_from_manifest`, `sealed_digest`; `rubric_judge.rubric_state`, `draft_path`, `changes_path`.
- Produces: `scope_digest(manifest, scope_rel)`, `rubric_state_for(scope_id, digest)`, `draft_current(scope_id, digest) -> bool`, `changes_current(scope_id, digest) -> bool`, `delivery_next(scope_id, flag, name, manifest, scope_rel, active, skill_gen) -> (state, command, skill)`; `flow_next(fid, fm, body, concepts, manifest, flow_rel=None)`.

- [ ] **Step 1: Rewrite the existing test and add the precedence test** (in `tools/test_wiki_testmodel.py`, replace `test_next_routes_an_ungraded_story_to_tc_rubric` entirely)

```python
def _graded_fm():
    return dict(STORY, status="aligned", coverage_status="confirmed",
                coverage_map=[{"ac": "M-AC1", "components": []}],
                test_model={"status": "confirmed", "items": [
                    {"id": "SC-01", "technique": "UC", "kind": "scenario",
                     "basis": ["M-AC1"], "feasible": True}]})


def _with_next_state(draft, state, changes, fn):
    """Run fn() with wiki_next's three build/ readers stubbed."""
    real = (wiki_next.draft_current, wiki_next.rubric_state_for,
            wiki_next.changes_current)
    try:
        wiki_next.draft_current = lambda sid, digest: draft
        wiki_next.rubric_state_for = lambda sid, digest: state
        wiki_next.changes_current = lambda sid, digest: changes
        return fn()
    finally:
        (wiki_next.draft_current, wiki_next.rubric_state_for,
         wiki_next.changes_current) = real


def _st(rounds, current=None):
    return {"rounds": {n: {"score": s} for n, s in rounds.items()},
            "highest": max(rounds) if rounds else None,
            "improve_round_ran": 2 in rounds, "current": current}


def test_next_walks_the_six_delivery_steps_in_order():
    fm = _graded_fm()
    nxt = lambda: wiki_next.story_next("US-M", fm, "", _MANIFEST, "stories/US-M")
    # 1 no draft yet
    state, cmd, skill = _with_next_state(False, _st({}), False, nxt)
    assert "first cut NOT delivered" in state and cmd.endswith("--name US-M-sit --draft"), (state, cmd)
    assert skill.startswith("tc-generate-sit"), skill
    # 2 draft delivered, not graded
    state, cmd, skill = _with_next_state(True, _st({}), False, nxt)
    assert "NOT graded" in state and "--round 1 --pack" in cmd and skill.startswith("tc-rubric"), (state, cmd)
    # 3 round 1 only
    state, cmd, _s = _with_next_state(True, _st({1: 70.0}), False, nxt)
    assert "improve round NOT run" in state and cmd.endswith("--round 1"), (state, cmd)
    # 4 no current score on this set
    state, cmd, _s = _with_next_state(True, _st({1: 70.0, 2: 90.0}), False, nxt)
    assert "no strict score on the current sealed set" in state and "--round 2 --strict" in cmd, (state, cmd)
    # 5 graded, no change log
    state, cmd, skill = _with_next_state(True, _st({1: 70.0, 2: 90.0}, {"round": 2, "score": 90.0}), False, nxt)
    assert "change log NOT built" in state and cmd.endswith("--story US-M --diff"), (state, cmd)
    # 6 ready
    state, cmd, skill = _with_next_state(True, _st({1: 70.0, 2: 90.0}, {"round": 2, "score": 90.0}), True, nxt)
    assert "ready to export" in state and cmd == "py tools/wiki.py export --story US-M --name US-M-sit", (state, cmd)
    assert skill.startswith("tc-suite-author"), skill


def test_scope_digest_reads_the_manifest_only():
    from wiki_rubric import sealed_digest
    m = dict(_MANIFEST, tc_hashes={_TC_REL: "sha256:q"})
    assert wiki_next.scope_digest(m, "stories/US-M") == sealed_digest({_TC_REL: "sha256:q"}, [_TC_REL])
```

- [ ] **Step 2: Run to verify they fail**

Run: `py tools/test_wiki_testmodel.py`
Expected: `AttributeError: module 'wiki_next' has no attribute 'draft_current'`

- [ ] **Step 3: Implement in `tools/wiki_next.py`**

Replace `rubric_score_exists` with:

```python
def scope_digest(manifest, scope_rel):
    """Digest of the scope's ACTIVE sealed test cases, from the manifest alone."""
    from wiki_rubric import active_rels_from_manifest, sealed_digest
    return sealed_digest(manifest.get("tc_hashes") or {},
                         active_rels_from_manifest(manifest, scope_rel))


def rubric_state_for(scope_id, digest):
    from rubric_judge import rubric_state
    rc = load_config().get("rubric") or {}
    return rubric_state(scope_id, digest, rc.get("threshold", 70), rc.get("version", "v1"))


def _json_field_matches(path, key, digest):
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(key) == digest
    except (OSError, ValueError):
        return False


def draft_current(scope_id, digest):
    """A draft snapshot exists for exactly this sealed set."""
    from rubric_judge import draft_path
    return _json_field_matches(draft_path(scope_id), "sealed_digest", digest)


def changes_current(scope_id, digest):
    from rubric_judge import changes_path
    return _json_field_matches(changes_path(scope_id), "to_digest", digest)


def delivery_next(scope_id, flag, name, manifest, scope_rel, active, skill_gen):
    """Shared tail of story_next / flow_next once a rendered set exists: the
    six-step delivery precedence (spec 4.5). All build/ readers are module
    functions so tests can stub them."""
    digest = scope_digest(manifest, scope_rel)
    if not draft_current(scope_id, digest):
        return (f"rendered · {active} active TC(s) - first cut NOT delivered",
                f"py tools/wiki.py export {flag} {scope_id} --name {name} --draft",
                f"{skill_gen} (step 4a: draft export - the human reviews while "
                f"the grade loop runs)")
    st = rubric_state_for(scope_id, digest)
    if 1 not in st["rounds"]:
        return (f"draft delivered · {active} active TC(s) - NOT graded",
                f"py tools/eval_rubric.py {flag} {scope_id} --round 1 --pack",
                "tc-rubric (grade loop: 4 judge lenses, gap report, one "
                "improve round)")
    if not st["improve_round_ran"]:
        return ("graded round 1 - improve round NOT run",
                f"py tools/eval_rubric.py {flag} {scope_id} --round 1",
                "tc-rubric (merge; improver patch, --apply-patch, render --force, "
                "seal, --round 2 --pack)")
    if st["current"] is None:
        return ("graded - no strict score on the current sealed set",
                f"py tools/eval_rubric.py {flag} {scope_id} --round {st['highest']} --strict",
                "tc-rubric (re-merge on the current set; a regression keeps round 1)")
    cur = st["current"]
    if not changes_current(scope_id, digest):
        return (f"graded r{cur['round']} {cur['score']} - change log NOT built",
                f"py tools/eval_rubric.py {flag} {scope_id} --diff",
                f"{skill_gen} (step 6: diff draft -> final)")
    return (f"graded r{cur['round']} {cur['score']} - ready to export",
            f"py tools/wiki.py export {flag} {scope_id} --name {name}",
            "tc-suite-author (final export; suite compile for a multi-scope workbook)")
```

`json` is already imported; add `load_config` to the existing `from wiki import (ROOT, all_concepts, arg_after, body_section, load_manifest, ...)` line at the top of the module. In `story_next`, replace the last two `return` blocks (from `if not rubric_score_exists(sid):` to the end) with:

```python
    return delivery_next(sid, "--story", f"{sid}-sit", manifest, story_rel,
                         t["active"], "tc-generate-sit")
```

In `flow_next`, change the signature to `def flow_next(fid, fm, body, concepts, manifest, flow_rel=None):` and replace the final `return (... "ready" ... suite compile ...)` with:

```python
    stem = Path(flow_rel).stem if flow_rel else fid
    return delivery_next(stem, "--flow", f"{stem}-uat", manifest,
                         flow_rel or f"flows/{stem}", uat["active"], "tc-generate-uat")
```

In `collect_next`, change the flow call to `flow_next(fm["id"], fm, body, concepts, manifest, flow_rel=rel)`.

- [ ] **Step 4: Run to verify they pass**

Run: `py tools/test_wiki_testmodel.py`, `py tools/test_wiki_next_banners.py`, `py tools/test_app_next_json.py`, then `py tools/wiki.py next`
Expected: all `OK`; `next` prints the empty-bundle banner on master without error.

- [ ] **Step 5: Commit**

```bash
git add tools/wiki_next.py tools/test_wiki_testmodel.py
git commit -m "next: six-step delivery precedence after render - draft export, grade, improve, strict, diff, final export (task 8)"
```

---

### Task 9: Operator app export action accepts `draft`

**Files:**
- Modify: `tools/app/actions.py` (`_export` ~line 99)
- Test: `tools/test_app_actions.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_export_draft_flag_is_a_strict_boolean():
    assert actions.build("export", {"story": "US-1", "name": "n", "draft": True}) == \
        ["export", "--story", "US-1", "--name", "n", "--draft"]
    assert actions.build("export", {"story": "US-1", "name": "n", "draft": False}) == \
        ["export", "--story", "US-1", "--name", "n"]
    assert actions.build("export", {"flow": "f-e2e", "name": "n", "draft": True}) == \
        ["export", "--flow", "f-e2e", "--name", "n", "--draft"]
    for bad in ("true", 1, None):
        try:
            actions.build("export", {"story": "US-1", "name": "n", "draft": bad})
        except actions.ActionError:
            continue
        raise AssertionError(f"draft={bad!r} must be refused")
```

- [ ] **Step 2: Run to verify it fails**

Run: `py tools/test_app_actions.py`
Expected: `ActionError: unexpected params: ['draft']`

- [ ] **Step 3: Implement** (replace `_export`)

```python
def _export(params):
    extra = set(params) - {"story", "flow", "name", "draft"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    story, flow, name = params.get("story"), params.get("flow"), params.get("name")
    draft = params.get("draft", False)
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ActionError(f"invalid workbook name: {name!r}")
    if not isinstance(draft, bool):
        raise ActionError(f"draft must be true or false, got {draft!r}")
    if bool(story) == bool(flow):
        raise ActionError("export needs exactly one of story or flow")
    tail = ["--draft"] if draft else []
    if story:
        if not isinstance(story, str) or not STORY_RE.fullmatch(story):
            raise ActionError(f"invalid story id: {story!r}")
        return ["export", "--story", story, "--name", name] + tail
    if not isinstance(flow, str) or not FLOW_RE.fullmatch(flow):
        raise ActionError(f"invalid flow slug: {flow!r}")
    return ["export", "--flow", flow, "--name", name] + tail
```

- [ ] **Step 4: Run to verify it passes**

Run: `py tools/test_app_actions.py`
Expected: `test_app_actions OK` (or its existing final line).

- [ ] **Step 5: Commit**

```bash
git add tools/app/actions.py tools/test_app_actions.py
git commit -m "app: export action accepts a boolean draft flag (task 9)"
```

---

### Task 10: Synthetic pipeline chain test and smoke wiring

**Files:**
- Create: `tools/test_pipeline_chain.py`
- Modify: `tools/smoke.py` (unit-test list ~line 365; non-fast export ~line 425)

**Interfaces:**
- Consumes: everything from Tasks 1-7 through `score_scope(load_all=...)`, `write_packs`, `carry_forward`, `load_judgments`, `write_changes`, `export_gate`, `render_xlsx`.

- [ ] **Step 1: Write the chain test** (create `tools/test_pipeline_chain.py`)

```python
#!/usr/bin/env python3
"""The draft-first pipeline end to end over SYNTHETIC data
(run: py tools/test_pipeline_chain.py). Stands in for a smoke e2e that
cannot run against the tracked wiki without writing a real story's round
files (plan: Global Constraints). Every path is redirected to a temp dir."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rubric_judge as rj  # noqa: E402
import wiki_export as wx  # noqa: E402
from eval_rubric import score_scope  # noqa: E402
from wiki_rubric import sealed_digest, tc_record  # noqa: E402
from wiki_suite import render_xlsx  # noqa: E402

BODY1 = ("# Objective\n\no\n\n# Preconditions\n\n1. p\n\n# Test Data\n\n**Amount** = 100\n\n"
         "# Steps\n\n1. Enter.\n\n# Expected Results\n\n1. Accepted.\n")
BODY2 = BODY1.replace("**Amount** = 100", "**Amount** = 1 (min)")
ITEMS = [{"id": "BVA-01", "technique": "BVA", "kind": "boundary", "basis": ["S-AC1"], "feasible": True}]
STORY = {"type": "User Story", "id": "US-S", "title": "S",
         "acceptance_criteria": [{"id": "S-AC1", "text": "Accepted when 1 or more."}],
         "business_rules": [], "test_model": {"status": "confirmed", "items": ITEMS}}
MODULE = {"type": "Module", "id": "m", "title": "Mod"}


def _tc(tid, body, status="active"):
    fm = {"type": "Test Case", "id": tid, "status": status, "technique": "BVA",
          "title": tid, "priority": "P1", "module": "/modules/m.md", "kind": "sit",
          "covers": ["/stories/US-S.md#S-AC1"], "verifies_rules": [],
          "coverage_items": ["BVA-01"]}
    return f"testcases/sit/US-S/{tid}", fm, body


def _wiki(tcs):
    concepts = {"stories/US-S": (STORY, "", None), "modules/m": (MODULE, "", None)}
    hashes = {}
    for rel, fm, body in tcs:
        concepts[rel] = (fm, body, None)
        hashes[rel] = "sha256:" + str(abs(hash(body)))
    return concepts, {"tc_hashes": hashes}


def _judge(scope, rnd, lens, verdicts, h):
    rj.judgment_path(scope, rnd, lens).parent.mkdir(parents=True, exist_ok=True)
    rj.judgment_path(scope, rnd, lens).write_text(json.dumps(
        {"rubric_hash": h, "scope": scope, "round": rnd, "lens": lens,
         "verdicts": verdicts}), encoding="utf-8")


def _v(tc, dim, band):
    return {"tc": tc, "dimension": dim, "band": band, "rationale": "read it", "gap": ""}


def _merge(load_all, rnd, judge_dims):
    base = score_scope("story", "US-S", load_all=load_all)
    cur = {t["id"]: base["_tc_hashes"].get(t["rel"]) for t in base["_tcs"]}
    per_tc, per_scope, _n, present = rj.load_judgments(
        "US-S", rnd, base["rubric_hash"], [t["id"] for t in base["_tcs"]],
        judge_dims, current_hashes=cur)
    res = score_scope("story", "US-S", load_all=load_all, judgments=per_tc,
                      scope_judgments=per_scope)
    res["round"] = rnd
    res["judges_present"] = sorted(present)
    res["judges_missing"] = sorted(set(rj.LENSES) - present)
    public = {k: v for k, v in res.items() if not k.startswith("_")}
    rj.score_path("US-S", rnd).write_text(json.dumps(public, indent=1), encoding="utf-8")
    return res


def test_chain_draft_grade_carry_diff_final():
    d = Path(tempfile.mkdtemp(prefix="chain-"))
    old = (rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR)
    rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = d, d / "packs", d / "judgments"
    try:
        from rubric import dimensions
        # threshold 0: this test proves the CHAIN (draft -> carry -> diff ->
        # gated final), not the number a two-case synthetic set scores.
        cfg = {"rubric": {"threshold": 0, "version": "v1"},
               "ids": {"tc_format": "{story_num}-AC{ac_num:02d}-{seq:02d}", "story_prefix": "US-"}}
        # round 0: two cases rendered and sealed
        tcs0 = [_tc("S-AC01-01", BODY1), _tc("S-AC01-02", BODY1)]
        concepts0, manifest0 = _wiki(tcs0)
        export_tcs0 = [(r, f, b) for r, f, b in tcs0]
        digest0 = sealed_digest(manifest0["tc_hashes"], [r for r, _f, _b in tcs0])
        # 5 draft export
        render_xlsx(export_tcs0, "S", d / "draft.xlsx",
                    concepts={k: (v[0], v[1]) for k, v in concepts0.items()},
                    manifest=manifest0, draft=True)
        wx.write_draft_snapshot("US-S", "story", export_tcs0, manifest0, "draft.xlsx",
                                "sha", "v1", rj.draft_path("US-S"))
        assert wx.export_gate("US-S", "story", digest0, cfg)[1], "final refused before grading"
        # 6-7 round 1
        load0 = lambda: (concepts0, manifest0)
        base = score_scope("story", "US-S", load_all=load0)
        judge_dims = {x["id"] for x in dimensions(base["_rub"]) if "judge" in x["scored"]}
        h = base["rubric_hash"]
        for lens, dims in (("A", ["T1.4", "T1.5"]), ("B", ["T1.7"]), ("C", ["T1.8"])):
            _judge("US-S", 1, lens, [_v(t, dm, 3) for t in ("S-AC01-01", "S-AC01-02") for dm in dims], h)
        _judge("US-S", 1, "D", [_v("scope", "T2.5", 3), _v("scope", "T2.6", 3)], h)
        r1 = _merge(load0, 1, judge_dims)
        assert r1["partial"] is False and r1["sealed_digest"] == digest0
        # 8 the improver patched case 02 and added case 03
        tcs1 = [_tc("S-AC01-01", BODY1), _tc("S-AC01-02", BODY2), _tc("S-AC01-03", BODY2)]
        concepts1, manifest1 = _wiki(tcs1)
        load1 = lambda: (concepts1, manifest1)
        rj.patch_path("US-S", 1).write_text(json.dumps({"scope": "US-S", "round": 1, "patches": [
            {"op": "set", "ac": "AC1", "seq": 2, "field": "data", "value": "x", "closes": "G3.1"},
            {"op": "add", "closes": "G1.1", "test_case": {"ac": "AC1", "seq": 3}}]}), encoding="utf-8")
        # 9 round 2 pack with carry-forward
        base2 = score_scope("story", "US-S", load_all=load1)
        carried = rj.carry_forward("US-S", 2, base2["_tcs"], base2["_tc_hashes"], h, judge_dims)
        assert carried == {"A": ["S-AC01-01"], "B": ["S-AC01-01"], "C": ["S-AC01-01"]}, carried
        base2["round"] = 2
        rj.write_packs(base2, base2["_tcs"], base2["_fm"], base2["_rub"], 2, base2["_mech_by_tc"], exclude=carried)
        a = (d / "packs" / "US-S-r2-A.md").read_text(encoding="utf-8")
        assert "### S-AC01-01" not in a and "### S-AC01-02" in a and "### S-AC01-03" in a, a
        for lens, dims in (("A", ["T1.4", "T1.5"]), ("B", ["T1.7"]), ("C", ["T1.8"])):
            _judge("US-S", 2, lens, [_v(t, dm, 4) for t in ("S-AC01-02", "S-AC01-03") for dm in dims], h)
        _judge("US-S", 2, "D", [_v("scope", "T2.5", 4), _v("scope", "T2.6", 4)], h)
        r2 = _merge(load1, 2, judge_dims)
        assert r2["partial"] is False, "carried verdicts complete lens A/B/C for case 01"
        assert rj.carried_counts("US-S", 2) == {"A": 1, "B": 1, "C": 1}
        digest1 = r2["sealed_digest"]
        # 11 diff
        state = rj.rubric_state("US-S", digest1, 0, "v1")
        assert state["current"] == {"round": 2, "score": r2["score"]}, state
        current = {fm["id"]: tc_record(rel, fm, body, manifest1["tc_hashes"]) for rel, fm, body in tcs1}
        snapshot = json.loads(rj.draft_path("US-S").read_text(encoding="utf-8"))
        cause = rj.patch_tc_index("US-S", "story", json.loads(rj.patch_path("US-S", 1).read_text(encoding="utf-8")), cfg)
        jp, _mp = rj.write_changes("US-S", "story", snapshot, current, state, cause, digest1, 0, "v1")
        doc = json.loads(jp.read_text(encoding="utf-8"))
        assert doc["counts"] == {"added": 1, "changed": 1, "removed": 0, "unchanged": 1}, doc["counts"]
        td = next(c for c in doc["changes"] if c["kind"] == "changed" and c["field"] == "Test Data")
        assert td["closes"] == "G3.1", td
        # 12 final export gate + workbook
        cur, err = wx.export_gate("US-S", "story", digest1, cfg)
        assert cur == {"round": 2, "score": r2["score"]} and err is None, err
        render_xlsx([(r, f, b) for r, f, b in tcs1], "S", d / "final.xlsx",
                    concepts={k: (v[0], v[1]) for k, v in concepts1.items()}, manifest=manifest1,
                    grade={"round": 2, "score": r2["score"], "threshold": 0, "version": "v1"},
                    changes=wx.changes_for(digest1, doc))
        from openpyxl import load_workbook
        log = load_workbook(d / "final.xlsx")["Change Log"]
        assert log["C2"].value.startswith("Graded round 2:"), log["C2"].value
        assert log["C3"].value.startswith("Changed Test Data"), log["C3"].value
        assert "Added" in log["C4"].value, log["C4"].value
    finally:
        rj.RUBRIC_BUILD, rj.PACK_DIR, rj.JUDGMENT_DIR = old
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_pipeline_chain OK")
```

- [ ] **Step 2: Run it**

Run: `py tools/test_pipeline_chain.py`
Expected: `[PASS] test_chain_draft_grade_carry_diff_final` and `test_pipeline_chain OK`. If a step fails, the failing assertion names the stage; fix the owning task's code, not the test.

- [ ] **Step 3: Wire smoke** (`tools/smoke.py`)

After the `run(["tools/test_rubric_judge.py"], ...)` line add:

```python
run(["tools/test_wiki_export.py"], name="unit: draft/final export, workbook marks, gate")
run(["tools/test_rubric_carry.py"], name="unit: round-N verdict carry-forward")
run(["tools/test_rubric_diff.py"], name="unit: draft -> final diff")
run(["tools/test_pipeline_chain.py"], name="unit: draft-first pipeline chain (synthetic)")
```

Replace the non-fast story export block with:

```python
    _exportable = SIT_STORIES or stories_with("status: aligned")
    if not _exportable:
        print("[SKIP] story export: bundle has no story to export")
    else:
        # The final export is gated on a current strict score, which a smoke
        # run must not manufacture. The DRAFT export is the ungated first cut;
        # a second draft on an unchanged set is a refusal by design, so accept
        # either outcome and assert on the message.
        _snap = ROOT / "build/rubric" / f"{_exportable[0]}-draft.json"
        _had = _snap.exists()
        out = run(["tools/wiki.py", "export", "--story", _exportable[0],
                   "--name", "smoke-suite", "--draft", "--no-commit"],
                  expect=1 if _had else 0,
                  name=f"story draft export ({_exportable[0]}, "
                       f"{'refuses: unchanged set' if _had else 'writes DRAFT r0'})")
        assert ("already exported" in out) if _had else ("DRAFT r0" in out), out
        if not _had:
            _snap.unlink(missing_ok=True)      # leave the operator's build/ as found
```

- [ ] **Step 4: Run lint and smoke**

Run: `py tools/wiki.py lint` then `py tools/smoke.py --fast`
Expected: `0 errors` and `SMOKE OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/test_pipeline_chain.py tools/smoke.py
git commit -m "smoke: draft-first pipeline chain test; story export in smoke uses --draft (task 10)"
```

---

### Task 11: Skills, guides, CLI reference, playbook, README

**Files:**
- Modify: `.claude/skills/tc-generate-sit/SKILL.md`, `.claude/skills/tc-generate-uat/SKILL.md`, `.claude/skills/tc-rubric/SKILL.md`
- Modify: `docs/skills/tc-generate-sit.md`, `docs/skills/tc-generate-uat.md`, `docs/skills/tc-rubric.md`, `docs/cli.md`, `docs/playbook.md`, `README.md`

- [ ] **Step 1: `tc-generate-sit/SKILL.md`**

Insert after step 3's paragraph (before `3.5`), as a new step:

```
3a. **Draft export - the first cut.** Right after the first `py tools/wiki.py
   seal`:

   ```
   py tools/wiki.py export --story <id> --name <id>-sit --draft
   ```

   This writes the org workbook marked **DRAFT (ungraded, round 0)**, keeps a
   snapshot for the change log, and commits. **Open it for the human**
   (`start "<path>"` on Windows). The grade loop below runs while they
   review. `wiki next` names this command; do not skip to 3.5.
```

In step 3.5, after `--round 2 --pack`, add the sentence: `Round 2 packs carry forward the round 1 verdicts of every test case whose sealed content is unchanged; a lens whose pack says *Nothing to judge for this lens this round* needs no subagent. Never write or edit a `.carried.json` yourself.`

Replace step 6 with:

```
6. **Diff, then final export**:
   ```
   py tools/eval_rubric.py --story <id> --diff
   py tools/wiki.py export --story <id> --name <id>-sit
   ```
   The final export refuses without a non-PARTIAL, at-threshold score on the
   currently sealed set (that is the `--strict` gate, enforced). It fills the
   workbook's **Change Log** sheet from the diff: score delta, every changed
   field and the gap it closed. **Open the workbook** and point the human at
   the Change Log. For a multi-story workbook use `suite compile`.
```

Add to Red flags:

```
- `export refused: ... no score on the currently sealed set` and you reach for
  `--draft` to ship the final → the draft is round 0 only. Re-score (or run
  the missing lens), then export. Stop.
```

- [ ] **Step 2: `tc-generate-uat/SKILL.md`**

Add after step 2 (before 2.5):

```
2a. **Draft export**: after the first seal,
   `py tools/wiki.py export --flow <stem> --name <stem>-uat --draft` - the
   DRAFT round 0 workbook for the human, with the snapshot the change log
   needs. Open it; the grade loop runs while they review.
```

In 2.5 add the same carry-forward sentence as SIT. Replace step 4 with:

```
4. **Diff, then final export**: `py tools/eval_rubric.py --flow <stem> --diff`,
   then `py tools/wiki.py export --flow <stem> --name <stem>-uat` (refuses
   without a current strict score; fills the Change Log). `suite compile
   <uat-suite>` for the multi-flow workbook.
```

- [ ] **Step 3: `tc-rubric/SKILL.md`**

In Step 3.5 d, append:

```
                Round 2 packs are SMALLER: the engine copies round 1's A/B/C
                verdicts for every test case whose sealed hash is unchanged
                into judgments/<id>-r2-<L>.carried.json and lists only the
                touched cases in the pack. Lens D always reads the whole set.
                A pack that says "Nothing to judge for this lens this round"
                needs no subagent. A fresh verdict for a carried case is
                allowed and wins.
```

Add to Hard rules: `- Never write or edit a `.carried.json`; the engine writes it from round N-1's verdicts and drops any entry whose test case changed since.` Add to "The three artifacts" a fourth line: `4. **Draft snapshot and changes** - `build/rubric/<scope>-draft.json` (written by `wiki export --draft`) and `<scope>-changes.json/.md` (written by `eval_rubric --diff`), the change log the final workbook carries.`

- [ ] **Step 4: Guides and reference**

`docs/skills/tc-generate-sit.md`: add "### 3a. Draft export" after "### 3. Render" with the command and the sentence "You receive the DRAFT round 0 workbook now and review it while the grade loop runs." Replace "### 5. Evaluate, export, commit" body with the diff + final export commands and "The final export refuses without a current strict score and fills the Change Log sheet from the diff."

`docs/skills/tc-generate-uat.md`: same two edits with `--flow <stem>`.

`docs/skills/tc-rubric.md`: in "The loop, exactly one round", after line `d.`, add `   round 2 packs list only test cases changed since round 1; unchanged verdicts are carried (judgments/<id>-r2-<L>.carried.json)`. Add a section "## Draft, diff, final" with the three commands and what each writes.

`docs/cli.md`: in "Suites and export" replace the export line with:

```
py tools/wiki.py export --story <id> [--name <n>] --draft   # DRAFT r0 workbook + snapshot, right after seal
py tools/wiki.py export --story <id> [--name <n>]           # final: refuses without a current strict score; fills Change Log
py tools/wiki.py export --flow <stem> [--name <n>] [--draft]
```

and in "Grading" add `py tools/eval_rubric.py --story <id> --diff   # draft snapshot -> current sealed set: build/rubric/<id>-changes.{md,json}`. Under `build/` outputs add `<id>-draft.json`, `<id>-changes.md/json`, `judgments/<id>-rN-<L>.carried.json`.

`docs/playbook.md`, section "Generate and grade": replace the numbered list with:

```
1. writes the spec at `tools/sit_specs/US-XXXX.yaml` with `coverage_items`
   on every entry, renders and seals;
2. **exports the draft** (`export --story US-XXXX --name <n> --draft`): the
   DRAFT round 0 workbook is yours to review now;
3. runs one grade round while you review: `eval_rubric --round 1 --pack`,
   four judge lenses, gap report, one improver patch, re-render with
   `--force`, `--round 2` (only changed test cases are re-judged);
4. diffs draft against final (`eval_rubric --diff`) and **exports the
   final**, whose Change Log sheet lists every difference and why. The final
   export refuses without a current score at the threshold.
```

`README.md`: in the loop paragraph, after the generate sentence add: "You get the workbook twice: a labelled draft right after the first seal, and the graded final with a change log when the rubric round finishes."

- [ ] **Step 5: Verify and commit**

Run: `py tools/wiki.py lint`, `py tools/smoke.py --fast`
Expected: `0 errors`, `SMOKE OK`.

```bash
git add .claude/skills docs README.md
git commit -m "docs: draft-first pipeline - draft export step, carry-forward note, diff + gated final export in skills, guides, cli, playbook"
```

---

### Task 12: Finish

- [ ] **Step 1: Full verification on master**

Run in order: `py tools/wiki.py lint`, `py tools/smoke.py --fast`, and each new test file directly. All must pass; `smoke` must end with `[PASS] repo left clean` and `SMOKE OK`.

- [ ] **Step 2: Pilot on a project branch** (spec 9.9; needs the human's go-ahead because it touches project content)

On `<project-branch>`: `git merge master`, then for the pilot story run the protocol from step 3a: `export --story <id> --name <id>-sit --draft`, `--round 2 --pack` (observe the carried counts), `--diff`, `export --story <id> --name <id>-sit`. Open the final workbook's Change Log sheet and compare with `build/rubric/<id>-changes.md`. Record the draft and final timestamps in the merge commit message.

- [ ] **Step 3: Hand off** via `superpowers:finishing-a-development-branch`.
