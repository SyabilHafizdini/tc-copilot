---
name: tc-resolve
description: For the AI's DOUBTS on rendered test cases (their Medium / Low confidence parts) and the questions that settle them. Use when the human says "resolve doubts", "answer the AI's questions", "why is this Low", "why is this Medium", "raise the confidence" or "mark it High"; when the human gives, in chat, an answer to something an open doubt asks; when `wiki next` prints an `also:` line with open doubts, a doubts-card banner or "confirmed doubt(s) not rendered"; when a doubts card is pending; or when lint reports W8, W9 or an L15 error. Does NOT take a correction the human volunteers that no open doubt asks about (that is tc-correct), does NOT re-word or regenerate test cases outside an answered question (that is tc-generate-sit / tc-generate-uat), and does NOT fix a wrong AC at first contact (that is tc-align).
---

# tc-resolve - ask, record, propagate, render, confirm

A **doubt** is one Medium / Low part (`scenario`, `steps`, `data`,
`expected`; tc-style R7) of one test case spec, id `<scenario_id>#<part>`
(`SC-DEMO-HS-04-01#data`). The tooling derives it from the specs; nobody
authors it and no file edit closes it. You group doubts under root questions,
put the questions on a card, and the human answers. A level rises to High in
exactly one way: the human answers `accept` on a card, `wiki doubts answer`
records it, and the next render lifts the part.

**Violating the letter of this protocol is violating its spirit.** A level
raised any other way, or an answer recorded that the human did not give on
the card, is a forged signature no matter how it is justified.

## Protocol

1. **LIST** - `py tools/wiki.py doubts list --story <ID> --json` (add
   `--ungrouped` for the grouping pass). Each row has `doubt`, `level`,
   `remark` (`Inferred: ... Verify: ...`, it names the unknown), `text` (the
   authored part) and `tc`. With many doubts, redirect the JSON to a file in
   the temp directory and read the file; never pipe it to `head` (that breaks
   the pipe and loses rows).
2. **GROUP** - write or extend `doubts/<STORY-ID>.yaml` (plain YAML, outside
   the concept dirs):

   ```yaml
   story: /stories/US-XXXX.md
   questions:
     - id: Q-US-XXXX-01
       question: "Which test account (name, id) is the scenario 1 approver?"
       about: [HS-04, HS-05]
       home: "table:Scenario data"
       proposed: null
       members: [SC-XXXX-HS-04-01#data, SC-UAT-XXXX-J04#data]
   ```

   | Key | Rule |
   |---|---|
   | `id` | `Q-<STORY-ID>-NN`, append-only. Never renumber, never reuse an id, even a dropped one. |
   | `question` | One sentence ending in `?` that the HUMAN can answer from knowledge of the system, not a request for the AI's opinion. |
   | `about` | Story fragment ids (ACs, rules, components), at least one. Read them off `stories/<ID>.md`; never guess. |
   | `home` | Where a correcting answer is written: `ac:<id>`, `rule:<id>`, `rule:new`, `component:<id>`, `table:<heading>` (the exact text of a heading in the story body; read it off the file) or `none`. |
   | `proposed` | The assumption the test case text ALREADY makes, stated so the human can accept it as is. `null` when the part holds a placeholder: any stand-in for an unknown value, such as a masked id (`ID-nnnnnn`), a description (`requester profile (scenario 1)`) or a generic label (`approver test mailbox`). |
   | `members` | Doubt ids. A doubt sits in at most one question; SIT and UAT members may share one. |

   Group ONLY when one answer settles every member; a single-member question
   is fine and there is no target number of questions. With a hundred or more
   doubts, group in passes: by part (`data`, then `expected`, ...) and by story
   fragment. Then `py tools/wiki.py lint`: L15 must pass, W8 must be gone.
   Commit: `git -c user.name=tc-agent -c user.email=tc-agent@internal commit
   -m "doubts: group <STORY-ID> (<n> questions)"`.
