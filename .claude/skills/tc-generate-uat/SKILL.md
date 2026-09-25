---
name: tc-generate-uat
description: Generate or regenerate UAT test cases for a FLOW by walking its asserted journey — one state-chained test case per journey entry. Use when asked for UAT test cases, or to turn a flow's journey into test cases. Keywords: UAT test cases, journey walkthrough, flow, state-chained steps, one TC per step, segmented journey. Does NOT do SIT (that is tc-generate-sit, driven by a story's ACs), does NOT edit the journey (that is tc-align on the flow), and does NOT filter or export existing TCs into a workbook (that is tc-suite-author).
---

# tc-generate-uat — journey-segmented UAT generation

UAT is a walk through the product: the flow's asserted `journey:` (ordered
AC refs across its member stories) IS the test set — one TC per entry, each
starting exactly where the previous one ended. Never merge steps into one
test case; never invent steps not in the journey.
A worked flow reads `FLOW-<name>` with two or more member stories and a
journey numbered `J01..JNN`.

**Violating the letter of this protocol is violating its spirit.** One
stuffed flow test case, or a journey edited here instead of on the flow, is a
violation no matter how it is justified.

## Protocol

1. **Gate**: `py tools/wiki.py gate --flow <slug>` — the slug is the flow's
   FILE STEM (e.g. `--flow <name>-e2e`), not its id. Also refuse if the flow has no
   `journey:` — the journey is proposed and asserted during flow alignment
   (tc-align), not here. Also refuse if `test_model.status` is not
   `confirmed`: the flow's scenario model (`SC-MAIN` + `role: alternative`
   items, 29119-4 5.2.9) is proposed and asserted in tc-align with the
   journey (load **tc-rubric**, "Step 2", flow paragraph).
2. **Render the chain**: copy `tools/render_production_monitoring_uat.py` as
   this flow's run-record. Per journey entry, in order:
   - ID from config `ids.tc_format_uat` (wiki-unique `UAT-` prefix; exports
     strip it so the workbook shows the org's doc-scoped `TC-...`); an
     existing scenario binding owns its ID.
   - `covers`: the story AC ref + the flow journey ref (`#JNN`). Where a
     journey entry realises a flow branch, add the branch ref to `covers`
     too (this worked example is a linear walk — no branches).
   - Precondition = previous entry's `end_state` ("Continue from
     TC-...: user is at ..."); first entry uses the flow's
     entry_condition.
   - Expected results = the AC's Then-clause + the element-verification block
     built by `wiki_coverage.element_verification_block` from the covered AC's
     confirmed coverage_map — never hand-write element lists.
   - `coverage_items`: every journey TC names `SC-MAIN`; a TC that realises
     an alternative scenario names that `SC-ALT-nn` too. The engine caps
     T2.1 at band 2 while the model has no alternative item — that is a
     finding about the model, surface it, do not hide it.
   Polish wording per TC through the run-record script, never by hand-edit
   of generated files. Wording follows the **tc-style contract**
   (`.claude/skills/tc-style/SKILL.md`): short action steps, `**bold**`
   element names/values, hyphens never em/en dashes; Test Data stays `-`
   (the chained precondition fills the workbook's Field / Values column).
2a. **Draft export**: after the first seal,
   `py tools/wiki.py export --flow <stem> --name <stem>-uat --draft` - the
   DRAFT round 0 workbook for the human, with the snapshot the change log
   needs. Open it; the grade loop runs while they review. The draft
   refuses a set that already has a round score (a graded set is not a
   first cut).
2.5 **Grade loop (tc-rubric "Step 3.5")** — `py tools/eval_rubric.py --flow
   <id> --round 1 --pack`, four judge subagents, merge. The improver's patch
   applies to the run-record script's wording tables, never to rendered
   files; re-render with `--force`, re-seal, `--round 2`. Round 2 packs carry
   forward the round 1 verdicts of every test case whose sealed content is
   unchanged; a lens whose pack says *Nothing to judge for this lens this
   round* needs no subagent. Never write or edit a `.carried.json` yourself.
   Report the delta. The gate is `--round <current> --strict`, where
   current is round 2 unless round 2 regressed and round 1 was restored, in
   which case round 1. `wiki next` names the round (`py
   tools/eval_rubric.py --flow <stem> --round <current> --strict`). A merge
   (`--round N`, with or without `--strict`) refuses when the sealed set
   changed since the round N packs were written: re-run `--round N --pack`
   and re-judge - verdicts describe the content the judges read.
3. **Seal + verify**: `seal`, `manifest`, `lint` (L2/L12 validate every
   journey ref, L14 the test model). Re-render must print `rendered 0`
   unchanged. `py tools/eval_golden.py` → segmentation must be 1:1 (journey
   entries == active UAT TCs); report LCS vs the golden journey.
4. **Diff, then final export**: `py tools/eval_rubric.py --flow <stem> --diff`,
   then `py tools/wiki.py export --flow <stem> --name <stem>-uat` (refuses
   without a current strict score; fills the Change Log). `suite compile
   <uat-suite>` for the multi-flow workbook.
5. Commit as tc-agent: `generate-uat(<flow>): N journey TCs`.

## Hard rules

- **Member stories MUST be `coverage_status: confirmed` before rendering.**
  The coverage_map is UAT test content here — the labelled element list in each
  TC's Steps/Expected is read straight from it — so a proposed (uncorrected)
  map would bake the heuristic's mistakes into tester-facing TCs. Refuse to
  render a flow whose journey touches any story still at `proposed`.
- **After any coverage re-confirmation that touches a member story, re-render
  the UAT scope with `--force`** (e.g.
  `py tools/render_production_monitoring_uat.py --force`): coverage_map lives
  outside AC fragment pins, so plain byte-stability would preserve the old
  element lists. The renderer's COVMAP pins make `cascade` flag exactly the
  affected journey TCs stale; `--force` then re-derives them, and `seal`
  re-hashes. Never hand-patch the element lists.
- Journey edits happen on the FLOW (tc-align + human assert), never here.
- Editing/reordering journey entries stales exactly the affected TCs
  (their pinned `#JNN` fragment hashes change) — regenerate, don't patch.
- Superseding old-style flow TCs is a human retirement
  (`wiki retire ... --reason superseded`), L5-checked, never automatic.

## Red flags — STOP

- About to author one TC that spans several journey entries → that is the
  old-style stuffed flow test case. One TC per entry. Stop.
- About to edit or reorder `journey:` entries here → journey lives on the
  flow; take it back to tc-align + human assert. Stop.
- `eval_golden` prints segmentation MISMATCH but you are calling it done →
  entries and active UAT TCs are not 1:1. Stop.

## Not this skill

- SIT test cases for a story's ACs → `tc-generate-sit`.
- Proposing/asserting the journey or the scenario model's alternatives, or
  fixing a wrong walk → `tc-align`.
- The rubric, judges, improver, reading a score → `tc-rubric`.
- Filtering/exporting TCs that already exist → `tc-suite-author`.
- Wording/format of TC text → `tc-style`.
- Retiring old-style flow TCs → `tc-lifecycle`.
