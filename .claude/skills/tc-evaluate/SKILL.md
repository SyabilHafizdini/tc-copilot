---
name: tc-evaluate
description: SCORE an existing set of test cases against the ISO/IEC/IEEE 29119-4 rubric WITHOUT generating or changing anything - a story or flow already rendered in this wiki (native mode), or, later, a foreign workbook. Dispatches the four judge lenses, merges verdicts with `tools/eval_rubric.py`, and reports the score, per-technique C = N/T coverage and the gap report. Use when asked "how good are these test cases", "grade / score / audit the SIT set for story X", or to gate a suite export on the rubric threshold. It never generates, edits, or re-words a test case - if the set is weak the remedy is tc-generate-sit / tc-generate-uat, where the improve loop (tc-rubric) lives.
---

# tc-evaluate - standalone rubric evaluation

Read-only over the wiki's content. Produces a score and a gap report;
changes nothing the human asserted and nothing that is rendered.

## Protocol (native scope)

1. **Determine the scope**: `--story <id>` or `--flow <id>`.
2. **Refuse early**: `py tools/wiki.py testmodel --story <id>` - if the
   model is ABSENT or `proposed`, stop and route to `tc-generate-sit` step 2
   (tc-rubric). There is no honest number without a confirmed model, and the
   engine refuses one (spec 12).
3. **Round 1 packs**: `py tools/eval_rubric.py --story <id> --round 1 --pack`.
   Use the highest free round number if `build/rubric/<id>-r*-score.json`
   already exist, so an earlier grade is never overwritten.
4. **Dispatch the four judge lenses in parallel** exactly as tc-rubric
   states (each reads its pack, writes its JSON, returns the path).
5. **Merge**: `py tools/eval_rubric.py --story <id> --round <N>`. Confirm the
   output has no `judges missing` line; if it does, run that lens - do not
   report a PARTIAL number as the score.
6. **Report** to the human, in this order: headline score vs threshold and
   whether it is PARTIAL; per-technique `C = N/T`; every INCOMPLETE MODEL or
   UNKNOWN COVERAGE ITEM warning; the top gaps from
   `build/rubric/<id>-r<N>-gaps.md` (G1 uncovered items first). Name the
   rubric version and hash.
7. **Gate** (only when asked): `py tools/eval_rubric.py --story <id> --round <N> --strict`.

## Foreign workbook mode

Not implemented in this plan. When a workbook path is given, say so and offer
native mode on the story it belongs to. Do not improvise a column mapping.

## Hard rules

- Never propose or confirm a test model here - that is the coverage card in
  the generate skill.
- Never apply an improver patch, re-render, or edit a spec here. Report the
  gaps; the human decides whether to run the generate skill.
- Never present a PARTIAL score without the word PARTIAL and the missing
  lenses named.

## Not this skill

- Improving the set -> `tc-generate-sit` / `tc-generate-uat` with `tc-rubric`.
- The rubric itself (dimensions, clauses, bands) -> `standards/rubric/tc-rubric-v1.yaml`
  and `tc-rubric`.
- Building a workbook from the set -> `tc-suite-author`.
