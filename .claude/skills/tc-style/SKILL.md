---
name: tc-style
description: TC WRITING-STYLE contract for every rendered SIT/UAT test case and org workbook export - Field / Values column content, short imperative action wording, hyphens not em dashes, bold markers, shared preconditions. Load alongside tc-generate-sit/tc-generate-uat whenever authoring or rewording TC content, or reviewing exported workbook wording. A rules reference, not a workflow: it never decides which test cases exist, renders, seals, or exports anything.
---

# tc-style - TC writing-style contract

Human-stated feedback (syabz, 2026-07-23). Applies to every TC body a render
run-record writes and to every org workbook export. Enforced in two layers:
authoring rules here, plus export-time normalization in
`tools/wiki_suite.py` (`_richify`: `**bold**` markers -> real Excel bold,
em/en dashes -> hyphens).

## R1 - Field / Values column = concrete tester inputs

The workbook's Field / Values column (fed from the TC's `# Test Data`
section, plus per-TC precondition extras) shows WHAT THE TESTER ENTERS or
what data the run needs - dates, form values, filter selections. Author
`# Test Data` as one `**Field** = value` line per input:

```
**Site** = Site X
**Due Date (Order A)** = current system date - 1 day
**Request Date** = 13-Jul-26
```

Never prose paragraphs. Environment caveats compress to one short trailing
line (`Values are environment-specific - verify against the role's data
access.`). No inputs at all -> `-` (export leaves the column to the
precondition extras).

## R2 - Short wording: clear action items

Testers skim. Steps are imperative one-liners: verb first, one action per
step, aim <= 12 words, no rationale, no PRD citations inside the step text.
Expected results are short declaratives - what is seen, not why. Move
justification (rule ids, PRD sections) to Traceability; it is already there.

Bad:  `Compare the listed options against the Reference Data - Organisation
Structure entries permitted for the role.`
Good: `Check listed options against the role's permitted **Unit** entries.`

## R3 - Hyphens, never em/en dashes

Use `-` in all authored TC text. Verbatim strings from asserted sources
(component names like `MO Details – Open MO`, AC text) stay untouched in the
wiki - the export normalizes every dash to `-` so the workbook complies.

## R4 - Bold key items with `**...**`

Bold UI element names, field names, input values, statuses, and TC ids in
authored text: `Click the **'Unit'** dropdown`, `**Fulfilment Status** shows
**Fulfilled** (green)`. The export converts markers to real bold runs in
xlsx cells; the `.md` inventories render them as markdown bold. The lettered
element-verification block bolds element names automatically
(`wiki_coverage.element_verification_block`) - never hand-write it.

## R5 - Preconditions: one shared block, terse label-free extras

(syabz feedback 2026-07-23: "Field / Values should not have the
pre-condition for too many things... do not use pre-condition, just add it
in the content with least wording.")

Author every TC on a sheet with the SAME shared precondition lines
(a `PRE_COMMON` constant, verbatim) so the export's common-line detection
lifts them once into the sheet's blue `<Pre-condition>` block. Word the
navigation line `Unless the steps start from login, user is on ...` so it
stays true for login TCs too. Per-TC precondition lines are for
data-critical setup ONLY (e.g. `1+ open order satisfies **Overdue Due Date**.`) -
the export appends them to Field / Values as bare lines: no
`Pre-condition:` label, no numbering. Never repeat in a precondition what
the TC's `# Test Data` lines already state, and drop per-TC environment
notes - the shared block's `values are environment-specific` covers it.

## Where the rules bite

- Authoring: the SIT content specs (`tools/sit_specs/<STORY>.yaml` — the
  `title`, `objective`, `steps`, `expected`, `data`, `pre_extra` fields) and
  the UAT run-record (`tools/render_production_monitoring_uat.py`). Reworded
  content = re-render `--force`, then `seal`.
- R5 is partly structural now: a spec supplies `pre_common` once for the whole
  scope and at most one unnumbered `pre_extra` line per TC, which
  `render_sit.py` numbers for you. A numbered or multi-line `pre_extra` is a
  validation error, not a style nit.
- Export: `tools/wiki_suite.py::_richify` is the safety net for R3/R4; it
  never fixes R1/R2 - those are authoring discipline.
- Regression: `py tools/smoke.py` re-renders and compiles; a golden-eval or
  byte-stability failure after a style edit means you forgot `--force` +
  `seal`.

## Not this skill

This is a rules reference loaded *by* the generation skills. It decides nothing
on its own:

- Which test cases exist, and rendering them → `tc-generate-sit` /
  `tc-generate-uat`.
- Whether a TC should exist at all → `tc-lifecycle`.
- The workbook's sheet layout, formulas, and header block (as opposed to the
  wording inside cells) → `run-tc-copilot`, `references/xlsx-format.md`.