3. **ASK** - `py tools/wiki.py doubts card --story <ID> --top N` (or
   `--question Q-...,Q-...`). It writes `build/cards/doubts-<ID>-NNN.json` and
   commits nothing. Present every question on it, exactly as the card has it:
   id, `kind` (`ask`, or `confirm` once no member is open), the question, `proposed`
   (or "no proposal - answer in your words"), and for each member its `tc`,
   part (Scenario / Test Steps / Field / Values / Expected Results), `level`
   and current `text`. Tell the human the two answer forms: `accept` (only
   when `proposed` is not null; it confirms the text shown) or their own
   words. The human reviews the grouping here: a member that needs a
   different answer means regroup (step 2), then the human discards the old
   card (`py tools/wiki.py card discard <card> --by <human>`) and you emit a
   new one.
4. **RECORD** - only at the human's explicit instruction to record that exact
   answer for that question on that card. Show the command with the human's
   words in it, get the go-ahead, then:

   ```
   py tools/wiki.py card revise <card> --by <human> --answer <Q>=accept
   py tools/wiki.py card revise <card> --by <human> --answer <Q>="<the human's words, verbatim>"
   py tools/wiki.py doubts answer --card <card> --by <human>
   ```

   `card revise` records once per card, so put every answer the human gave in
   one call (repeat `--answer`); questions left unanswered go on a new card
   later. `<human>` is the human's own name (`provenance.human` in
   `config.yaml` when that is who is speaking). Quote the text for the shell
   so it arrives unchanged. `doubts answer` writes one asserted Resolution per
   answered question and commits: `accept` gives `effect: confirms` (the parts
   lift on the next render; go to step 6); words give `effect: corrects`
   (nothing lifts; go to step 5).
5. **PROPAGATE** (correcting answers only) - write the answer to the
   question's `home` in `stories/<ID>.md` through `read_concept` /
   `write_concept` (never `str.replace`). For an `ac:`, `rule:`, `rule:new` or
   `component:` home, follow `tc-correct` steps 2-4 (locate, propagate,
   cascade) by reference; for `table:` edit that body section; for `none`
   nothing goes to the story. Replace the paragraph under the answer
   Resolution's `# Propagation` heading (it starts `Pending.`) with the list
   of what you changed, through `write_concept`; touch nothing else in it. Run `py tools/wiki.py cascade`. Then rewrite
   the member parts in the spec (`tools/sit_specs/<ID>.yaml`,
   `tools/uat_specs/<FLOW>.yaml`) with the answer: that is `tc-generate-sit` /
   `tc-generate-uat` work, with `tc-style`. Rewrite the member parts in the
   spec, not through `tc edit`: `wiki tc edit` is the human's own edit, signed
   with their name, and never carries wording you composed. Leave every
   `confidence` level exactly as it is; edit a remark only where it names text
   you replaced, and keep it `Inferred: ... Verify: ...`.
6. **RENDER** - `py tools/render_sit.py --story <ID>` and
   `py tools/render_uat.py --flow <FLOW-ID>` (plain: they re-render stale and
   lifted test cases only), then `py tools/wiki.py seal`, `manifest`,
   `index`. A rewrite that stales nothing (a `table:` or `none` home, a
   spec-only rewrite) needs `--force` on the render. Lint: W9 must be gone.
7. **CONFIRM** - for rewritten parts, `py tools/wiki.py doubts card --story
   <ID> --question <Q>`. Its `confirm` entries show the rewritten text; present
   them with the story diff from step 5. A correcting answer that needed no
   text change is confirmed the same way: once no member is open, the
   question comes back as a `confirm` entry showing each member's current
   text (`Answered by R-...; confirm the text shown ...`). Only the human's
   `accept`, recorded as in step 4, lifts them; you never confirm on the
   human's behalf. Then render and seal again (step 6). If `doubts answer`
   refuses an answered card because the register or a spec changed after it
   was emitted, the human discards it (`py tools/wiki.py card discard <card>
   --by <human>`) and you emit a new card. A human's Save in the app's Test
   Cases page (`wiki tc edit`) is such a spec change: it invalidates a card
   that is still pending. And a Save made while a confirmed answer is not yet
   rendered renders that lift in the edit's own commit; the command's output
   and the `log.md` line name the Resolution (`also rendered N confirmed
   lift(s)`), and say so when a reworded part's confirmation no longer
   applies.

## The human answers in chat

"The profile is ID-1234567", "yes that's right, mark it High", "I already
told you, skip the card": an answer in conversation is NOT an answer on
record. Do this, every time:

