---
name: tc-help
description: START HERE when you do not know what to do next — reports where the project stands, the single next command, and which skill owns it, by reading `wiki next --json`. Use when the human is lost, resuming after a break, asking "what now", "where were we", "which skill do I use", or describing a goal in their own words ("I want to export a workbook"). Read-only: it routes and never edits, generates, asserts, or ingests anything.
---

# tc-help — where am I, what next, which skill

Everything this skill reports is COMPUTED, never guessed. If the CLI did not
say it, do not say it.

## Protocol

1. `py tools/wiki.py next --json` — one read-only call, ~1s. It returns
   `{phase, banners, rows}`.
2. Report, in this order and nothing else:
   - **Where you are** — `phase.label` (`n/3`) plus the story/TC counts.
   - **Blockers first** — every banner, verbatim in meaning: a staged PRD,
     a card awaiting an answer, hand-edit drift, files in
     `PUT_FILES_HERE/`. Banners outrank rows: they block everything after
     them.
   - **The one next thing** — the first row's `state`, its `command`, and
     the `skill` that owns it. List the remaining rows compactly (one line
     each) so the human can pick a different scope.
3. Offer to invoke the owning skill. Do not invoke it without a yes.

## When the human states a goal instead of asking where they are

Map intent to owner, then confirm against real state before acting:

| They said | Skill |
|---|---|
| "I dumped some files" / "ingest this PRD/Figma/deck" | `tc-intake` |
| "align this story", "review the ACs", "the AC is wrong" | `tc-align` |
| "I have no PRD / no acceptance criteria" | `tc-align` (source-less branch) |
| "SIT test cases", "coverage map", "component gap" | `tc-generate-sit` |
| "UAT test cases", "walk the journey" | `tc-generate-uat` |
| "export", "workbook", "regression suite", "filter TCs" | `tc-suite-author` |
| "retire this TC", "someone hand-edited a TC" | `tc-lifecycle` |
| "new PRD version", "what changed" | `tc-change-report` |
| "that definition/rule is wrong" (no new PRD) | `tc-correct` |
| "run the platform", "is it healthy", "where does X live" | `run-tc-copilot` |
| "re-word this test case" | `tc-style` |
| "grade / score / judge these test cases", "how good is the SIT set", "rubric", "29119" | `tc-evaluate` (existing set) or `tc-rubric` inside `tc-generate-sit`/`-uat` (while generating) |
| "test model", "coverage items", "C = N/T", "the gap report", "improve round" | `tc-rubric` |

If state contradicts the request — they ask for SIT test cases on a story
that is still `draft` — say so and name the blocking step. Never route
around a gate to satisfy the request.

## Hard rules

- Read-only. This skill runs `next`, `status`, `lint`, `gate` and nothing
  that writes.
- Never invent a next command. If `next` returns no command for a row, the
  next action is the skill, not a command.
- Never claim work is done. Report what the CLI computed.

## Not this skill

- Actually doing any of the work above → the owning skill in the table.
- Deep platform operation (smoke, exports, artifact locations) →
  `run-tc-copilot`.
