# tc-style

The writing-style contract for every rendered test case and every exported
workbook. A rules reference, loaded by the generate skills; it decides
nothing on its own.

## When it applies

- Authoring or re-wording test-case content in `tools/sit_specs/<id>.yaml`
  (`title`, `objective`, `steps`, `expected`, `data`, `pre_extra`) or a UAT
  spec (`tools/uat_specs/<FLOW-ID>.yaml`).
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

The agent rewords in the spec and re-renders under its own commit.
`wiki tc edit` is your own edit (the Save button of the app's Test Cases
page). The agent runs it from the command line only when you dictate the exact
text and tell it to save that text under your name, and never for wording it
composed.

## Not this skill

Which test cases exist (`tc-generate-sit` / `tc-generate-uat`), whether one
should exist (`tc-lifecycle`), the workbook's sheet layout and header block
(`run-tc-copilot`, `references/xlsx-format.md`).

## Runs, sections and Continue from (R6)

Test cases are run top-down as a flow. Every test case belongs to a `run` (one
complete flow with one data profile) and a `section` (one screen or stage). The
export gives each run its own worksheet, prints a `Section:` row per section
inside it, and every test case leads its steps with where it starts:
`Continue from TC-<id>: <end state>`, the same with `(fresh run replayed to
this point)` for a fork, or `Start of run:`. Inside a section the refusals
come first, then the test case that completes the step. A fork, where one
cannot be avoided, comes last.

**Flows are sheets.** A run is one flow with one data profile, and it is its
own worksheet. Every sheet starts from the beginning and a test case never
continues from another sheet. The main profile's refusals, read-only checks,
base cases and state observations all go on the main flow sheet. A valid
variant that completes a step the main flow already completed does not fork:
it goes on a variant flow sheet that walks the flow again with its own
profile, using the variant at each step it has one. Single-case runs share one
`Standalone checks` sheet. A state-transition check does not repeat the
action: it continues from the test case that performed it and observes the
resulting state; an observation that does not visit the AC's form sets
`element_block: false`. A fork (`fresh_run: true`) is the last
resort, for a test case that needs a state its flow has already moved past.

Two practical points. A sheet that opens later in the journey than login, and
a standalone check, still begin with `continue_from: start`; they carry one
`pre_extra` line saying which persona or data to use and which steps to
complete first, and a mid-sheet end-to-end case that starts again from login
says to use a fresh data set. And a test case that needs a page its sheet's
previous test case already saved is not a linear continuation: it is a
standalone check or a fork.

### What `render_sit.py` refuses

All of these abort the render with the offending entry index; fix the spec,
never the tool:

- ``run '<name>' must begin with `continue_from: start` - each sheet is one
  flow and starts from the beginning``
- ``continue_from <ac>/<seq> is in run '<name>' - a flow never continues from
  another sheet; use start and walk this flow from the beginning``
- `run '<name>' is not contiguous - its test cases must sit together, in run
  order`, and the same for `section '<name>' is not contiguous`
- ``a `start` test case must begin at the spec's entry_state '<state>', not
  '<state>'``
- `continue_from <ac>/<seq> ends at '<state>' but this test case starts at
  '<state>'`
- ``<ac>/<seq> is already continued by <ac>/<seq> - a second test case from
  the same state needs `fresh_run: true` ``
- ``profile '<a>' differs from <ac>/<seq>'s '<b>' - a different data set needs
  `fresh_run: true` or `continue_from: start` ``

The export writes the sheets in the order the runs first appear in the spec.

## AI confidence and remarks (R7)

Two columns follow Expected Results. `Confidence` is the test case's
overall level. `Remarks` breaks it down, one line per reviewed column:

```
Scenario: High - Source: AC3; PRD section 2.4.
Test Steps: High - Source: AC3 and the component table.
Field / Values: Medium - Inferred: the quantity is given as 10. Verify: stock of that item is at least 10.
Expected Results: Low - Inferred: the order is refused on Save. Verify: whether the field blocks it or Save rejects it.
```

**High** means stated or shown by the source, **Medium** means a detail is
assumed, **Low** means the thing itself is inferred. The overall level is the
lowest of the four. Review the Low rows first, then the Medium ones; within a
row, the remark tells you which column to check. The same breakdown is in
each markdown test case under `# Confidence`.
