# CLI reference

Everything under `tools/` is deterministic and LLM-free. Python is the `py`
launcher. Every mutating `wiki` command auto-commits as `tc-agent`; add
`--no-commit` to batch steps. Commands marked **human** require `--by <name>`
and run only at a human's instruction. A flag takes its value as the next
argument (`--prd rental-payment`); the `=` form (`--prd=rental-payment`) is refused,
because it would otherwise be skipped without a word.

## Orientation

```
py tools/wiki.py next [--story <id>] [--json]   # what to do now + owning skill (read-only)
py tools/wiki.py status                          # story table, TC counts, one PRD <id> line each (adopted, staged)
py tools/wiki.py dashboard                       # build/status/dashboard.{json,html}
py tools/wiki.py app [--port 8765]               # operator app (needs FastAPI)
py tools/smoke.py [--fast]                       # health check; needs a clean tree
```

In the operator app, Settings and the dashboard list every registered PRD with
its adopted and staged versions; the Changes page lists each PRD's staged version and its pending report id, with the
`diff --prd <id>` command to read the changes; it does not show the report body (approve and reject
stay CLI commands, run at your instruction); Documents and Explore group PRD sections under their PRD; and
the suite preview has a PRD filter.

The app's docked chat is Off by default. Switch it on under Settings,
Appearance, chat; the choice is kept in the browser.

## Intake

```
py tools/wiki.py triage [--apply] [--card <card>] [--prd <id>] [--prd-title "<title>"] [--prd-version N]
py tools/wiki.py ingest-prd [--prd <id>] [--title "<title>"] | ingest-figma | ingest-decks | ingest-reference
py tools/wiki.py diff --prd [<id>]                            # adopted vs staged sections of one PRD
py tools/wiki.py approve-cr CR-NNN --by <you> [--prd <id>]    # human, at your instruction only
py tools/wiki.py reject-cr  CR-NNN --by <you> [--prd <id>]    # human, at your instruction only
```

A product can be described by several PRDs. Each has an id (a lowercase-hyphen
slug matching `^[a-z0-9][a-z0-9-]{1,63}$`, such as `rental-application`), a title,
and its own version line, recorded in the manifest `prds` registry. `--prd <id>`
is optional while exactly one PRD is registered; with several, a command that
needs it refuses and lists the ids (a bare `diff --prd` counts as omitted).
`ingest-prd --prd <new-id> --title "<title>"` registers a new PRD; `--title` is
required for a new id and ignored for a registered one. A new id is refused
when it has the form `v<digits>` (it would read as a version directory) or is
`index` or `log` (reserved file names); `ingest-prd`, `triage` and
`migrate-prds` apply this one rule.

On disk, per PRD: uploads `inputs/prd/<id>/vN/` (one pdf, docx or md per
version; only `v` plus a whole number from 1 counts as a version directory),
sections `sources/prd/<id>/<slug>.md` (section id `prd#<id>/<slug>`), staged
sections `staging/<id>/prd-vN.json`, change reports
`changereports/<id>/CR-NNN.md`. Report numbers are unique across the project.

`ingest-prd` refuses, before writing anything: a version directory with more
than one candidate document, a document that yields no sections, a heading
whose section file would be `index` or `log`, two sections with the same
heading path, and a version lower than the adopted one. The first version
adopts. When the newest version directory is the adopted version, an unchanged
document prints "nothing changed" and a changed one is refused, naming the next
version directory: adopted content changes only through an approved change
report. A newer version stages and writes that PRD's change report; running it
again on the same staged version writes no second report (a changed document
for a version with a pending report is refused). After a rejection,
re-ingesting an identical document writes nothing; a changed one produces a new
pending report. The new report does not name the rejected one; the `ingest-prd`
console output prints a note that does.

