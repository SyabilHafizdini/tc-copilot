# Draft-first generation pipeline

Design spec. Companion diagram: `2026-09-25-draft-first-pipeline.html` (same
directory; standalone HTML, open in a browser).

Branch: `master` (platform base). Project branches receive it by merge or
cherry-pick, never the other way round.

## 1. Goal

Deliver the SIT / UAT workbook to the human **twice**: a labelled draft the
moment the first rendered set is sealed, and the graded final with a change
log when the rubric loop finishes. Cut the wall-clock of round 2 by having the
judges re-read only the test cases the improver actually changed.

Today the human sees nothing until eleven LLM passes have run (two serial
authoring passes, four judges, one improver, four judges). Seven of those
passes add nothing the human can look at. After this change the human waits
for the coverage-card confirmation plus one LLM pass, then reviews the draft
while the grade loop runs behind it.

## 2. What does not change

Every rule in `CLAUDE.md` and the skills stands:

- Nothing renders before the human confirms the coverage card. The draft is
  the real rendered, sealed set - never a preview of unconfirmed content.
- Only a human asserts. The draft export asserts nothing.
- Exactly one improve round. No third round, ever.
- No verdict is ever edited. A carried-forward verdict is a **copy** of a
  verdict for content whose sealed hash has not changed; it is dropped, not
  adjusted, the moment the hash differs.
- Generated files are never hand-edited. The diff reads sealed content and
  writes only under `build/`.
- Every mutation is a `tc-agent` commit. `tools/` stays LLM-free.
- Refusals are the product. This change adds two refusals and removes none.

## 3. The pipeline

Twelve stages, three lanes (human / agent LLM / deterministic tooling). Stages
1-4 and 6-8 are today's protocol unchanged. Stages 5, 9, 11 and 12 are new.

| # | Stage | Lane | Command | New |
|---|---|---|---|---|
| 1 | Gate | tooling | `wiki gate --story <id>` | |
| 2 | Propose map + model, agent corrects/enriches, card emitted | tooling → LLM 1 | `coverage --propose`, `testmodel --propose` | |
| 3 | Human confirms the card | human → tooling | `wiki assert story <id> --by <h> --card <c>` | |
| 4 | Spec, render, seal | LLM 2 → tooling | `render_sit.py --story <id>`, `wiki seal` | |
| 5 | **Draft export** | tooling → human | `wiki export --story <id> --name <n> --draft` | yes |
| 6 | Round 1 pack + four judges | tooling → LLM 3-6 | `eval_rubric.py --story <id> --round 1 --pack` | |
| 7 | Merge, gap report, improver patch | tooling → LLM 7 | `eval_rubric.py --story <id> --round 1` | |
| 8 | Apply patch, forced re-render, re-seal | tooling | `--apply-patch`, `render_sit.py --force`, `wiki seal` | |
| 9 | **Round 2 pack with carry-forward**, judges on touched TCs | tooling → LLM 8-11 | `eval_rubric.py --story <id> --round 2 --pack` | yes |
| 10 | Merge round 2, delta, regression check, verify, strict gate | tooling | `--round 2`, `lint`, `rtm`, `coverage`, `testmodel`, `eval_golden`, `--round 2 --strict` | |
| 11 | **Diff** draft snapshot vs sealed set | tooling | `eval_rubric.py --story <id> --diff` | yes |
| 12 | **Final export**, refuses without a current strict score, fills Change Log | tooling → human | `wiki export --story <id> --name <n>` | yes |

