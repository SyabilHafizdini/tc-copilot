---
name: tc-intake
description: Route files a human dumped into PUT_FILES_HERE/ into the typed intake tree and ingest them — run triage, resolve every refusal WITH the human (Figma page names, PRD version), apply, then chain into ingest-prd/figma/decks. Use when files are waiting in PUT_FILES_HERE/, when triage refuses a file, or when asked to ingest a PRD, Figma export, or deck. Does NOT align stories (that is tc-align) and does NOT classify a new PRD version's changes (that is tc-change-report, after ingest).
---

# tc-intake — dumping ground to ingested sources

`py tools/wiki.py triage` decides everything decidable. This skill exists
for the part it deliberately refuses to decide: names that become permanent
identities.

## Protocol

1. `py tools/wiki.py triage` — read the plan and the emitted card
   (`build/cards/triage-NNN.json`). Never pass `--apply` yet.
2. For every **REFUSED** row, resolve it with the human before moving on:
   - *unstable Figma page name* — ask what the screen actually is, then
     rename the file in `PUT_FILES_HERE/` (kebab-case, no spaces). The stem
     becomes `figma#<stem>` permanently.
   - *non-lowercase extension* — rename to the lowercase form.
   - *competing destination* — two dumped files route to the same place.
     Establish with the human which one is current; never guess.
3. For every **ASK** row, put the question to the human individually. The
   question is always the same one: **does this document state acceptance
   criteria?** If yes it is the PRD; if no it is reference material. Present
   triage's proposed answer and your reasoning, and let the human's answer
   win. For a folder, ask first whether one classification covers all its
   direct files, or whether it must be walked file by file (`split`).
4. Record the answers in one command:
   `py tools/wiki.py card revise build/cards/triage-NNN.json --by <human>
   --answer <qid>=accept|prd|reference|split|ignore ...`
5. `py tools/wiki.py triage --apply --card build/cards/triage-NNN.json`.
6. Run the follow-up commands triage prints (`ingest-prd`, `ingest-figma`,
   `ingest-decks`, `ingest-reference`).
7. `py tools/wiki.py next` — hand the human their next action.

## Hard rules

- Never route around a refusal by editing `wiki_triage.py` or moving files
  by hand. The refusal is the product (spec P3).
- Never answer a card on the human's behalf. `--apply` refuses without a
  fully answered card, and that refusal is the gate — do not look for a way
  past it.
- Never rename a Figma png or reference document that has already been
  ingested; that is an identity change, not a rename.
- A `.pptx` is never the PRD — a deck carries no acceptance criteria. It is
  reference material via `ingest-decks`.
- `.xlsx` is not a PRD input. It is reference material.
- `ingest-prd` on a version newer than the adopted one STAGES a change
  report rather than adopting it — that is `tc-change-report`, not this
  skill.

## Not this skill

- Turning ingested sources into an aligned story → `tc-align`.
- Classifying what changed in a new PRD version → `tc-change-report`.
- Anything about test cases → `tc-generate-sit` / `tc-generate-uat`.
