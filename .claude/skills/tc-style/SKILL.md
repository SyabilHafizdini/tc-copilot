---
name: tc-style
description: TC WRITING-STYLE contract for every rendered SIT/UAT test case and org workbook export - Field / Values column content, short imperative action wording, hyphens not em dashes, bold markers, shared preconditions, flow sections chained with Continue from, AI confidence level and remarks per column (Scenario, Test Steps, Field / Values, Expected Results). Load alongside tc-generate-sit/tc-generate-uat whenever authoring or rewording TC content, or reviewing exported workbook wording. A rules reference, not a workflow: it never decides which test cases exist, renders, seals, or exports anything.
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

## R6 - Test cases are a flow: runs, sections and `Continue from`

A set is run top-down, not as isolated blocks. Every test case sits in a
**run** (one complete flow with one data profile; each run is its own
worksheet) and in a **section** (one screen, step or stage of the journey; the
sheet prints one `Section: <name>` row per section). It states where it starts:

| Line | Meaning |
|---|---|
| `Continue from TC-<id>: <that test case's end state>` | Picks up exactly where the named test case ended. Inside a section the predecessor is normally the test case directly above. |
| `Continue from TC-<id> (fresh run replayed to this point): ...` | A fork: that end state is needed again after another test case already moved past it. The run is replayed up to the named test case. |
| `Start of run: ...` | No predecessor: the first test case of a sheet, or a standalone check. |

A test case's end state can be continued linearly by ONE test case; any other
test case that needs it is a fork (`fresh_run: true`). A linear chain keeps one
data profile; changing the profile is a fork or a `start`. `render_sit.py`
refuses both.

Order inside a section: the test cases that leave the screen unchanged
(refusals, validations), then the one that completes the step. A fork, where
one cannot be avoided, comes last. Steps start from the predecessor's end
state - never re-navigate what it already did. A link is checked on the
declared states (the predecessor's `ends_at` equals the successor's
`starts_at`) and the chain line prints the declared state text; Postconditions
(`post`) say the same hand-over in words, so keep the two in agreement. Author the
chain through `run` / `section` / `continue_from` / `fresh_run` (SIT spec) or
the journey (UAT); the renderer writes the line into Preconditions and the
export lifts it to the top of the Test Steps cell.

**Flows are sheets.** A run is one complete flow with one data profile, and
it is its own worksheet. Every sheet starts from the beginning (`Start of
run`) and a test case never continues from another sheet. Put every refusal,
read-only check, base case and state observation of the main profile on the
main flow sheet. A valid variant that completes a step the main flow already
completed does not fork: it goes on a variant flow sheet that walks the flow
again with its own profile, using the variant at each step it has one.
Single-case runs share one `Standalone checks` sheet. A state-transition
check does not repeat the action: it continues from the case that performed
it and observes the resulting state; an observation that does not visit the
AC's form sets `element_block: false` so it does not list controls of a page
the tester is not on. A fork
(`fresh_run: true`) is the last resort, for a case that needs a state its flow
has already moved past.

A sheet that opens later in the journey than login, and a standalone check,
still begin with `continue_from: start` and carry ONE `pre_extra` line saying
which persona or data to use and which steps to complete first. A mid-sheet
end-to-end case that starts again from login says to use a fresh data set in
that line.

A case that needs a page its sheet's previous case already saved is not a
linear continuation: it is a standalone check or a fork.

## R7 - Confidence per column: tell the tester where the AI inferred

Every test case is rated on FOUR parts - one per workbook column the tester
reviews - each with a level and a remark. The workbook shows them right after
Expected Results (`Confidence` = the lowest of the four, `Remarks` = one
line per column) and the markdown carries them in `# Confidence`.

