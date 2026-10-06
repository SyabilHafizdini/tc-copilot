# Playbook

How a tester and the agent run this platform day to day. **The agent
proposes, you assert**; the tooling enforces it. Examples use `US-XXXX` for a
story id.

## The mental model

- The **wiki is the only source of truth**: `stories/`, `glossary/`,
  `resolutions/`, `sources/`. Test cases, the RTM, suites and the dashboard
  are compiled views of it and are never edited by hand.
- Every fact is either `agent-proposed` or human-asserted. Only assertion
  unlocks generation.
- **Nothing regenerates by itself.** Upstream changes flag staleness; you
  decide when to regenerate.
- Every mutation is a git commit by `tc-agent`. `git log` is the audit trail.

Three standing commands:

```
py tools/wiki.py next       # what should happen next, and which skill does it
py tools/wiki.py status     # raw state
py tools/smoke.py --fast    # is the platform healthy?
```

## The core loop per story

### Align (`tc-align`)

The agent reads the PRD sections and Figma page, drafts the story (summary,
ACs under the PRD's own numbers, business rules, component table, glossary
proposals), and brings you questions with proposed answers. It ends with an
alignment card. You choose:

- **Assert**: answers become Resolutions under your name; the gate opens.
- **Revise**: say what is wrong; the agent loops with the delta.
- **Discard**: the session's commits are reverted.

A story with open questions cannot be asserted. A story that is not aligned
cannot be generated from.

Three source situations, each declaring a `provenance`:

| Source | Branch | provenance |
|---|---|---|
| PRD numbers its ACs | Phase A | `prd-verbatim` |
| No PRD at all; you are interrogated | Phase A′ | `human-stated` |
| PRD describes behaviour in prose only | Phase A″ | `prd-interpreted` |

### Generate and grade (`tc-generate-sit`, `tc-generate-uat`, `tc-rubric`)

SIT is coverage-first. Before rendering, the agent proposes one coverage card
carrying two things: the component-to-AC map, and the 29119-4 test model
(every partition, boundary, rule row, transition and scenario the story
contains). You confirm the card. Then the agent:

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

The strict gate is `py tools/eval_rubric.py --story US-XXXX --round <current> --strict`,
where current is round 2 unless round 2 regressed and round 1 was restored,
in which case round 1. `wiki next` names the round.

UAT walks an asserted flow journey: one test case per journey step, each
starting where the previous ended. The flow's scenario model (main plus
alternative scenarios) is asserted in `tc-align`.

### Stitch a flow from existing test cases