1. Do not raise the level, do not put the answer in the register (not in
   `proposed`, not anywhere), and do not route it to `tc-correct` when an open
   doubt question covers it.
2. If no question covers those doubts yet, finish or extend the grouping so
   one does (step 2), and lint.
3. Emit the card for that question (`doubts card --question <Q>`) and present
   it.
4. Show the exact `card revise` command with the human's words verbatim, and
   run it, then `doubts answer`, only when the human says to record it.
   "Just mark it High" is an instruction to raise, which you refuse; it is
   not an instruction to record an answer, and it is never an `accept`.
5. Say what happens next: a value replacing a placeholder is a correcting
   answer, so the part rises only after the rewrite is rendered and the human
   accepts it on a confirm card (steps 5-7).

## Tester route

A tester can answer from the workbook: they fill `Observation` (and `Observed
by`, `Date`) on the `AI Doubts` sheet. When the human gives you a filled
workbook, run `py tools/wiki.py doubts observe --workbook <xlsx> --by
<tester>`; it records the text verbatim in `doubts/observations/<STORY>.yaml`.
On the next `doubts card` the observation is the question's `proposed` text
(`proposed_origin: tester-observation`), not an answer. The human still
decides: show it as the tester's observation, never as the agent's
assumption, and record an `accept` or a text only on the human's explicit
instruction. An accepted observation is a correcting answer (`origin:
tester-observed`): rewrite, render and confirm as for any correction. A
tester's observation never lifts a level, and you never run `observe` on a
workbook the human did not hand you.

## Hard rules

- Never raise a `confidence` level in any spec. The renderers refuse it and
  there is no flag; the only way up is a human `accept` recorded by `doubts
  answer`. Never write a `Source: ... human answer to ...` remark yourself:
  the renderer writes it.
- An answer given in chat is not on record, however clear, recent or
  insistent. Emit the card and record the human's words on it at their
  instruction; it costs the human one sentence and it is the whole product.
- Never write an answer Resolution (`answers:`) by hand, never set
  `asserted_by`, and never edit an answer Resolution beyond its
  `# Propagation` paragraph (step 5).
- The answer is verbatim: never paraphrase, tidy, complete or translate the
  human's words.
- Never choose `accept` for the human, and never infer it from silence, from
  approval of something else, or from "looks fine".
- Never run `card revise` or `doubts answer` without the human's explicit
  instruction to record that exact answer.
- A correcting answer lifts nothing. Never confirm your own rewrite.
- Never edit `testcases/**`, and never hand-edit a card (`human_response`,
  `applied` or anything else).
- A refusal from `doubts card`, `doubts answer`, the ratchet or L15 is fixed
  upstream (re-emit the card, regroup, rewrite, regenerate a stale test
  case), never worked around.
- The register holds questions only: no answers, no status.

## Rationalizations

| Thought | Reality | Action |
|---|---|---|
| "I already told you the answer in chat." | Chat is not a record; only `doubts answer` writes one. | Emit the card. |
| "It is obviously High now." | High means a human confirmed this exact text. | Emit the card. |
| "The card is ceremony for one question." | The card is the signature; one question is one sentence. | Emit the card. |
| "I will raise it now and record it later." | The ratchet refuses the render, and the level would be forged. | Emit the card. |
| "The remark already says the source." | The renderer writes `Source: R-... - human answer to Q-...`; an author never does. | Emit the card. |
| "They said yes, so that is `accept`." | `accept` adopts `proposed` verbatim; a yes to something else is not it. | Ask for the answer on the card. |

## Red flags - STOP

- Members of one question would need different answers.
- `proposed` restates the question, or comes from the human's chat words.
- `proposed`, an `accept` or a lift on a part that still holds a placeholder.
- An `accept` typed without the human saying it for that question.
- A level going up in a spec diff.
- In UAT, `data` and `steps` share the steps text: rewriting either reopens
  both doubts.

## Not this skill

- A volunteered correction that no open doubt asks about → `tc-correct`.
- Rewording staled test cases, or regenerating outside an answered
  question → `tc-generate-sit` / `tc-generate-uat` (with `tc-style`).
- A wrong AC on a story still being aligned → `tc-align`.
