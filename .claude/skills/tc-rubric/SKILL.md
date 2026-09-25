---
name: tc-rubric
description: The ISO/IEC/IEEE 29119-4 GRADE LOOP for generated test cases - test model (TD1/TD2) on the coverage card, coverage_items on every test case, then one fixed improve round - evaluate with four judge lenses, gap report, improver patch, re-evaluate, report the delta. Load ALONGSIDE tc-generate-sit / tc-generate-uat at their step 2 (test model) and step 3.5 (grade loop), or when asked to grade, score, judge, or improve a story's or flow's test cases against the rubric. Keywords: rubric, 29119-4, test model, coverage items, C = N/T, judge lens, gap report, improve round, score, PARTIAL. A rules reference plus one loop protocol - it never decides which test cases exist (that is the generate skill), never scores an EXISTING set without generating (that is tc-evaluate), and never edits a rendered testcases/ file.
---

# tc-rubric - 29119-4 test model + grade loop

Every test case this platform generates is graded against a versioned rubric
derived from **ISO/IEC/IEEE 29119-4:2021** (Software testing - Part 4: Test
techniques). The rubric is `standards/rubric/tc-rubric-v1.yaml`; the operator guide is
`docs/skills/tc-rubric.md`. The engine
`tools/eval_rubric.py` is LLM-free: it scores the mechanical dimensions itself
and MERGES judge verdicts you write as JSON. Same inputs + same verdicts =
same score, which is what makes the gate legitimate.

**Violating the letter of this protocol is violating its spirit.** Scoring a
story whose test model the human never confirmed, writing a verdict without
reading the pack, or "improving" a rendered test-case file by hand is a
violation no matter how it is justified.

## The three artifacts (spec 5, 5.2)

1. **Test model** - frontmatter `test_model:` on the story (or flow). One item
   per 29119-4 *test coverage item*: an EP partition, a BVA boundary, a DT
   rule, an ST transition, a PW pair, a UC scenario. `status: proposed` is the
   agent's guess; `status: confirmed` is the human's answer. It folds into the
   existing coverage card - **no second gate**.
2. **`coverage_items:`** on every spec entry in `tools/sit_specs/<STORY>.yaml`
   - the ids of the model items that test case exercises. This is the link
   that makes T1.1 and all of Tier 2 computable. A test case that names none
   scores T1.1 = 0.
3. **Verdicts** - `build/rubric/judgments/<scope>-r<N>-<lens>.json`, one per
   judge lens per round, written by a subagent that read its pack.
4. **Draft snapshot and changes** - `build/rubric/<scope>-draft.json`
   (written by `wiki export --draft`) and `<scope>-changes.json/.md`
   (written by `eval_rubric --diff`), the change log the final workbook
   carries.

## Step 2 (in the generate skill): the test model on the coverage card

a. `py tools/wiki.py testmodel --story <id> --propose` - a deterministic
   scaffold: one UC scenario per active AC, one DT rule per business rule, and
   BVA / EP / ST items where an AC's text states a bound, an enumerated set,
   or a state change. **Expect it to be incomplete and sometimes wrong** -
   that is what the card is for.
b. Enrich it (read_concept / write_concept, never str.replace), still
   `status: proposed`:
   - **EP**: for every input or displayed field with a value domain, name the
     valid partitions AND the invalid ones (one item each).
   - **BVA**: for every ordered domain, name each boundary (min, min-1,
     max, max+1 where a max exists). "1 or greater" is two items: 1 and 0.
   - **DT**: for every rule with two or more conditions, one item per rule
     row of the decision table (each combination that yields a distinct
     action).
   - **ST**: one item per transition (state + event -> new state), including
     the guard that must NOT transition.
   - **UC**: main scenario plus each alternative / exception scenario the AC
     text implies.
   - Mark an item the environment cannot exercise `feasible: false` with a
     non-empty `justification` (29119-4 6.1 requires the reason recorded).
   - Every `basis` id must be a real AC / rule id of this story (lint L14).