UAT is the same shape with `--flow <stem>` in place of `--story <id>`: the
journey and scenario model stand in for the card, the run-record script for
the spec, and the improver's patch is applied to the run-record's wording
tables by the agent (the engine's `--apply-patch` stays SIT-only, as today).
Stages 5, 9, 11 and 12 work from sealed hashes, so they need no knowledge of
how the change was made.

## 4. Components

### 4.1 Draft export - `wiki export ... --draft`

`cmd_export` in `tools/wiki.py` gains `--draft` and `--flow <stem>`.

Behaviour with `--draft`:

1. `refuse_if_unsealed("export")` as today.
2. refuse when the current sealed set already has a round score (its
   digest equals some `<scope>-r<N>-score.json` digest): a graded set is not
   a first cut. A changed, ungraded set overwrites the snapshot (a new first
   cut). Refusal: `export refused: the sealed set of <scope> was graded in
   round N; a graded set is not a first cut. Next: py tools/eval_rubric.py
   <flag> <scope> --diff, then py tools/wiki.py export <flag> <scope> --name
   <n>`. *(Amendment A2, final-review fix wave: replaces the earlier
   "unchanged set" refusal, which sent the agent back to a second draft
   after the improve round.)*
3. Workbook name is `<name>-draft`. Files:
   `build/inventory/<kind>/<name>-draft_<ts>.xlsx` and
   `<name>-draft-latest.xlsx` (via `inventory_paths`).
4. The workbook is visibly marked in the org header block (`_fill_toc`):
   - B1 title: `DRAFT (ungraded, round 0) - AGILE TEST SPECIFICATIONS - Table of Contents`
   - row 8 "Version No.": `DRAFT r0`
   - Revision History row 18 "Summary of Changes":
     `DRAFT first cut - rendered and sealed, not yet graded against the
     ISO/IEC/IEEE 29119-4 rubric. A final workbook with a Change Log follows.`
   - Change Log sheet: one row, `Test Case ID` empty, description
     `Draft round 0 - no changes yet.`
5. Writes the diff snapshot `build/rubric/<scope>-draft.json` (format in 5.1).
6. Commits as tc-agent: `export(<name>-draft): N TCs [draft r0]`.

The draft skips the rubric gate **because the workbook says so**. That is the
difference between an honest draft and a workaround.

Behaviour without `--draft` is the final export, 4.2.

`--flow <stem>`: selects active `kind: uat` test cases whose `covers` resolve
to that flow, sorted by `tc_sort_key` (journey order), rendered with
`test_type="UAT"`. Today `cmd_export` reads `--story` only; the operator app
already builds `export --flow`, so this closes a real gap as well.

### 4.2 Final export gate - `wiki export` without `--draft`

Promotes the prose rule "`--round 2 --strict` is the export gate" into a CLI
refusal. `cmd_export` refuses unless **all** of:

1. `build/rubric/<scope>-r2-score.json` exists - the improve round ran.
2. Some `build/rubric/<scope>-r<N>-score.json` has `partial: false`,
   `score >= config rubric.threshold`, `rubric_version == config
   rubric.version`, and `sealed_digest` equal to the digest of the currently
   sealed scope (5.3). The highest such N is "the current score".

Refusal text names the failing condition and the next command, e.g.

```
export refused: US-1234 has no score on the currently sealed set.
  The latest score (round 2, 93.44) was computed on a different sealed set.
  Next: py tools/eval_rubric.py --story US-1234 --round 2   (re-merge on the
        current set; if round 1 was restored after a regression, --round 1)
  A first cut without the gate is: py tools/wiki.py export --story US-1234
        --name <n> --draft
```

On success:

- Workbook as today, plus row 8 "Version No." `r<N> · rubric <score>` and the
  Revision History summary `Graded round <N>: score <score> (threshold
  <t>), rubric <version>`.
- If `build/rubric/<scope>-changes.json` exists and its `to_digest` equals
  the current digest, the **Change Log** sheet is filled from it (one row per
  change, 4.4). If it does not exist, the sheet gets one row
  `No draft snapshot - change log not available` and the export still
  succeeds (the diff is a courtesy to the reviewer, not a gate).
- Commit: `export(<name>): N TCs, rubric r<N> <score>`.

Regression case: round 2 restored to round 1. The current sealed set is the
round 1 content; `<scope>-r1-score.json` carries its digest, `<scope>-r2-
score.json` exists (condition 1) but has a different digest, so the current
score is round 1. No extra step. The strict protocol command in the skill
becomes `--round <current> --strict`; the skill text says which.

Because the score JSON is a `build/` artifact, a fresh clone cannot final-
export until it has been re-scored. That is the same truth `wiki next`
already tells about a clone ("not graded").

### 4.3 Round N+1 carry-forward - `eval_rubric --round N --pack`, N ≥ 2

Judges A, B and C are per test case; lens D is per set. A per-test-case
verdict describes one sealed file. If that file's sealed hash is unchanged
since the previous round, re-reading it is waste.

Mechanism, in `tools/rubric_judge.py`:

1. Every score JSON's `test_cases[i]` gains `sealed_hash` (the manifest
   `tc_hashes` value for that TC's file at scoring time). Every score JSON
   gains `sealed_digest` (5.3).
2. On `--round N --pack` with N ≥ 2, for each lens in A, B, C:
   - Load round N-1's judgment file for that lens if it exists **and** was
     accepted (same `load_judgments` validation, same rubric hash). Missing
     or rejected → no carry for that lens; full pack as today.
   - For each active TC whose current `tc_hashes` value equals the
     `sealed_hash` recorded for it in `<scope>-r<N-1>-score.json`: copy its
     round N-1 verdicts for the lens's dimensions, verbatim, adding
     `"carried_from": N-1`, into
     `build/rubric/judgments/<scope>-r<N>-<L>.carried.json`
     (same envelope as a judgment file: `rubric_hash`, `scope`, `round`,
     `lens`, `verdicts`). A TC with no round N-1 verdict, or with a changed
     hash, or new this round, is **not** carried.
   - The pack for that lens contains only the TCs **not** carried, under a
     header line
     `Carried forward from round <N-1>: <k> test case(s) unchanged since
     their last verdict - do not band them; band only the <m> below.`
     If m == 0 the pack says `Nothing to judge for this lens this round;
     every verdict is carried. Do not write a judgment file.` and the skill
     tells the agent to skip that subagent.
   - Lens D is never carried. Its pack is the whole set, as today.
3. `load_judgments(scope, N, ...)` reads, per lens, the fresh file
   `<scope>-r<N>-<L>.json` first (if present), then the `.carried.json`
   (if present). A fresh verdict for a `(tc, dim)` **wins**; a carried one
   fills only what the fresh file does not band. A judge who re-bands an
   untouched TC has done a fresh read, which is always allowed. Each carried
   verdict is re-checked at load time: if the TC's current hash no longer
   equals `sealed_hash` in round N-1's score JSON, that verdict is dropped
   with a printed note (`carried verdict dropped: <tc> changed since round
   <N-1>`), so the dimension reads NOT ASSESSED and the score is PARTIAL -
   the honest reading. Duplicate / malformed / wrong-hash entries in a
   carried file are hard refusals exactly like a judge file.
4. `judges_present` lists a lens as present when either file exists;
   the score JSON gains `carried: {"A": k, "B": k, "C": k}` counts, and
   the printed round summary says `round 2: 31 fresh, 48 carried (A) ...`.

The delta (`round_delta`) and `--strict` are unchanged. Two scores still
compare only under the same rubric hash.

Why hash-based, not patch-based: the patch names `(ac, seq)` for SIT only;
a UAT wording change lives in the run-record script; a regression restore
touches every patched TC back. Sealed hashes cover all three without the
engine knowing how a file changed.

### 4.4 Diff - `eval_rubric --story <id> --diff` / `--flow <stem> --diff`

LLM-free. Inputs: `build/rubric/<scope>-draft.json` (5.1) and the current
sealed set. Refuses if there is no draft snapshot
(`--diff refused: no draft snapshot for <scope>. Next: py tools/wiki.py
export --story <id> --name <n> --draft` - a diff needs a "from").

Algorithm:

1. Build the current record set exactly as the snapshot did (5.1), from the
   same reader, so unchanged content yields byte-equal records.
2. By TC id:
   - in current, not in snapshot → **added**;
   - in snapshot, not in current, or current status `retired` → **removed**
     (with the retirement reason when present);
   - in both with equal `hash` → unchanged (not listed);
   - in both with different `hash` → **changed**: one line per field whose
     value differs, with old and new values. Fields: `title`, `technique`,
     `priority`, `coverage_items`, `covers`, `verifies_rules`, and every
     body section by heading. Long section values are shown as a unified
     line diff (difflib) capped at 40 lines per field in the markdown; the
     JSON carries full old/new.
3. Cause join, best effort: if `build/rubric/<scope>-r1-patch.json` exists,
   map each `set` op `(ac, seq)` → TC id via `config ids.tc_format` and the
   scope's story number, and each `add` op's `test_case.(ac, seq)` the same
   way; a flow patch op joins only when it carries a `tc` key. A change with
   a matching op shows `closes: G3.4` and the op's field; otherwise
   `cause: not recorded`.
4. Score header: `from` = the draft snapshot's `score` if a score existed at
   draft time (usually none: `null` / "ungraded"), then every round's score
   for the scope, the delta line, and `regression: round 1 restored` when
   the current score's round is lower than the highest round file.
5. Writes `build/rubric/<scope>-changes.md` and `<scope>-changes.json`
   (5.2). Never commits (`build/` is ignored). Prints the counts:
   `US-1234: 29 added, 14 changed, 0 removed, 36 unchanged`.

### 4.5 `wiki next`

`story_next` precedence after "coverage confirmed, model confirmed, no stale,
active > 0" becomes:

1. no draft snapshot for the scope, or the snapshot's digest equals
   neither the current digest nor the digest of any round score file (a
   draft that grading has started on is delivered) *(amendment A1,
   final-review fix wave)* →
   state `rendered · N active TC(s) - first cut NOT delivered`, command
   `py tools/wiki.py export --story <id> --name <id>-sit --draft`, skill
   `tc-generate-sit (step 4a: draft export - the human reviews while the
   grade loop runs)`.
2. no `<scope>-r1-score.json` → `NOT graded` → `--round 1 --pack` (as today,
   with the explicit round).
3. no `<scope>-r2-score.json` → `graded round 1 - improve round NOT run` →
   `py tools/eval_rubric.py --story <id> --round 1` (merge / improver),
   skill tc-rubric.
4. no current score at threshold (4.2 condition 2) → `graded - no strict
   score on the current sealed set` → `py tools/eval_rubric.py --story <id>
   --round 2 --strict`, skill tc-rubric.
5. no changes file, or `to_digest` ≠ current → `ready - change log NOT
   built` → `py tools/eval_rubric.py --story <id> --diff`, skill
   tc-generate-sit (step 6).
6. otherwise → `graded r<N> <score> - ready to export` →
   `py tools/wiki.py export --story <id> --name <id>-sit`, skill
   tc-suite-author. The suite compile stays the command when the operator
   wants a multi-story workbook.

`flow_next` mirrors 1-6 with `--flow <stem>` and the run-record render.
`rubric_score_exists` is replaced by a helper `rubric_state(scope)` returning
the round files present, the current score (if any) and the digest match, so
`next`, `export` and `--diff` share one reading.

### 4.6 Skills and docs

- `tc-generate-sit/SKILL.md`: step **4a** after step 3's seal: the draft
  export command and the sentence "Open the draft for the human; the grade
  loop runs while they review." Step 3.5 gains "round 2 packs carry forward
  verdicts for unchanged test cases; a lens whose pack says *nothing to
  judge* needs no subagent." Step 6 becomes: `--diff`, then final `export`
  (which refuses without a current strict score), open the final workbook,
  point the human at the Change Log sheet. Red flag added: "`export refused:
  no score on the currently sealed set` and you reach for `--draft` to ship
  the final → the draft is round 0 only. Re-score. Stop."
- `tc-generate-uat/SKILL.md`: same three edits with `--flow`.
- `tc-rubric/SKILL.md`: 3.5 d gains the carry-forward paragraph and the
  `.carried.json` rule (never edit it; a fresh verdict wins). Hard rule
  added: "Never write a `.carried.json` yourself; the engine writes it."
- `docs/skills/tc-generate-sit.md`, `tc-generate-uat.md`, `tc-rubric.md`,
  `docs/cli.md`, `docs/playbook.md` (the "Generate and grade" section gets
  the two deliveries), `README.md` loop paragraph.
- `tc-help`: no change; it reads `wiki next`.

### 4.7 Operator app

`tools/app/actions.py::_export` accepts an optional boolean `draft` and
appends `--draft`. No other UI change in this spec; the existing export
surface gains the checkbox where it lives. (The Explore surface showing the
change log is a later sub-project.)

## 5. Data formats

### 5.1 Draft snapshot - `build/rubric/<scope>-draft.json`

```json
{
  "scope": "US-1234", "kind": "story",
  "exported_at": "2026-09-25T10:14:02+08:00",
  "workbook": "build/inventory/sit/US-1234-sit-draft_20260925-101402.xlsx",
  "seal_commit": "<git sha of HEAD at export time, i.e. the last seal commit>",
  "sealed_digest": "sha256:...",
  "rubric_version": "v1",
  "score": null,
  "test_cases": {
    "1234-AC01-01": {
      "rel": "testcases/sit/1234-AC01-01",
      "hash": "<manifest tc_hashes value>",
      "status": "active",
      "title": "...", "technique": "UC", "priority": "P1",
      "coverage_items": ["UC-AC01-main"],
      "covers": ["stories/US-1234#AC01"], "verifies_rules": [],
      "sections": {"Preconditions": "...", "Test Data": "...",
                   "Steps": "...", "Expected Results": "..."}
    }
  }
}
```

`sections` holds every `## ` heading of the TC body verbatim (via
`body_section`), so the diff never hardcodes the section list. The record
builder is one function, `tc_record(rel, fm, body, manifest)`, used by the
snapshot, the diff's current side, and the score JSON's `sealed_hash`.

