# tc-resolve

Turns the AI's doubts about its own test cases into a short list of questions
you answer once, on a card. Every part of a test case the AI rated Medium or
Low (tc-style R7) is a doubt; the agent groups doubts that one answer would
settle under a root question, asks you the questions that touch the most test
cases first, records your answer only when you tell it to, and the renderer
lifts the parts you confirmed to High.

## When to use it

- `wiki next` prints an `also:` line with open doubts, a doubts-card banner,
  or `confirmed doubt(s) not rendered`.
- Lint warns W8 (ungrouped doubts) or W9 (a confirmed doubt not rendered), or
  errors L15 (an invalid register, an orphan answer, a forged lift).
- You ask "why is this Low", "why is this Medium", "resolve doubts", "answer
  the AI's questions", "raise the confidence" or "mark it High", or you tell
  the agent in chat the answer to something an open doubt asks.

Not for a correction you volunteer that no open doubt asks about
(`tc-correct`), not for re-wording or regenerating test cases outside an
answered question (`tc-generate-sit`, `tc-generate-uat`), not for a wrong AC
while the story is still being aligned (`tc-align`).

## What a doubt is

One Medium / Low part of one test case, derived by the tooling from the specs.
Its id is `<scenario_id>#<part>`, the part being `scenario`, `steps`, `data`
or `expected` (the Scenario, Test Steps, Field / Values and Expected Results
columns). Nobody writes doubts, and editing a file never closes one. Each
doubt carries a basis hash of the part's current text, so an answer confirms
exactly that text: rewriting a confirmed part reopens its doubt.

| State | Meaning |
|---|---|
| open | no answer covers it |
| answered | you corrected it; the agent has not rewritten the part yet |
| rewritten | the part was rewritten after your correction; waiting for you to confirm it |
| closed | you accepted this exact text; it renders High |

## How it runs

1. **List.** The agent reads the doubts and their remarks:

   ```
   $ py tools/wiki.py doubts list --story US-DEMO-001
   US-DEMO-001: 12 open doubts in 0 questions (12 ungrouped)
   Ungrouped
       SC-DEMO-HS-01-01#data  Low  1.1-AC01-01  Inferred: the requester profile is given only as 'scenario 1'. Verify: fill in the actual test account id ...
   ```

   Each line is the doubt id, its level, the test case id and the remark.
   `--json` gives the same data with the authored text of each part;
   `--ungrouped` shows only the doubts no question holds yet; `--all` also
   shows closed ones; no `--story` lists every story.

2. **Group.** The agent writes the register `doubts/<STORY-ID>.yaml`, one
   entry per root question:

   ```yaml
   story: /stories/US-DEMO-001.md
   questions:
     - id: Q-US-DEMO-001-01
       question: "Which test account (name, id) is the scenario 1 approver, and which mailbox receives the email?"
       about: [HS-04, HS-05]
       home: "table:Scenario data"
       proposed: null
       members: [SC-DEMO-HS-04-01#data, SC-UAT-DEMO-J04#data]
   ```

   - `id` is append-only and never reused.
   - `question` is one sentence ending in `?`, answerable by you.
   - `about` names the story's ACs, rules or components it concerns.
   - `home` is where a correcting answer is written: `ac:<id>`, `rule:<id>`,
     `rule:new`, `component:<id>`, `table:<heading>` or `none`.
   - `proposed` is the assumption the test cases already make, so you can
     accept it; `null` when the part holds a placeholder (any stand-in for an
     unknown value) and there is nothing to accept.
   - `members` are the doubts one answer settles. SIT and UAT doubts can
     share a question.

   The register holds questions only. It has no answer field and no status:
   state comes from Resolutions, so nobody can close a doubt by editing it.
   Lint must pass, then the agent commits as `tc-agent`.

3. **Ask.** The agent emits a card and shows you every question on it, with
   its proposed answer and, for each member, the test case, the column, the
   level and the current text:

   ```
   $ py tools/wiki.py doubts card --story US-DEMO-001 --top 5
   build/cards/doubts-US-DEMO-001-001.json: 5 question(s)
   next:
     py tools/wiki.py card revise build/cards/doubts-US-DEMO-001-001.json --by <user> --answer Q-US-DEMO-001-01=accept   (or --answer Q-US-DEMO-001-01="<text>")
     py tools/wiki.py doubts answer --card build/cards/doubts-US-DEMO-001-001.json --by <user>
   ```

   `--question Q1,Q2` picks questions, `--top N` keeps the first N in impact
   order. A question is an `ask` while it has open doubts and a `confirm` once
   none is open: its parts were rewritten after your correction, or your
   correction needed no text change and you confirm the text as it stands. If the grouping is wrong
   (one member needs a different answer), say so: the agent regroups, you
   discard the card (`card discard <card> --by <you>`) and it emits a new one.