c. Put the model in the coverage card under `"test_model": {"items": [...]}`
   with the SAME item ids as the story file. Present the card. On confirm,
   `py tools/wiki.py assert story <id> --by <user> --card <card>` flips the
   model to `confirmed` (refuses if the card and the file differ).
d. Then author `coverage_items:` on every spec entry as you write the spec
   (on an ALREADY-rendered story, re-render with `--force` afterwards, or the
   items never reach the test-case frontmatter and every C reads 0/T).
   Aim: every feasible item covered by at least one test case, every test
   case naming at least one item. `py tools/wiki.py testmodel --story <id>`
   shows which items are still uncovered.

For a **flow** (UAT) the model is a scenario model (5.2.9): `SC-MAIN` with
`role: main` over the journey, plus one `role: alternative` item per abnormal,
exception or error path. A model with the main scenario only is
**INCOMPLETE** and T2.1 is capped at band 2 - propose the alternatives in
tc-align on the flow, not here.

## Step 3.5 (in the generate skill): the grade loop - ONE round, fixed

```
a. evaluate     py tools/eval_rubric.py --story <id> --round 1 --pack
                -> build/rubric/<id>-r1-score.json (PARTIAL: no judges yet)
                -> build/rubric/<id>-r1-gaps.md
                -> build/rubric/packs/<id>-r1-{A,B,C,D}.md
b. judge        dispatch 4 subagents IN PARALLEL, one per lens (below).
                Each reads its pack and writes its judgment JSON. Then
                py tools/eval_rubric.py --story <id> --round 1
                -> the round-1 score with every dimension assessed.
c. improve      dispatch the improver subagent (below) on
                build/rubric/<id>-r1-gaps.md. It returns
                build/rubric/<id>-r1-patch.json. You apply it:
                py tools/eval_rubric.py --story <id> --apply-patch build/rubric/<id>-r1-patch.json
                py tools/render_sit.py --story <id> --force && py tools/wiki.py seal
                (--force is required: a spec edit does not move the pinned
                AC fragments, so an unforced render reports "untouched" and
                writes nothing - the same is true right after adding
                coverage_items to an already-rendered story)
d. re-evaluate  py tools/eval_rubric.py --story <id> --round 2 --pack
                4 judges again (round 2 packs), then
                py tools/eval_rubric.py --story <id> --round 2
                -> prints the round 1 -> round 2 delta.
                Round 2 packs are SMALLER: the engine copies round 1's A/B/C
                verdicts for every test case whose sealed hash is unchanged
                into judgments/<id>-r2-<L>.carried.json and lists only the
                touched cases in the pack. Lens D always reads the whole set.
                A pack that says "Nothing to judge for this lens this round"
                needs no subagent. A fresh verdict for a carried case is
                allowed and wins. The merge refuses if the sealed set
                changed since these packs were written: re-pack, re-judge.
e. STOP.        Report both scores and the delta. If round 2 is LOWER,
                the improvement was wrong: `git checkout -- tools/sit_specs/<id>.yaml`,
                re-render, re-seal, and say so prominently. Never ship the
                worse set because it came second (spec 7.3).
                The gate is `--round <current> --strict`, where current
                is round 2 unless round 2 regressed and round 1 was
                restored, in which case round 1. `wiki next` names the
                round.
```

Exactly one improvement round. No score threshold extends it. The gate is
`py tools/eval_rubric.py --story <id> --round <current> --strict` (see step
e; threshold from `config.yaml rubric.threshold`); `--strict` refuses a
PARTIAL score - if a judge file is missing, run that lens, do not reach for
`--allow-partial`. A merge (`--round N`, with or without `--strict`) refuses
when the sealed set changed since the round N packs were written: re-run
`--round N --pack` and re-judge - verdicts describe the content the judges
read.

### The four judge lenses (spec 7.1)

Judges are lenses over the whole set, never one subagent per test case.
Each subagent prompt is exactly:

> Read `build/rubric/packs/<id>-r<N>-<L>.md`. It states the dimensions you
> band, the obligation text from ISO/IEC/IEEE 29119-4, the material, the
> mechanical ceilings, and the exact JSON file to write. Band every test case
> (or the whole set, for lens D) on every listed dimension. Write ONLY that
> file, with the `rubric_hash` shown in the pack. Return the path.

| Lens | Dimensions | Reads |
|---|---|---|
| A expected-result | T1.4 determinacy, T1.5 derived from the basis | every TC + its AC / rule text |
| B input-completeness | T1.7 inputs and starting state complete | every TC + the model items it names |
| C technique-fit | T1.8 tag fits the coverage-item kind | every TC + model shape |
| D set-level | T2.5 valid/invalid balance, T2.6 quality-characteristic spread | the whole set + ACs + model |

A verdict on a dimension the lens does not own, on a mechanical dimension,
on an unknown TC, under another rubric hash, or without a rationale is
**rejected** by the engine with every error listed - fix the file, never
delete the verdict.

### The improver (spec 7.2)

One subagent. It PROPOSES; you are the sole writer. Prompt:

> Read `build/rubric/<id>-r<N>-gaps.md` and `tools/sit_specs/<id>.yaml`.
> For each gap you can close, emit one patch: `{"op":"set","ac":..,"seq":..,
> "field":..,"value":..,"closes":"G3.4"}` to change a field of an existing
> entry, or `{"op":"add","test_case":{...full entry...},"closes":"G1.2"}` to
> add a test case for an uncovered coverage item. Every new or changed
> `expected` must be traceable to the AC / rule text; every `data` value
> concrete (`**Field** = value`); wording per tc-style. Write
> `build/rubric/<id>-r<N>-patch.json` as `{"scope":"<id>","round":N,
> "patches":[...]}` and return the path. Do not edit any other file.

`--apply-patch` validates every patch against the spec's key set and writes
nothing if any patch is bad.

## Reading the score

- `score` = tier1 mean x 0.40 + tier2 x 0.60 (config `rubric.blend`).
- **PARTIAL** = at least one dimension NOT ASSESSED. A missing judge is never
  band 0 - and a ceiling of 0 (empty Expected Results, no negative case in
  the set) IS band 0 without a judge (spec 4).
- `coverage`: per technique, `C = N/T x 100` (29119-4 6.1). `T` counts the
  feasible items in the model; `N` the ones some active test case names.
- Two scores compare only under the same `rubric_hash`.

## Hard rules

- Never score a story whose `test_model.status` is not `confirmed`; the
  engine refuses, and that refusal is correct.
- Never write a verdict without reading the pack, and never edit a verdict
  to move a score.
- Never edit `testcases/**` to close a gap (W4 drift). Gaps close through
  the spec + re-render.
- Never run a third round. Never keep round 2 when it regressed.
- Never write or edit a `.carried.json`; the engine writes it from round
  N-1's verdicts and drops any entry whose test case changed since.

## Red flags - STOP

- `eval_rubric REFUSED: test_model status is 'proposed'` and you are about
  to set `confirmed` yourself -> the human did not answer the card. Stop.
- About to write `coverage_items` ids that are not in the model "to be
  fixed later" -> W7 / T1.1 band 1. Fix the model on the card first.
- `--strict REFUSED ... PARTIAL` and you reach for `--allow-partial` -> a
  judge did not run. Run it.
- The gap report lists G1 items and you are closing them by deleting the
  items from the model -> that is coverage by definition. Add test cases, or
  mark infeasible WITH a justification the human confirms.

## Not this skill

- Which test cases exist, rendering, sealing -> `tc-generate-sit` /
  `tc-generate-uat` (this skill runs inside them).
- Scoring an existing set or a foreign workbook without generating ->
  `tc-evaluate`.
- The AC or rule text is wrong -> `tc-align`.
- Wording of a test case -> `tc-style`.