### 5.2 Changes - `build/rubric/<scope>-changes.json` / `.md`

```json
{
  "scope": "US-1234", "kind": "story",
  "from": {"label": "draft r0", "digest": "sha256:...", "score": null,
           "exported_at": "..."},
  "to": {"label": "round 2", "digest": "sha256:...", "score": 93.44,
         "round": 2},
  "to_digest": "sha256:...",
  "rounds": [{"round": 1, "score": 70.77}, {"round": 2, "score": 93.44}],
  "delta": 22.67, "regression_restored": false,
  "counts": {"added": 29, "changed": 14, "removed": 0, "unchanged": 36},
  "changes": [
    {"tc": "1234-AC06-01", "kind": "changed", "field": "Test Data",
     "old": "...", "new": "...", "closes": "G3.1",
     "op": {"op": "set", "ac": "AC6", "seq": 1, "field": "data"}},
    {"tc": "1234-AC20-03", "kind": "added", "closes": "G1.19, G2.2",
     "title": "Quantity rejects a value below 1"},
    {"tc": "1234-AC02-02", "kind": "removed", "reason": "superseded"}
  ]
}
```

The markdown is the same content for humans: header with scores and delta,
then `## Added`, `## Changed` (one `###` per TC, one bullet per field with a
fenced line diff), `## Removed`.