| Part | Column | High when... | Medium when... | Low when... |
|---|---|---|---|---|
| `scenario` | Scenario | it is an AC or a rule as stated | it is a variant the source implies (a boundary, a partition, a transition, a data variant) | no AC or rule asks for it |
| `steps` | Test Steps | every element and the order are in the source | an intermediate action, navigation detail or element name is assumed | the path or control is not shown by the source |
| `data` | Field / Values | the values are shown by the source or fixed by a rule | plausible values were chosen where the source gives none | a needed value is unknown and left as a placeholder |
| `expected` | Expected Results | the outcome is stated or shown | a detail is assumed: a label, a message text, a placement, which page opens | the outcome itself is inferred |

Remark per part:

- Medium / Low (required): `Inferred: <what was assumed>. Verify: <what to
  check and correct>.` At most 200 characters. Name the concrete thing (the
  value, the message, the page, the control).
- High: the evidence, `Source: <AC / rule ids>; <cited slide or section>.`

No rubric jargon, no "ER1". Confidence describes the SOURCE, not how sure the
author feels: a value or outcome the source does not state is Medium or Low
however plausible it is. After the grade loop, reconcile `expected` with lens
A: banded 3 on T1.4 or T1.5 is at most Medium, 2 or lower is Low.

**A level is never raised by the author.** Lowering is allowed; raising is
not, not even after the human told you the answer in chat, and not after you
rewrote the part with that answer. A Medium / Low part rises to High only
through a human answer recorded on a doubts card (`tc-resolve`); the renderers
refuse a spec level above the one last rendered, with no override. A part the
human confirmed renders as:

- level `High`, remark `Source: <R-id> - human answer to <Q-id> (<by>,
  <date>).` (e.g. `Source: R-US-DEMO-001-24 - human answer to Q-US-DEMO-001-01
  (operator, 2026-10-05).`)

The renderer writes that remark; the author never does. In the spec the part
keeps its authored level and its `Inferred: ... Verify: ...` remark.

## Where the rules bite

- Authoring: the SIT content specs (`tools/sit_specs/<STORY>.yaml` — the
  `title`, `objective`, `steps`, `expected`, `data`, `pre_extra` fields) and
  the UAT specs (`tools/uat_specs/<FLOW-ID>.yaml`). Reworded
  content = re-render `--force`, then `seal`.
- R5 is partly structural now: a spec supplies `pre_common` once for the whole
  scope and at most one unnumbered `pre_extra` line per TC, which
  `render_sit.py` numbers for you. A numbered or multi-line `pre_extra` is a
  validation error, not a style nit.
- R6 and R7 are structural: `section`, `continue_from`, `run`, `starts_at`,
  `ends_at`, `profile` and `confidence` are required keys on every SIT spec
  entry (and the spec declares `states`, `entry_state` and `profiles`). The
  export writes one worksheet per `run`. `confidence` maps the four parts
  (`scenario`, `steps`, `data`, `expected`) to a level and `remarks` maps the
  same parts to text; the UAT spec (`tools/uat_specs/<FLOW-ID>.yaml`) carries
  `confidence` and `remarks` per journey entry. The renderers refuse a missing
  key or part, a `continue_from` that names no earlier test case or one in
  another run, a run that does not begin with `continue_from: start`, a run or
  section that is not contiguous, or a Medium / Low part with no remark.
- Export: `tools/wiki_suite.py::_richify` is the safety net for R3/R4; it
  never fixes R1/R2 - those are authoring discipline.
- Regression: `py tools/smoke.py` re-renders and compiles; a golden-eval or
  byte-stability failure after a style edit means you forgot `--force` +
  `seal`.
- Who rewords, and how: the agent rewords in the spec and re-renders under its
  own commit. `wiki tc edit` is the human's own edit (the app's Save). From
  the command line run it only when the human dictates the exact text and
  tells you to save it under their name; the `--from` file holds their words
  verbatim. Never use it for wording you composed.

## Not this skill

This is a rules reference loaded *by* the generation skills. It decides nothing
on its own:

- Which test cases exist, and rendering them → `tc-generate-sit` /
  `tc-generate-uat`.
- Whether a TC should exist at all → `tc-lifecycle`.
- The workbook's sheet layout, formulas, and header block (as opposed to the
  wording inside cells) → `run-tc-copilot`, `references/xlsx-format.md`.
