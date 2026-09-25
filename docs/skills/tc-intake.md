# tc-intake

Turns a pile of files in `PUT_FILES_HERE/` into ingested sources under
`sources/`. The CLI decides everything decidable; this skill handles the part
it deliberately refuses to decide: names that become permanent identities.

## When to use it

- Files are waiting in `PUT_FILES_HERE/`.
- `triage` refused or asked about a file.
- You want a PRD, Figma export or deck ingested.

Not for aligning stories (`tc-align`) or classifying what changed in a new
PRD version (`tc-change-report`).

## How it runs

1. `py tools/wiki.py triage` prints a routing plan and emits a card at
   `build/cards/triage-NNN.json`. Nothing moves yet.
2. Every **REFUSED** row is resolved with you:
   - *Unstable Figma page name*: what is the screen? The file is renamed in
     `PUT_FILES_HERE/` (kebab-case). The stem becomes `figma#<stem>` forever.
   - *Non-lowercase extension*: renamed.
   - *Competing destination*: two files route to the same place. You say
     which is current.
3. Every **ASK** row is one question: **does this document state acceptance
   criteria?** Yes means it is the PRD; no means reference material. For a
   folder, first whether one answer covers all its files or it must be walked
   file by file.
4. Your answers are recorded on the card:
   ```
   py tools/wiki.py card revise build/cards/triage-NNN.json --by <you> --answer <qid>=accept|prd|reference|split|ignore
   ```
5. `py tools/wiki.py triage --apply --card build/cards/triage-NNN.json`
   moves the files into `inputs/prd/vN/`, `inputs/figma/`, `inputs/decks/`,
   `inputs/reference/`.
6. The ingest commands triage prints run next: `ingest-prd`, `ingest-figma`,
   `ingest-decks`, `ingest-reference`.
7. `py tools/wiki.py next` hands you the next action.

## What you get

- `sources/prd/<section>.md`: one concept per PRD section, verbatim body,
  tables preserved as markdown.
- `sources/figma/<page>.md`: one concept per page PNG, with an image hash.
- `sources/decks/<deck>/slide-NN.md`, `sources/reference/*.md`.
- `manifest.json` rebuilt; `index.md` files regenerated.

## Refusals and why

- `--apply` refuses without a fully answered card. Nobody answers the card
  on your behalf.
- A Figma PNG or reference document that has already been ingested is never
  renamed; that would be an identity change.
- A `.pptx` is never the PRD; decks carry no acceptance criteria. `.xlsx` is
  reference material.
- `ingest-prd` on a version newer than the adopted one stages a change
  report instead of adopting. That hands over to `tc-change-report`.

## Tips

- Prefer triage over placing files directly under `inputs/`. Direct placement
  skips the "already holds a document" check, and two PRDs in one version
  directory make `ingest-prd` pick one silently.
- Keep exactly one document per PRD version directory.
