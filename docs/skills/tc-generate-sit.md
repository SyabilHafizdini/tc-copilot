# tc-generate-sit

Generates SIT test cases for one aligned story. Coverage first, then a data
spec, then a render, then one grade round against the 29119-4 rubric.

## When to use it

- You want SIT test cases for an aligned story.
- A story has no confirmed coverage map or test model.
- Stale test cases need regenerating after a correction or PRD change.

Not for UAT (`tc-generate-uat`), not for filtering existing test cases into
a workbook (`tc-suite-author`), not for a story that is not aligned yet
(`tc-align`).

## How it runs

### 1. Gate

`py tools/wiki.py gate --story <id>` must print `GATE OPEN`. If it is
blocked, the fix is alignment.

### 2. Coverage prep, one card, one confirmation

a. `py tools/wiki.py coverage --story <id> --propose` writes a heuristic
   component-to-AC map at `coverage_status: proposed`.
b. The agent corrects the map where the name-matching heuristic was wrong.
c. `py tools/wiki.py testmodel --story <id> --propose` scaffolds the
   29119-4 test model: one scenario per AC, plus boundaries, partitions and
   transitions detected in the AC text. The agent enriches it: valid and
   invalid partitions, boundaries on both sides, decision-table rows, state
   transitions with their guards. Infeasible items carry a justification.
d. The coverage card `build/cards/coverage-<id>-NNN.json` carries the map,
   a proposed disposition for every uncovered component, and the test model.
e. **You confirm the card.** `py tools/wiki.py assert story <id> --by <you>
   --card <card>` flips both the coverage and the model to confirmed. It
   refuses if the card and the story file disagree.

### 3. Render

The agent writes `tools/sit_specs/<id>.yaml`: data only, named keys, one
base use-case entry per AC plus technique extras (BVA on boundaries, DT on
multi-condition rules, EP and ST on domains and states). Every entry names
its `coverage_items` from the confirmed model, and its technique tag must
fit the kind of item named. Then:

```
py tools/render_sit.py --story <id>
```

The spec is validated before anything is written. Unknown keys, bad
techniques, duplicate `(ac, seq)`, unknown AC or rule ids, and coverage
items the model does not define all abort with the offending index.

Every entry also names its `section`, the entry it continues from
(`continue_from`, or `start`), its `run`, `starts_at`, `ends_at` and
`profile` (the spec declares `states`, `entry_state` and `profiles`) and a
`confidence` level with `remarks` for each of four parts: scenario, steps,
data and expected. The renderer refuses a spec without these keys.

Choose the runs first. A run is one flow with one data profile, and each run
becomes its own worksheet in the workbook. The main profile's flow is the
first run: its refusals, read-only checks, base cases and state observations.
Each valid variant goes on a variant flow run that walks the flow again from
`continue_from: start`, using the variant at each step it has one. A case
that needs no earlier state of a flow goes on the `Standalone checks` run as
a `start`. A state-transition check is an observation: it continues from the
case that performed the action and verifies the resulting state, never
repeating the action; an observation that does not visit the AC's form sets
the optional `element_block: false` so it does not list controls of a page
the tester is not on. A fork (`fresh_run: true`) is the last resort, only for
a case that needs a state its flow has already moved past; more than one in ten entries forking
means the variants and transition checks are misplaced. The rule itself is in
`tc-style` (R6).

The spec is written in run order, run by run and section by section, so each
run reads as a flow with one section row per stage. Besides the missing-key
and unknown-key refusals above, the validator refuses:

- a run that does not begin with `continue_from: start` (`each sheet is one
  flow and starts from the beginning`);
- a `continue_from` into another run (`a flow never continues from another
  sheet; use start and walk this flow from the beginning`);
- a run or section that is not contiguous;
- a `start` entry that does not begin at the `entry_state`;
- a predecessor whose `ends_at` is not this entry's `starts_at`;
- a second linear continuation of one state, or a linear link that changes
  profile (both need `fresh_run: true`, or a `start`).

Wording follows `tc-style`: `**Field** = value` test data, short imperative
steps, bold on UI elements, hyphens not dashes. Expected results of view and
verify ACs end with the element-verification block built from the coverage
map, never hand-written.

### 3a. Draft export

Right after the first seal:

```
py tools/wiki.py export --story <id> --name <id>-sit --draft
```

You receive the DRAFT round 0 workbook now and review it while the grade
loop runs.

### 3.5. Grade loop, one round, fixed

See `tc-rubric`. In short: `eval_rubric --round 1 --pack`, four judge
subagents, merge, improver patch, `--apply-patch`, `render_sit.py --force`,
seal, `--round 2`, four judges, merge, report the delta. A regression
restores round 1. `--round <current> --strict` is the export gate (round 2,
or round 1 after a restored regression; `wiki next` names it). A merge
refuses when the sealed set changed since that round's packs were written:
re-pack and re-judge.

### 4. Seal and verify

`seal`, `lint`, `rtm`, `coverage --story <id>`, `testmodel --story <id>`.
Done means: no GAP rows in the component coverage table, and the gap
report's uncovered-items list is empty or every remaining item explained.
Re-render prints `rendered 0` on an unchanged wiki.

### 5. Evaluate, export, commit

`eval_golden.py` when a golden set exists. Then diff and export:

```
py tools/eval_rubric.py --story <id> --diff
py tools/wiki.py export --story <id> --name <n>
```

The final export refuses without a current strict score and fills the
Change Log sheet from the diff. Use a suite (`suite compile <suite>`) for a
multi-story workbook. Commit as `tc-agent`: `generate-sit(<id>): N TCs,
coverage-complete, rubric <score>`.

## Refusals and why

- `render_sit.py` refuses while coverage is `proposed`. The override flag is
  not a substitute for your confirmation.
- `assert` refuses without the card you answered.
- The engine refuses to score a proposed or empty test model.

## Tips

- Regeneration reads the wiki, never prior test-case bodies. Stale test
  cases regenerate under their existing ids. Retired scenarios are
  suppressed.
- A spec-only edit does not move the pinned AC fragments, so an unforced
  render reports "untouched". Use `--force` after editing the spec.
- Hand-edit drift (lint W4) blocks that file until you `release` or `revert`
  it (`tc-lifecycle`).