`approve-cr` and `reject-cr` need `--by` set to a real name and a report id of
the form `CR-<number>`; a report that belongs to another PRD is refused with the
`--prd` to use. A report can be approved only if it is for the PRD's currently
staged version, newer than the adopted one, and computed against the version
still adopted: staging v3 while v2's report is pending leaves v2's report
pending but unapprovable (the output names the report to act on; the old one
can only be rejected). Approval makes one commit carrying the assertion
trailer, never touches another PRD, and drops aligned stories that cite a
changed or removed section of that PRD to needs-review, once (the cause names a
removal); a human re-assert settles it. Rejection keeps the version staged;
`wiki next` then reports the rejection and that a corrected document is awaited.

`triage --apply` needs a PRD answer and a version answer for every PRD file
(`--prd`, `--prd-title` for a new id, `--prd-version`). It refuses, listing the
registered ids or naming the next version, when one is missing or wrong, and
when `--prd-title` is given without `--prd` (a title names a new PRD). It
never overwrites or deletes a PRD document: an occupied version directory is
refused, the refusal names the next free version, and the agent stops and asks
you; only you move an old document out. The Figma,
deck and reference routes do replace an existing file of the same name and say
"(REPLACES existing)" in the plan. After a rejected change report, a corrected
document goes through triage as the next version number, or you replace the
file under `inputs/prd/<id>/v<N>/` yourself and, once you say the file is in
place, the agent runs `ingest-prd --prd <id>`; the agent never deletes, moves
or replaces a document under `inputs/prd/`.

## Wiki integrity

```
py tools/wiki.py lint          # L1-L15 errors, W1-W10 warnings; exit 1 on any L
py tools/wiki.py manifest      # rebuild manifest.json from frontmatter
py tools/wiki.py index         # regenerate every index.md
py tools/wiki.py cascade       # staleness flags; never regenerates
py tools/wiki.py impact <ref>  # downstream impact of a concept or fragment
py tools/wiki.py rtm [--graph] # build/rtm/{matrix,trace,graph.json,gaps}
```

## Alignment and gates

```
py tools/wiki.py assert story|flow <id> --by <you> --card <card>   # human
py tools/wiki.py assert term|figma <id> --by <you>                 # human
py tools/wiki.py card revise|discard <card> --by <you> [--answer q=v]
py tools/wiki.py gate --story <id> | --flow <stem>                 # GATE OPEN or the reason
```

## Coverage and the test model

```
py tools/wiki.py coverage --story <id> [--propose] [--graph]
py tools/wiki.py testmodel --story <id> | --flow <id> [--propose [--force]]
```

`coverage --propose` writes a heuristic component-to-AC map at
`coverage_status: proposed`. `testmodel --propose` scaffolds the 29119-4 test
model at `status: proposed`. Both are confirmed by `assert --card`, never by
hand. `testmodel` without `--propose` shows the model and per-technique
`C = N / T`.

## Generation

```
py tools/render_sit.py --story <id> [--force]      # SIT from tools/sit_specs/<id>.yaml
py tools/render_uat.py --flow <FLOW-ID> [--force]  # UAT from tools/uat_specs/<FLOW-ID>.yaml
py tools/wiki.py seal                               # hash-seal rendered TCs
```

`--force` re-renders even when the pinned AC fragments are unchanged. It is
required after a spec-only edit, such as adding `coverage_items` or applying
an improver patch. A plain render also re-renders a test case whose lift
changed: a part a human confirmed through `doubts answer` renders High with
the remark `Source: <R-id> - human answer to <Q-id> (<by>, <date>).` and
`authored` + `resolution` in its frontmatter. Both renderers refuse, before
writing anything, a spec `confidence` level higher than the level the test
case was last authored with (the raise ratchet); there is no override flag.

## Grading (ISO/IEC/IEEE 29119-4 rubric)

```
py tools/eval_rubric.py --story <id> --round N [--pack]        # score, gaps, judge packs (+ <id>-rN-packed.json)
py tools/eval_rubric.py --story <id> --apply-patch <patch.json> # improver patch -> spec
py tools/eval_rubric.py --story <id> --round N --strict         # gate on config threshold; refuses if the set moved since --pack
py tools/eval_rubric.py --story <id> --diff   # draft snapshot -> current sealed set: build/rubric/<id>-changes.{md,json}
py tools/eval_golden.py [--strict]                              # compare with eval/golden
```

