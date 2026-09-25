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

### Export (`tc-suite-author`)

```
py tools/wiki.py export --story US-XXXX --name <release>
py tools/wiki.py suite compile <name>
```

A suite is a filter, never generation. Describe it in plain language
("SIT regression without module X, P1 only"), confirm the resolved count,
recompile any time.

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

## When a new PRD version arrives (`tc-change-report`)

Drop it in `inputs/prd/v<N+1>/` and run `ingest-prd`. Nothing changes: the
version is staged and a change report is written. The agent classifies each
change editorial or material and presents conflicts with your Resolutions
first. One decision as a unit:

```
py tools/wiki.py approve-cr CR-NNN --by <you>
py tools/wiki.py reject-cr  CR-NNN --by <you>
```

Approval fires the cascade; affected stories drop to needs-review for
re-alignment or a direct re-assert.

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

If a command refuses, the fix is upstream. Never a workaround.