Change Log sheet rows (Dashboard / Test Case ID / Description of Change):
`Dashboard` = the sub-story title as the Test Statistics sheet names it;
`Test Case ID` = display id (`TC-` prefix); `Description of Change` =
`Added - <title> (closes G1.19)` / `Changed Test Data, Expected Results
(closes G3.1)` / `Removed - superseded`. First row: `Graded round 2: 70.77
→ 93.44 (+22.67), rubric v1`.

### 5.3 Sealed digest

`sealed_digest(scope)` = `sha256` over the newline-joined, sorted
`"<rel> <tc_hashes[rel]>"` lines of the scope's **active** test cases. Same
active files, same content → same digest. Recorded in every score JSON, the
draft snapshot and the changes file; compared by `export`, `--diff` and
`wiki next`. One helper in `tools/wiki_rubric.py`, no second implementation.

## 6. Refusals added

| Command | Refuses when | Why |
|---|---|---|
| `export` (final) | no round 2 score file | the improve round never ran |
| `export` (final) | no non-PARTIAL, at-threshold score whose digest matches the sealed set | the workbook would carry a score for other content |
| `export --draft` | the current sealed set already has a round score (A2) | a graded set is not a first cut |
| `--round N` merge (incl. `--strict`) | `<scope>-rN-packed.json` exists and its hashes differ from the current set's | verdicts describe the content the judges read |
| `--diff` | no draft snapshot | no "from" side |
| `--round N --pack` | round N-1 judgment file present but invalid | carrying a rejected verdict launders it |