Outputs under `build/rubric/`: `<id>-rN-score.json`, `<id>-rN-gaps.md`,
`packs/<id>-rN-{A,B,C,D}.md`, `judgments/<id>-rN-<lens>.json` (written by the
judge subagents), `<id>-rN-delta.json`, `<id>-rN-packed.json`, `<id>-draft.json`,
`<id>-changes.md/json`, `judgments/<id>-rN-<L>.carried.json`.

## Flow builder

The operator app's **Plan > Flow Builder** page stitches SIT test cases into a
flow on a canvas:

- The left list holds every live SIT test case, by id and title, under the
  criterion it covers. Drag one onto the canvas (or press +) to make it a
  journey step. The step keeps the criterion too, because a journey entry is
  keyed by criterion (`ref`); the test case is recorded beside it as
  `source_tc`.
- A step starts with the test case's postcondition as its end state; edit it
  on the step. A step's "Criterion and options" lets you swap to another test
  case of the same criterion.
- Drag from the dot on a step's right edge to the next step to connect them.
  Where two lines leave one step, the upper one is the main path and the lower
  one becomes a branch. Select a line or a step and press Delete to remove it.
- The right panel shows the journey, branches and every possible path as you
  draw, and says what is still missing (an unconnected step, an end state).
- **Start from an existing flow** lays an existing journey out for editing.
  The journey list does not record where a branch leaves and rejoins, so that
  wiring is a best guess: check it.
- **Save as draft flow** runs the command below through the app's action
  allowlist.

```
py tools/wiki.py flow-draft <flow-draft-ID.json>
```

