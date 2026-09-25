# tc-style

The writing-style contract for every rendered test case and every exported
workbook. A rules reference, loaded by the generate skills; it decides
nothing on its own.

## When it applies

- Authoring or re-wording test-case content in `tools/sit_specs/<id>.yaml`
  (`title`, `objective`, `steps`, `expected`, `data`, `pre_extra`) or a UAT
  run-record.
- Reviewing exported workbook wording.

## The five rules

**R1 Field / Values holds concrete tester inputs.** The workbook column is fed
from `# Test Data`. Author it as one `**Field** = value` line per input:

```
**Site** = Site X
**Due Date (Order A)** = current system date - 1 day
```

Never prose paragraphs. No inputs at all is `-`. Environment caveats compress
to one trailing line.

**R2 Short wording.** Steps are imperative one-liners, verb first, one action
each, about 12 words, no rationale, no PRD citations. Expected results are
short declaratives: what is seen, not why. Justification lives in
Traceability.

**R3 Hyphens, never em or en dashes.** Verbatim strings from asserted sources
stay untouched in the wiki; the export normalises every dash.

**R4 Bold key items.** UI element names, field names, input values, statuses
and test-case ids: `Click the **'Unit'** dropdown`. The export converts
markers to real bold runs. The lettered element-verification block bolds
element names itself; never hand-write it.

**R5 One shared precondition block, terse extras.** Every test case on a
sheet shares the same `pre_common` lines so the export lifts them once into
the sheet's precondition block. Per-test-case `pre_extra` is one unnumbered
line for data-critical setup only; the renderer numbers it. Never repeat in
a precondition what `# Test Data` already states.

## Where it is enforced

- Structurally: a numbered or multi-line `pre_extra` is a spec validation
  error.
- At export: `tools/wiki_suite.py` converts bold markers and dashes (R3, R4).
  It never fixes R1 or R2; those are authoring discipline.
- The rubric's lens A and lens B read the same fields and band determinacy
  and completeness, so style failures cost score.

## After a wording change

Re-render the scope with `--force`, then `seal`. A golden-eval or
byte-stability failure after a style edit means one of those was skipped.

## Not this skill

Which test cases exist (`tc-generate-sit` / `tc-generate-uat`), whether one
should exist (`tc-lifecycle`), the workbook's sheet layout and header block
(`run-tc-copilot`, `references/xlsx-format.md`).
