# tc-evaluate

Scores an existing set of test cases against the 29119-4 rubric without
generating, editing or re-wording anything. It produces a score and a gap
report; the remedy for a weak set lives in the generate skills.

## When to use it

- "How good are these test cases?"
- Audit the SIT or UAT set for a story or flow already rendered in the wiki.
- Gate a suite export on the rubric threshold.

Not for improving the set (`tc-generate-sit` / `tc-generate-uat` with
`tc-rubric`), not for proposing the test model (the coverage card in the
generate skill).

## How it runs

1. Determine the scope: `--story <id>` or `--flow <id>`.
2. `py tools/wiki.py testmodel --story <id>`. If the model is absent or
   `proposed`, stop and route to the generate skill's step 2. The engine
   refuses to score without a confirmed model.
3. `py tools/eval_rubric.py --story <id> --round N --pack`, using the
   highest free round number so an earlier grade is never overwritten.
4. Dispatch the four judge lenses in parallel, exactly as `tc-rubric`
   states: each reads its pack and writes its JSON.
5. `py tools/eval_rubric.py --story <id> --round N` merges. If the output
   lists a missing judge, run that lens. A PARTIAL number is not reported as
   the score.
6. Report: headline score against the threshold; per-technique `C = N / T`;
   every INCOMPLETE MODEL or UNKNOWN COVERAGE ITEM warning; the top gaps,
   uncovered items first; rubric version and hash.
7. Only when asked: `--strict` as the gate.

## What you get

- `build/rubric/<id>-rN-score.json` and `<id>-score.json` (latest).
- `build/rubric/<id>-rN-gaps.md`.
- The judge packs and verdict files for audit.

## Foreign workbooks

Scoring an arbitrary `.xlsx` with a confirmed column mapping is designed but
not implemented. Given a workbook path, the skill says so and offers native
mode on the story it belongs to.

## Hard rules

- Never apply an improver patch, re-render or edit a spec here.
- Never present a PARTIAL score without the word PARTIAL and the missing
  lenses named.