`flow-draft` writes `flows/<ID>.md` at `status: draft`. A drawing is a
proposal: the flow still goes through `tc-align` (card, scenario model, the
human's `assert flow --card`) before `tc-generate-uat` will walk it. It
refuses an id whose flow is already asserted, a criterion that does not exist,
a step with no end state, and a `source_tc` that is missing, retired, UAT, or
does not cover the step's criterion.

## Doubts

```
py tools/wiki.py doubts list [--story <id>] [--all] [--ungrouped] [--json]   # read-only
py tools/wiki.py doubts card --story <id> [--question Q1[,Q2,...]] [--top N]
py tools/wiki.py doubts answer --card <path> --by <user> [--story <id>]
py tools/wiki.py doubts observe --workbook <xlsx> --by <tester>
```

A doubt is a Medium / Low confidence part of a test case, id
`<scenario_id>#<part>`, derived from the specs. `doubts list` prints each
story's open doubts grouped under the questions of its register
`doubts/<id>.yaml`, in impact order, then the ungrouped ones. `--ungrouped`
shows only those, `--all` adds closed questions and doubts, `--json` adds
the authored text and basis hash of each part. Lint L15 validates every
register, every answer Resolution and every lifted test case part; W8 warns
while open doubts are ungrouped; W9 warns while a confirmed doubt is not
rendered. Owned by `tc-resolve`.

`doubts card` writes the deterministic card `build/cards/doubts-<id>-NNN.json`
(`card_type: doubts`, `register_hash`, one `open_questions` entry per eligible
question, in impact order). A question with open doubts is an `ask`; one whose
doubts were rewritten after an answer is a `confirm`; answered-and-waiting or
closed questions are left out. `--question` restricts to ids, `--top N` keeps the
first N. It refuses without a valid register or when nothing is eligible, and
commits nothing (`build/` is git-ignored). The human answers it with the
existing `card revise <card> --by <user> --answer <Q>=accept|<Q>="<text>"`
(one call per card; repeat `--answer` for several questions) or drops it with
`card discard <card> --by <user>`.

`doubts answer` is the only writer of an answer Resolution. It reads the card the
human answered, recomputes the same questions from the register and the specs,
and writes nothing unless every answered question passes. `accept` writes
`effect: confirms` with `confirmed_parts` (doubt to current basis); a text writes
`effect: corrects` with `member_basis` and the text verbatim. Each Resolution is
`resolutions/R-<story>-NN.md` (`answers: <Q>`, `card: <file>`), the card is
stamped `applied`, and one commit as tc-agent carries an
`Assertion-Event: cli-doubts-answer` trailer. Partial answers are allowed; emit a
new card for the rest. It refuses (exit 1, `doubts answer refused: ...`, nothing
written) when: `--card` or `--by` is missing, the card is absent, not JSON or not
a doubts card; the card's story has no register or differs from `--story`; there
are no answers; `--by` differs from the card's `human_response.by`; the card is
already applied; an answer names a question not on the card; the register or a
spec changed after the card was emitted; an `accept` has no `proposed` answer or
its member's test case is stale or not yet bound; a text answer is empty. No
flag bypasses any refusal. After a confirming answer, render the story (and its
UAT flow) then `seal`; after a correcting answer, write the answer to the
question's `home`, rewrite the parts, render, and confirm on a new card.

`doubts observe` is the tester's route. A tester fills the `Observation`
(and optionally `Observed by`, `Date`) columns of the `Doubts` sheet in the
exported workbook; `doubts observe` reads the sheet (columns found by header
text) and appends one entry per filled row to
`doubts/observations/<STORY>.yaml` (question, the text verbatim, who, when, the
workbook name and sha256), then commits it as tc-agent (no Assertion-Event
trailer: nothing is asserted). Rows with Question ID `-` or an unknown id are
reported as skipped; running it again on the same workbook appends nothing.
It refuses (exit 1, `doubts observe refused: ...`, nothing written) when
`--workbook` or `--by` is missing, the file is absent or not an xlsx, there is
no `Doubts` sheet, or the `Question ID` / `Observation` column is missing.
An observation is evidence, not an assertion, and never lifts a level. On the
next `doubts card` the latest observation of an `ask` question is its
`proposed` text, with `proposed_origin: tester-observation`, `observed_by`,
`observation_at` and the register's own `register_proposed`. `accept` on it
writes `effect: corrects`, `origin: tester-observed` and `member_basis` (never
`confirmed_parts`): the answer is then written to the question's `home`, the
parts rewritten and rendered, and a human confirms on a new card. A
text answer behaves as before, and an observation added after a card was
emitted makes `doubts answer` refuse that card. Lint L15 checks every
observations file.

## Test case edits

```
py tools/wiki.py tc edit <id> --field <field> --from <path> --by <human>   # human only
```

Rewords ONE field of ONE test case in its source spec
(`tools/sit_specs/<STORY>.yaml` or `tools/uat_specs/<FLOW>.yaml`), never in the
rendered `testcases/` file. Fields: `title`, `objective`, `steps`, `expected`,
`priority`; SIT also `data`, `post`, `pre_extra` (empty text removes one of
those three). `--from` must name an existing UTF-8 text file holding the new
text; a missing or non-UTF-8 file is refused. A file under `build/edits/`
(where the operator app puts it) is deleted as soon as it has been read, so
also when a later check refuses; a file anywhere else is never deleted.

The command finds the entry by the test case's `scenario_id`, rewrites only
that key (every other byte of the spec is kept), runs the forced render,
`index` and `seal`, appends one line to `log.md`, and commits once as
`tc edit(<id>): <field> by <human>`; the log line is part of that same commit.
The forced render leaves a test case file alone when its text did not change
(it would differ only in the wiki commit it was rendered at), so an edit
changes one test case file and one sealed hash, and a compiled workbook marks
that one row as changed. `--no-commit` is honoured as on every mutating
command: the rendered edit stays in the tree, uncommitted.
`--allow-lint-errors` is refused: an edit is one commit of a wiki that passes
lint, or nothing. `--by` must be one line of text and not a flag.
Unchanged text is a no-op (nothing is written or committed), but only after
every check below has passed: a dirty tree, drift or a stale test case still
refuses.

It refuses - and leaves the tree exactly as it was - on:

- the text: empty text on any field except SIT `data`, `post` and `pre_extra`;
  a multi-line `title`, `priority` or `pre_extra`; a `priority` other than
  `P1`, `P2` or `P3`; more than 20000 characters; NUL in the text.
- the target: a field outside the set, an unknown id, a test case that is
  neither SIT nor UAT, a test case that no spec entry renders (for example
  because its spec does not parse; the refusal names the files that do not
  parse), a retired test case or a voided AC, a test case of the story or flow
  that was never rendered, a stale test case anywhere in the story or flow
  (regenerate first).
- the tree: a test case file that differs from its sealed hash, ANYWHERE in
  the repo and not only in the edited story (`seal` re-hashes every test case,
  so the edit would otherwise seal someone else's hand edit), and a dirty
  working tree. If you have just rendered (for example after
  `wiki doubts answer`), the render is not sealed yet: run `seal`. If a file
  was edited by hand, run `release` or `revert`.
- the rewrite: an edit that would delete a YAML comment on the key (move the
  comment first), and any refusal from the renderer, `seal` or lint.

On any failure, or an interrupt, every file the command wrote is put back and
nothing is committed; the roll-back is checked against `git status`, and
anything it could not put back is listed instead of "Nothing was changed". If
the commit landed and a later step failed, the output says the edit is
committed and nothing is undone.
It never changes a confidence level or a remark in the spec: only
`wiki doubts answer` raises one. A confirmation is of the exact text, so
rewording a part a human had confirmed returns that part to its authored level
and remark on the render, and its doubt is open again until it is confirmed
again; the other confirmed parts of the test case stay High. The command says
so: its output, the `log.md` line and the commit message carry
`confirmation <R-id> of <tc> <part> no longer applies (text changed)`.
Two more effects on doubts to know before saving:

- An edit changes a spec, so a doubts card that was emitted before it and is
  not yet applied is refused by `doubts answer` (the card no longer matches);
  the human discards it and a new card is emitted.
- If a confirmed answer has not been rendered yet, the edit's forced render
  renders it, in the edit's commit. The output, the log line and the commit
  message then also say `also rendered N confirmed lift(s): <R-ids>`.

The operator app's review panel saves through this command (action `tc_edit`).

## Suites and export

```
py tools/wiki.py export --story <id> [--name <n>] --draft   # DRAFT r0 workbook + snapshot, right after seal; refuses a graded set
py tools/wiki.py export --story <id> [--name <n>]           # final: refuses without a current strict score; fills Change Log
py tools/wiki.py export --flow <stem> [--name <n>] [--draft]
py tools/wiki.py suite compile <name>              # from suites/<name>.yaml
```

A suite can filter by PRD with `include_prds` / `exclude_prds` (lists of PRD
ids): `include_prds` keeps test cases that draw on at least one listed PRD,
`exclude_prds` drops those that draw on any. A test case draws on the PRDs in
its `generated_from.prd_versions` (`{<id>: <version>}`, shown on its
Traceability line as `PRD <id> v<N>, ... · wiki <sha>`, or `no PRD`); one with
none draws on no PRD. `suite compile` refuses an unknown id and lists the
registered ones. The workbook's Proj Doc References sheet lists one row per PRD
drawn on (title and adopted version), or one row naming the project when none.
A PRD with nothing adopted reads `no adopted version` and an id the registry
does not hold reads `<id> (unregistered)`, here and on the Traceability line.

Workbooks land in `build/inventory/<kind>/` as a timestamped file plus a
stable `-latest` copy. Each workbook has a sidecar beside it under the same
name with a `.json` suffix (`<name>_<ts>.json` and `<name>-latest.json`): when
it was compiled, the wiki commit, what compiled it (the suite name, or the
export name and story; a flow export records the flow, and a draft export
records `draft: true` and no story), `tcs_order: "sheet"`, and the sealed hash of every test
case in it (`tcs`, `{<ref>: <hash>}`; the value is `null` for a test case the
manifest had not sealed), listed in the order the workbook holds them (sheet by
sheet, row by row). Only these two commands write the sidecar; never edit it.

The operator app's Workbook view (`#/workbook/<kind>/<file>`) draws the
workbook from the file and compares those hashes with the manifest to mark the
rows that changed since the compile. It shows the sheets as tabs, a version
picker (every compile of the name) with Download, and a stale banner. Recompile
on the banner reuses `suite compile` for a suite source, or `export` for an
export that recorded a story (that is the final export, so it refuses without a
current strict score and the banner shows the refusal); any other source, a
draft export included, offers Download only. A click, or
Enter or Space, on a test case row opens the review panel; **Open** links on the
Suites page and the inventory list, and the review panel's **Open in workbook**
link (opened from the Test Cases grid; a test case in no workbook reads "Not in
a compiled workbook" instead), lead to the view. An editor with unsaved text
asks before a click, a filter, a tab or a page change would discard it. Notes
on how rows are linked:

- A row whose `TC-` id is shared by more than one test case in the workbook (a
  SIT and a UAT twin display the same id) is linked only when the sidecar has
  `tcs_order: "sheet"` and the counts match. A workbook compiled before that
  field existed leaves such rows unlinked until it is recompiled; rows with a
  unique id still link.
- A sidecar that is not what `write_sidecar` writes (missing or wrongly typed
  fields), or no sidecar at all, reads as freshness unknown: the banner says
  `freshness unknown — recompile to track changes`. With no sidecar the app
  infers the source from the file name: a name that matches
  `suites/<name>.yaml` is a suite; a name of the form `<STORY>-sit`, `-uat` or
  `-osat` (the shape `wiki export` defaults to) whose `stories/<STORY>.md`
  exists is an export of that story;
  any other name has no source, so the banner has no Recompile button. For
  unknown freshness press Recompile if the banner offers it; otherwise rerun
  `py tools/wiki.py suite compile <name>` or
  `py tools/wiki.py export --story <id> --name <name>`, which writes the
  sidecar.
- A `kind` outside `sit`, `uat`, `osat`, `mixed` is not found (HTTP 404); an
  unreadable workbook is HTTP 422 naming the file (without its directory). The
  listing skips Excel `~$` lock files. A file it cannot read is named in the
  listing's `skipped` list (kind, file, error) and shown on the page; when it
  is a `-latest` file, the listing falls back to that name's newest timestamped
  compile.

## Lifecycle (all human)

```
py tools/wiki.py retire <tc-id> --by <you> --reason superseded --superseded-by <tc-id>
py tools/wiki.py void-ac /stories/<id>.md#<AC> --by <you> --caused-by <src> --cause-version <n>
py tools/wiki.py unretire <tc-id> --by <you>
py tools/wiki.py release <tc-id> --by <you>        # keep a hand-edit (W4)
py tools/wiki.py revert <tc-id>                    # discard a hand-edit
```

## Migrations

```
py tools/wiki.py migrate-ids                       # the only sanctioned tc_format change
py tools/wiki.py migrate-provenance [--apply]      # backfill provenance (lint L13)
py tools/wiki.py migrate-prds [--id <id> --title "<title>"]   # once, at your instruction; you choose the id and title
```

`migrate-prds` is a one-time, one-way conversion. It asserts nothing, but it
rewrites every test case, re-seals and fixes a permanent PRD id and title, so
the agent proposes it, asks you for the id and title (never inferred from a
file name) and runs it only at your explicit instruction. Its refusals are
fixed upstream, never bypassed.

On a schema-1 project every command except `migrate-prds`, `status` and `lint`
refuses and names `migrate-prds`; so do `render_sit.py` and `render_uat.py`.
`status` says the manifest is schema 1 and `lint` warns W10. `tc edit` makes the
refusal itself, after it has consumed its text file and before it writes
anything. `app` still opens, because its views only read, and shows a migration
notice on every page; every action it runs is refused the same way.
`eval_rubric.py --apply-patch` refuses too (scoring, which writes only under
`build/rubric/`, does not). A
project with no `manifest.json` yet is schema 2 from its first command and is
never refused.

It converts a project written before the PRD registry (manifest
`schema_version` 1, one unnamed PRD) to schema 2 in one commit. A project that
never ingested a PRD takes no arguments; a project with an ingested PRD needs
`--id` and `--title` and refuses without them. It moves the flat PRD layout one
level down under the id (`inputs/prd/vN/`, `sources/prd/`, `staging/`,
`changereports/`), rewrites every reference to the moved sections (including
story `source_pins` keys, `review_because` causes, a voided AC's
`voided.caused_by` and a retired test case's `retirement.caused_by`), sets each
test case's `generated_from.prd_versions` and Traceability line (edited in
place, not re-rendered), writes the registry, and re-seals. Change reports
that were already acted on gain `prd:` and have their references to moved
sections updated; they are not reworded. A file that is not in the form the
tools write (quotes, comments, a flow-style list) is not re-serialised: each
reference is substituted where it stands and every other byte is kept. A
fragment pin moves with a fragment whose reference was rewritten, so no test
case goes stale because of the migration; a pin that was already out of date
stays so.

Before writing anything it refuses on: `--no-commit` or `--allow-lint-errors`
(neither is accepted), `--id` on a project with no PRD, an id that does not
match the PRD id pattern, has the form `v<digits>` or is `index` or `log`, a
missing `--title`, an `--id` that collides with an existing path, an unsealed
test case, a dirty working tree, lint errors, a directory that is not a git
repository with a commit, unreadable PRD files, a section whose id does not
match its file name, and a reference to a moved section that cannot be
rewritten where it stands (folded over several lines or written with escapes;
it names the files). It also refuses, after the writes and with every file put
back, when lint L10 would read the commit as a new assertion, and says which
case it is: git cannot pair a moved change report with its old path (a human
shortens that report's list of references, commits, and re-runs), or a
reference shares a line with `asserted_by:` or an asserted `status:` (a human
moves it to its own line).

An unsealed test case, lint errors and a reference that cannot be rewritten in
place are repaired with commands (`seal`, `release`, `revert`, an assertion)
that all refuse on schema 1. Resolve them on the platform revision the project
last ran on (the last one before the PRD registry), commit, then upgrade and
re-run `migrate-prds`. The refusals say so.

Any failure after the first write restores every file and leaves HEAD where it
was, with three reported exceptions: when git cannot report HEAD, nothing is
rolled back and the output says it is unknown whether the commit landed; when
the commit landed and a later step failed, the migration is committed and the
output says so; and when the roll-back cannot be verified clean, the leftover
files are listed. It is idempotent: on a migrated project it says so and
changes nothing. It prints notes for what to check by hand: prose that still
names a flat `sources/prd/<slug>` or `prd#<slug>` (this note covers concept
files only: stories, flows, glossary, modules, resolutions, sources, test
cases and change reports; it does not read `suites/`, the spec files under
`tools/`, `log.md` or `docs/`), test cases whose story cites
no PRD so their versions were dropped, test cases to re-render, how many
fragment pins moved, and untracked
files left in place. Every rewritten test case's hash changes, so compiled
workbooks read as changed until you recompile the suites.

## Where things live

| Path | Contents |
|---|---|
| `sources/prd/<prd-id>/`, `sources/figma/` | Verbatim ingested sections (one directory per PRD) and pages |
| `stories/`, `flows/`, `glossary/`, `resolutions/` | The asserted wiki |
| `tools/sit_specs/<id>.yaml` | SIT test-case content, data only |
| `testcases/sit/`, `testcases/uat/` | Rendered test cases (never hand-edited) |
| `suites/*.yaml` | Suite definitions |
| `doubts/<id>.yaml` | Doubt registers: root questions per story (lint L15) |
| `manifest.json` | Hashes, bindings, counters (never hand-edited) |
| `build/` | Git-ignored compiled views: cards, rtm, rubric, inventories |
