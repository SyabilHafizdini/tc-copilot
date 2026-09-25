---
name: tc-generate-sit
description: Generate or regenerate SIT test cases for a STORY — coverage map AND 29119-4 test model first (propose, correct, human-confirms the one coverage card), render from tools/sit_specs/<STORY>.yaml with coverage_items on every test case, then ONE rubric grade-and-improve round (tc-rubric). Use when asked for SIT test cases, when a story has no confirmed component coverage, or when a coverage/component GAP needs dispositioning. Keywords: SIT test cases, coverage map, component coverage gap, Component x AC matrix, GAP row. Does NOT do UAT (that is tc-generate-uat, driven by a flow journey) and does NOT filter or export existing TCs into a workbook (that is tc-suite-author).
---

# tc-generate-sit — coverage-first SIT generation

Product-agnostic protocol; all product facts come from the story's own
frontmatter (ACs, components, coverage_map) and config.yaml.
All examples below use `<STORY>` for the story id — substitute your own.

**Violating the letter of this protocol is violating its spirit.** Rendering
before the coverage card is confirmed, or asserting coverage yourself, is a
violation no matter how it is justified.

## Protocol

1. **Gate**: `py tools/wiki.py gate --story <id>`. BLOCKED → stop; the fix
   is alignment (tc-align), never a workaround.
