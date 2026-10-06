---
name: tc-intake
description: Route files a human dumped into PUT_FILES_HERE/ into the typed intake tree and ingest them - run triage, resolve every refusal WITH the human (Figma page names, which PRD, PRD version), apply, then chain into ingest-prd/figma/decks. Use when files are waiting in PUT_FILES_HERE/, when triage refuses a file, or when asked to ingest a PRD, Figma export, or deck. Does NOT align stories (that is tc-align) and does NOT classify a new PRD version's changes (that is tc-change-report, after ingest).
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
4. For every file the human answers `prd`, ask two more questions before
   applying, and never infer either from the file name:
   - **Which PRD is this?** List the registered PRDs (`py tools/wiki.py
     status` prints one `PRD <id>: ...` line each). The answer is an existing
     id, or a new id plus a title (id: lowercase-hyphen slug matching
     `^[a-z0-9][a-z0-9-]{1,63}$`, for example `rental-application`). With
     exactly one registered PRD triage defaults to it, but still ASK "is this
     `<id>`, or a new PRD?" before applying: a second PRD arriving on a
     one-PRD project is exactly the case the default gets wrong.
   - **Which version is it?** State the adopted version of that PRD and the
     next number (`v1` for a PRD with nothing adopted), and let the human
     confirm. A version is a whole number from 1 with no leading zero.
5. Record the answers in one command:
   `py tools/wiki.py card revise build/cards/triage-NNN.json --by <human>
   --answer <qid>=accept|prd|reference|split|ignore ...`
6. `py tools/wiki.py triage --apply --card build/cards/triage-NNN.json`, and
   for a `prd` file add the human's answers: `--prd <id>` (omit only when
   exactly one PRD is registered and the human confirmed it),
   `--prd-title "<title>"` (only for a new id) and `--prd-version N`
   (required). `--apply` refuses a `prd` file with no PRD answer when zero or
   several PRDs are registered (the refusal lists the registered ids), a new
   id with no `--prd-title`, a `prd` file with no `--prd-version`, a version
   that is not a whole number from 1, a version below the adopted or the
   staged one (the refusal names the next version), a version directory that
   already holds a document, and two files answered `prd` in one apply (apply
   them one at a time, each with its own answers). Triage never overwrites or
   deletes a PRD document. The Figma, deck and reference routes do replace an
   existing file of the same name; the plan and the result then say
   "(REPLACES existing)", so tell the human before applying.
   When a version directory is occupied, STOP and ask the human. The refusal
   names the next free version and says the old document may be moved out by
   the human: the agent never deletes, moves or replaces a document under
   `inputs/prd/` itself.
7. Run the follow-up commands triage prints (`ingest-prd --prd <id>`,
   `ingest-figma`, `ingest-decks`, `ingest-reference`).
8. `py tools/wiki.py next` - hand the human their next action.

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
- Never delete, move or replace a document under `inputs/prd/` on your own
  initiative, including to clear an occupied version directory. Ask the
  human; a corrected document after a rejected change report is handled by
  `tc-change-report`.
- `ingest-prd --prd <id>` on a version newer than that PRD's adopted one
  STAGES a change report for that PRD rather than adopting it - that is
  `tc-change-report`, not this skill. Other PRDs are untouched.
- Never pick the PRD for the human. Two PRDs with similar names are exactly
  the case a guess gets wrong, and the id is permanent. The same goes for the
  version: it is the human's answer, never read off a file name.
- `ingest-prd` refuses, and the refusal is the product (fix the document or
  the answer, never the tool): a version directory with more than one
  candidate document, an empty document (no sections), a heading whose
  section file would be `index` or `log`, two sections with the same
  heading path, and a version lower than the adopted one. Only directories
  named `v<N>` (N from 1, no leading zero) count as versions. Ask the human
  to fix the document or to remove the extra file themselves.

## Not this skill

- Turning ingested sources into an aligned story → `tc-align`.
- Classifying what changed in a new PRD version → `tc-change-report`.
- Anything about test cases → `tc-generate-sit` / `tc-generate-uat`.