Nothing that refuses today stops refusing.

## 7. Testing

Unit tests, `tools/test_*.py`, using `testkit.py` fixtures and redirected
build dirs as the existing rubric tests do:

- `test_wiki_export_draft.py`: draft names, header marks, snapshot content,
  the unchanged-set refusal, `--flow` selection and ordering, commit
  message.
- `test_wiki_export_gate.py`: every final-export refusal in section 6 with
  its message; success fills Version No., Revision History and Change Log;
  the missing-changes-file courtesy row; the regression case picks round 1.
- `test_rubric_carry.py`: carried file written only for unchanged hashes;
  new TC never carried; lens D never carried; fresh verdict wins over
  carried; carried verdict dropped when the hash moved (score PARTIAL);
  invalid round N-1 file → refusal; empty pack text when m == 0; score JSON
  `sealed_hash`, `sealed_digest`, `carried` counts.
- `test_rubric_diff.py`: added / changed / removed / unchanged
  classification; per-field old/new; section diff capping; patch join for
  SIT `(ac, seq)` → id and the `not recorded` fallback; regression header;
  `to_digest`; no-snapshot refusal.
- `test_wiki_next_banners.py`: the six-step precedence in 4.5 for a story
  and a flow.
- `test_app_actions.py`: `draft: true` → `--draft`; any other value refused.