2. **Coverage prep (mandatory, before any rendering)**:
   a. If the story has no coverage_map:
      `py tools/wiki.py coverage --story <id> --propose` (deterministic
      name-matching heuristic — expect residual errors; that is what the
      card is for).
   b. Read `build/rtm/coverage-<id>.md`. Correct the proposed map yourself
      (edit via read_concept/write_concept, never str.replace) where the
      heuristic mis-mapped — you are still proposing, not asserting.
   c. **Test model (29119-4 TD1/TD2)** — load **tc-rubric** and follow its
      "Step 2". `py tools/wiki.py testmodel --story <id> --propose`
      scaffolds `test_model: {status: proposed, items: [...]}`; enrich it
      (EP partitions incl. invalid ones, BVA boundaries on both sides, DT
      rule rows, ST transitions, UC alternatives; `feasible: false` only
      with a justification). Every `basis` must be a real AC/rule id (lint
      L14).
   d. Emit the **coverage card** `build/cards/coverage-<id>-NNN.json`:
      the map, plus per undispositioned GAP component a proposed
      disposition — (i) a drafted candidate AC (next free number after the
      PRD's own, origin agent-proposed) or (ii) out-of-scope with note —
      **plus `"test_model": {"items": [...]}`** with the same item ids as
      the story file. One card, one confirmation, covering both.
   e. **HUMAN GATE.** Present the card. On confirm: write coverage_status:
      confirmed, component_dispositions, any accepted candidate ACs; the
      confirmation is the assertion event — run
      `py tools/wiki.py assert story <id> --by <user> --card <card>` at
      that instruction (it flips `test_model.status` to confirmed and
      refuses if the card and the file disagree) and reference the card in
      the commit. On revise: loop to (b).
3. **Render top-down**: write this scope's content spec at
   `tools/sit_specs/<STORY>.yaml` — **data only, named keys**. The engine is
   `tools/render_sit.py` and is shared; never copy it. Then:

   ```
   py tools/render_sit.py --story <id>
   ```

   The spec is fully validated first — unknown/missing keys, bad
   technique/priority, duplicate `(ac, seq)`, and AC/rule ids that do not exist
   in the story all abort the run with the offending index and a suggested
   correction. **Nothing is written until it validates**, so treat a validation
   error as the answer, not as an obstacle to work around. Copy the shape from
   `tools/sit_specs/<STORY>.yaml`; `py tools/render_sit.py` with no args lists
   the available specs.

   One base TC per active AC in ascending AC order (AC01, AC02, …); technique
   extras (BVA on rule boundaries, DT on multi-condition rules, EP/ST on
   component value domains/states) immediately after their AC's base TC. IDs
   from config `ids.tc_format` (zero-padded); an existing scenario binding owns
   its ID.
   **Every entry carries `coverage_items: [...]`** — the ids from the
   confirmed test model that this test case exercises (spec tc-rubric 5.2).
   The technique tag must fit the item kind (BVA ↔ boundary, EP ↔ partition,
   DT ↔ rule, ST ↔ transition, UC ↔ scenario; ERR fits any). Aim for every
   feasible item named by at least one test case; a negative case invalidates
   exactly ONE input, marked `(invalid)` in Test Data. `render_sit.py`
   refuses an id the model does not define.
   Element names in Steps verbatim from the component table; expected
   values traceable to AC/rule text. Expected Results of every view/verify
   AC end with the element-verification block built by
   `wiki_coverage.element_verification_block` from the confirmed
   coverage_map — never hand-write element lists. All authored wording
   follows the **tc-style contract** (`.claude/skills/tc-style/SKILL.md`):
   Test Data as `**Field** = value` lines (feeds the workbook's
   Field / Values column), short imperative steps, `**bold**` on UI
   elements/values, hyphens never em/en dashes.
3a. **Draft export - the first cut.** Right after the first `py tools/wiki.py
   seal`:

   ```
   py tools/wiki.py export --story <id> --name <id>-sit --draft
   ```

   This writes the org workbook marked **DRAFT (ungraded, round 0)**, keeps a
   snapshot for the change log, and commits. **Open it for the human**
   (`start "<path>"` on Windows). The grade loop below runs while they
   review. `wiki next` names this command; do not skip to 3.5. The draft
   refuses a set that already has a round score: a graded set is not a
   first cut.
3.5 **Grade loop (tc-rubric "Step 3.5") — one round, fixed.** After the
   first seal: `py tools/eval_rubric.py --story <id> --round 1 --pack`, four
   judge subagents in parallel (one per pack), merge, improver subagent →
   `--apply-patch`, re-render **with `--force`**, re-seal, `--round 2 --pack`.
   Round 2 packs carry forward the round 1 verdicts of every test case whose
   sealed content is unchanged; a lens whose pack says *Nothing to judge for
   this lens this round* needs no subagent. Never write or edit a
   `.carried.json` yourself. Four judges, merge, report round 1 → round 2.
   If round 2 is lower, restore the round-1 spec and say so. The gate is
   `--round <current> --strict`, where current is round 2 unless round 2
   regressed and round 1 was restored, in which case round 1. `wiki next`
   names the round (`py tools/eval_rubric.py --story <id> --round <current>
   --strict`, config `rubric.threshold`). A merge (`--round N`, with or
   without `--strict`) refuses when the sealed set changed since the round N
   packs were written: re-run `--round N --pack` and re-judge - verdicts
   describe the content the judges read.
4. **Seal + verify**: `py tools/wiki.py seal`, `lint`, `rtm`,
   `coverage --story <id>`, `testmodel --story <id>`. **Definition of
   done:** the matrix's Component coverage table has no GAP rows — every
   component is covered, ACs-without-TCs, or out-of-scope — AND the gap
   report's G1 list (feasible coverage items no test case names) is empty
   or each remaining item is explained; anything else means step 2 or 3.5
   was skipped. Re-render must print `rendered 0` on an unchanged wiki.
5. **Evaluate**: `py tools/eval_golden.py` when a golden set exists for the
   scope (this repo: eval/golden/). Missing > 0 is a defect to explain or
   fix, never to ignore. Extras are fine.
6. **Diff, then final export**:
   ```
   py tools/eval_rubric.py --story <id> --diff
   py tools/wiki.py export --story <id> --name <id>-sit
   ```
   The final export refuses without a non-PARTIAL, at-threshold score on the
   currently sealed set (that is the `--strict` gate, enforced). It fills the
   workbook's **Change Log** sheet from the diff: score delta, every changed
   field and the gap it closed. **Open the workbook** and point the human at
   the Change Log. For a multi-story workbook use `suite compile`.
7. Commit as tc-agent: `generate-sit(<id>): N TCs, coverage-complete,
   rubric <round-2 score>`.

## Hard rules

- Never render before the coverage card is confirmed for this story.
- Never map/assert coverage yourself — heuristic + your corrections stay
  `proposed` until the human confirms. The same holds for the test model:
  `wiki assert --card` is the only path to `confirmed`.
- Never skip the grade loop, never run a third round, never edit a rendered
  TC to move a score (tc-rubric).
- Regeneration reads the wiki, never prior TC bodies; stale TCs regenerate
  under their existing IDs; retired scenarios are SUPPRESSED.
- Drift (W4) blocks that file; surface it (release/revert is the human's).

## Red flags — STOP

- `render_sit.py` printed **REFUSED: coverage_status is 'proposed'** and you
  are reaching for `--allow-unconfirmed-coverage` → step 2d never happened.
  That flag is not a substitute for the human's confirmation. Stop.
- `assert story` printed **--card is required** and you are about to point it
  at any card just to get past it → the card must be the one you presented and
  the human answered. Stop.
- Matrix still shows GAP rows but you are calling generation done → step 2
  was skipped. Stop.
- `eval_rubric REFUSED: test_model status is 'proposed'` and you are about
  to write `confirmed` → the human never answered the card. Stop.
- A spec entry has no `coverage_items` "because none fit" → the model is
  missing an item; take it back to the card. Stop.
- About to copy `render_sit.py` for a new story → the engine is shared; write
  `tools/sit_specs/<STORY>.yaml` instead. Stop.
- `export refused: ... no score on the currently sealed set` and you reach for
  `--draft` to ship the final → the draft is round 0 only. Re-score (or run
  the missing lens), then export. Stop.

## Not this skill

- UAT test cases from a flow journey → `tc-generate-uat`.
- Filtering/exporting TCs that already exist → `tc-suite-author`.
- The story is not `aligned` yet, or an AC is wrong → `tc-align`.
- Wording/format of TC text → `tc-style`.
- The rubric, the judge lenses, the improver, reading a score → `tc-rubric`
  (loaded alongside, not instead).
- Scoring a set that already exists without regenerating → `tc-evaluate`.
- Retiring or un-retiring a TC → `tc-lifecycle`.
- The story has **no acceptance criteria** → `tc-align`. Generation is never
  where requirements are born: do not draft ACs here, not even obvious ones.
  `py tools/wiki.py gate --story <id>` refuses an aligned story with an empty
  `acceptance_criteria`, and that refusal is correct. If the human has no PRD,
  tc-align's Phase A′ elicits the ACs from them first.