In the operator app open **Plan > Flow Builder**. Drag SIT test cases onto the
canvas, connect them in the order a user walks them, fork where the journey
can go two ways, then **Save as draft flow**. The result is a draft flow; you
still confirm it on the alignment card before UAT test cases are generated
from it. Details: [cli.md](cli.md#flow-builder).

### Export (`tc-suite-author`)

```
py tools/wiki.py export --story US-XXXX --name <release>
py tools/wiki.py suite compile <name>
```

A suite is a filter, never generation. Describe it in plain language
("SIT regression without module X, P1 only"), confirm the resolved count,
recompile any time.

### Review and edit in the app

`py tools/wiki.py app` opens the operator app. The Test Cases page shows every
test case in the workbook's columns; a row opens a review panel where you can
reword one field and Save. Save runs `wiki tc edit` under your name
(`provenance.human` in `config.yaml`): the text goes into the spec, the test
case is re-rendered and sealed, and one commit records it. It never changes a
confidence level; rewording a part you had confirmed reopens its doubt, and
the panel says so before you save. The Workbook page draws a compiled
workbook from the file, marks the rows that changed since it was compiled and
offers Recompile. Both are described in [cli.md](cli.md) under "Test case
edits" and "Suites and export".

## When you spot an error (`tc-correct`)

Tell the agent the correction in plain language. It records your words
verbatim as a Resolution, finds everything affected through the manifest,
edits the wiki, runs the cascade and shows a card. Asserting the card does
not regenerate anything. Batch corrections, then regenerate once:

```
py tools/wiki.py cascade      # what is stale
```

Never hand-edit a generated test case. Lint flags it (W4) and regeneration
skips that file until you `release` or `revert` it.

## When the AI is unsure (`tc-resolve`)

Every part of a test case rated Medium or Low is a doubt, listed by:

```
py tools/wiki.py doubts list --story US-XXXX
```

`wiki next` shows open doubts as a non-blocking `also:` line, and lint warns
W8 while they are ungrouped. The agent groups doubts that one answer settles
under a root question in `doubts/US-XXXX.yaml`, then puts the questions
touching the most test cases first on a card:

```
py tools/wiki.py doubts card --story US-XXXX --top 5
```

For each question you answer `accept` (the proposed answer is right) or in
your own words. The agent records your answer only when you tell it to:

```
py tools/wiki.py card revise <card> --by <you> --answer Q-US-XXXX-01=accept
py tools/wiki.py doubts answer --card <card> --by <you>
```

An `accept` lifts those parts to High on the next render, with a remark naming
your answer. Your own words lift nothing yet: the agent writes them into the
story, rewrites the parts, renders, and brings a new card for you to confirm
the rewritten text. The agent never raises a confidence level itself, and an
answer you give in chat goes onto a card before it counts. The workbook's
`AI Doubts` sheet lists the open questions.

## When a new PRD version arrives (`tc-change-report`)

Put the file in `PUT_FILES_HERE/` and let `tc-intake` route it (it asks you
which PRD and which version), or place it under `inputs/prd/<id>/v<N+1>/`
yourself; the agent never places a PRD document. Then run
`ingest-prd --prd <id>`. Nothing
changes: that PRD's version is staged and its change report is written; other
PRDs are untouched. The agent classifies each
change editorial or material and presents conflicts with your Resolutions
first. One decision as a unit:

```
py tools/wiki.py approve-cr CR-NNN --by <you> --prd <id>
py tools/wiki.py reject-cr  CR-NNN --by <you> --prd <id>
```

The agent runs these only when you tell it to. Approval fires the cascade;
stories that cite a changed or removed section of that PRD drop to
needs-review for re-alignment or a direct re-assert. If a newer version of the
same PRD is staged before you decide, the older report can only be rejected;
`wiki next` names the report to act on. The app's Changes page lists each PRD's staged version and its pending report id, with the
`diff --prd <id>` command to read the changes; it does not show the report body.

## When requirements die or test cases are replaced (`tc-lifecycle`)

Does the coverage obligation still exist?

- **No, the requirement is dead**: `void-ac` the AC. Test cases covering only
  voided ACs retire automatically; mixed ones go stale for your call.
- **Yes, a new test case took over**: `retire ... --reason superseded
  --superseded-by <new>`. Refused if the successor covers less.

Retired test cases keep their files and ids. Regeneration never recreates one
unless you `unretire` it.

## Refusals you should expect

| The system refuses to | Because |
|---|---|
| generate from a non-aligned story or flow | unaligned facts make circular test cases |
| assert a story with open questions | deferred questions rot |
| render before coverage and the test model are confirmed | the card is the human's decision |
| score a proposed or empty test model | there is no honest denominator |
| pass `--strict` on a PARTIAL score | a judge did not run |
| retire "superseded" with a weaker successor | silent coverage loss |
| regenerate a hand-edited test case | your edit would be destroyed |
| change `tc_format` after first generation | ids are in defect reports; use `migrate-ids` |
| let the agent set `aligned` or `asserted_by` | that is your signature |
| render a confidence level raised in a spec | only your answer on a card raises a level |
| apply a doubts card after its questions or test cases changed | you answered what the card showed, not what is there now |
| run any command but `status`, `lint` and `migrate-prds` on a project written before the PRD registry | the manifest is schema 1; `migrate-prds` converts it once, at your instruction, with the PRD id and title you choose (see [cli.md](cli.md), Migrations) |

If a command refuses, the fix is upstream. Never a workaround.