`tools/smoke.py --fast` gains one end-to-end case on the fixture story:
render → seal → draft export → r1 pack (no judges; PARTIAL) → synthetic
judge files → merge → patch → force render → seal → r2 pack shows carried
counts → diff → final export refused (PARTIAL) → synthetic r2 judges →
merge → final export succeeds with a filled Change Log. `SMOKE OK` on a clean
tree remains the definition of healthy.

Definition of done for the implementation: `py tools/wiki.py lint` 0 errors,
`py tools/smoke.py --fast` prints `SMOKE OK`, every test above passes, and
the pilot story on a project branch produces a draft, a change log and a
final workbook whose Change Log matches `<scope>-changes.md`.

## 8. Out of scope

- Any change to the coverage card, the test model, or the one-round rule.
- Scoring foreign workbooks (`tc-evaluate` foreign mode).
- Showing the change log inside the operator app's Explore surface.
- Diffing two arbitrary exports; the diff is draft → current only.
- Parallelising the two serial authoring passes (test model enrichment and
  spec authoring). They are the remaining wait before the first cut and are
  the subject of a separate spike if needed.

## 9. Implementation order

1. `sealed_digest` + `tc_record` helpers in `wiki_rubric.py`; score JSON
   gains `sealed_hash` / `sealed_digest`. Tests.
2. Draft export + snapshot + `--flow` in `wiki.py` / `wiki_suite.py`. Tests.
3. Carry-forward in `rubric_judge.py` (`write_packs`, `load_judgments`) and
   `eval_rubric.py` summary line. Tests.
4. `--diff` in `eval_rubric.py` + `rubric_judge.py`. Tests.
5. Final export gate + Change Log fill. Tests.
6. `wiki next` precedence + `rubric_state`. Tests.
7. App action flag. Test.
8. Skills, docs, README, smoke case. `lint`, `smoke --fast`.
9. Merge to the project branch, run the pilot story end to end, record the
   three timestamps (card confirm, draft, final) in the commit message.