4. **You answer.** For each question, either `accept` (only when there is a
   proposed answer: it confirms the text shown) or your own words. The agent
   shows you the exact command with your words in it and runs it only when you
   say so:

   ```
   py tools/wiki.py card revise <card> --by <you> --answer Q-US-DEMO-001-01="<your words>"
   py tools/wiki.py doubts answer --card <card> --by <you>
   ```

   `doubts answer` writes one asserted Resolution per answered question
   (`answers: Q-...`, your words verbatim under `# Human Statement`) and
   commits it with an `Assertion-Event:` trailer. Questions you skip go on a
   later card.

5. **Accept: the levels lift.** The agent renders and seals. Each confirmed
   part renders High with the remark
   `Source: R-US-DEMO-001-24 - human answer to Q-US-DEMO-001-01 (operator, 2026-10-05).`
   and its frontmatter part gains `authored` (the level the AI gave it) and
   `resolution`. A plain render re-renders only the lifted test cases; every
   other test case stays byte-identical.

6. **Your words: rewrite, then confirm.** A correcting answer lifts nothing
   yet. The agent writes your answer to the question's `home` in the story,
   fills the Resolution's `# Propagation`, runs the cascade, rewrites the
   member parts in the spec, renders and seals. Then it emits a new card whose
   `confirm` questions show the rewritten text. Your `accept` on that card
   lifts them; a further correction loops again. When your correction needed
   no text change, the next card still asks you to confirm each member's
   current text (`Answered by R-...`); the agent never confirms for you.

## Answering in chat does not count

If you tell the agent an answer in conversation ("the profile is ID-1234567,
set it to High"), it will not raise the level. It makes sure a question
covers those doubts, emits the card for it, and asks you to let it record
your words on the card. That costs one sentence and it is what makes the
level trustworthy: every High part in a workbook traces to a source or to a
signed answer.

## What you see in the workbook

`suite compile` adds an `Doubts` sheet after the test-case sheets when the
selected test cases have open doubts. One row per question that touches a
selected test case, in impact order, then one row per ungrouped doubt (status
`ungrouped`, the remark as its text). Columns: Question ID, Question, Status,
Test cases, Lowest level, Affected (TC id / column), Answer, then blank
Observation, Observed by and Date for the tester. On the test-case sheets,
each Remarks line of a grouped doubt carries its question id, for example
`**Field / Values**: Low [Q-US-DEMO-001-01] - Inferred: ...`.

Open doubts never block an export; `wiki next` shows them as a non-blocking
`also:` line.

## The tester route

A tester who knows the answer writes it in the Observation column of the
`Doubts` sheet (and their name and the date). Give the filled workbook to
the agent: `doubts observe` records the text verbatim in
`doubts/observations/<story>.yaml`, and on the next card that text is the
question's proposed answer, marked as the tester's observation. You still
answer: `accept` it or give your own words. An accepted observation is a
correcting answer, so the test case text is rewritten and you confirm it on a
new card like any correction. A tester's observation never raises a level by
itself.

## Refusals and why

- **The raise ratchet.** The renderers refuse a spec whose level is higher
  than the level the test case was last authored with:

  ```
  render_sit REFUSED: confidence raised without a human answer in US-DEMO-001
    ERROR SC-DEMO-HS-04-01: confidence.data raised from Low to High - only a human answer raises a level (py tools/wiki.py doubts card --story US-DEMO-001)

    1 problem(s). Nothing was written.
  ```

  There is no override flag. The way up is a question.

- **`doubts card`** refuses without a valid register, for an unknown
  question id, a closed question, or when nothing is eligible.

- **`doubts answer`** refuses, writing nothing, when the card is missing, not
  JSON or not a doubts card; is for another story; has no answers; was
  answered by someone other than `--by`; is already applied; or when the
  register or a spec changed after the card was emitted (discard it with
  `card discard <card> --by <you>`, the one way out of an answered card, and
  emit a new card). It also refuses `accept` on a question with no proposed
  answer, or on a member whose test case is stale or not yet bound; when the
  working tree has other uncommitted changes; and when the repository does
  not lint clean. If its commit still fails, it rolls the answer back.

- **L15** rejects an invalid register (a question that does not end in `?`,
  a bad or repeated id, an `about` that is not a story fragment, a `home`
  that names no AC, rule, component or body heading, an unknown key, a member
  that is not a doubt, belongs to another story or sits in two questions, a
  question with no members that no Resolution answers), a spec under
  `tools/*_specs/` that cannot be read, a Resolution that carries `effect`,
  `confirmed_parts` or `member_basis` without `answers` and `card`, an answer
  Resolution that names no real question or member or was committed by
  anything but `doubts answer`, and a test case lifted to High without an
  asserted confirming answer Resolution behind it:

  ```
  L15 doubts/US-FIXTURE-DOUBTS.yaml: Q-US-FIXTURE-DOUBTS-02: question must end with '?'
  ```

  While the register is invalid, `doubts list` says `register invalid - run:
  py tools/wiki.py lint` and the workbook shows every doubt as ungrouped.

- **W8** warns while open doubts sit outside every question; **W9** warns
  while a confirmed doubt is not yet rendered (it names the render command).
