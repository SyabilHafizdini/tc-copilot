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
4. For every file you answer `prd`, two more questions, never guessed from
   the file name:
   - **Which PRD is this?** An existing id (`py tools/wiki.py status` prints
     one `PRD <id>: ...` line each), or a new id plus a title. An id is a
     lowercase-hyphen slug such as `rental-application`. With exactly one
     registered PRD, triage defaults to it, but you are still asked whether
     this document is that PRD or a new one.
   - **Which version is it?** The adopted version of that PRD and the next
     number are stated and you confirm. A version is a whole number from 1.
5. Your answers are recorded on the card:
   ```
   py tools/wiki.py card revise build/cards/triage-NNN.json --by <you> --answer <qid>=accept|prd|reference|split|ignore
   ```
6. `py tools/wiki.py triage --apply --card build/cards/triage-NNN.json
   [--prd <id>] [--prd-title "<title>"] [--prd-version N]` moves the files
   into `inputs/prd/<id>/vN/`, `inputs/figma/`, `inputs/decks/`,
   `inputs/reference/`.
7. The ingest commands triage prints run next: `ingest-prd --prd <id>`,
   `ingest-figma`, `ingest-decks`, `ingest-reference`.
8. `py tools/wiki.py next` hands you the next action.

## What you get

- `sources/prd/<id>/<section>.md`: one concept per PRD section (id
  `prd#<id>/<section>`), verbatim body, tables preserved as markdown.
- A `PRD <id>` entry in the manifest `prds` registry: title, adopted version,
  staged version.
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
- `triage --apply` refuses a `prd` file with no PRD answer (when zero or
  several PRDs are registered; it lists the registered ids), a new id with no
  `--prd-title`, a version that is not a whole number from 1, a version below
  the adopted or the staged one (it names the next version), and a version
  directory that already holds a document, a `prd` file with no version, and
  two files answered `prd` in one apply (apply them one at a time). Triage
  never overwrites or deletes a PRD document; the agent stops and asks you
  when a version directory is occupied, and never removes a document under
  `inputs/prd/` itself. The Figma, deck and reference routes do replace an
  existing file of the same name and say "(REPLACES existing)" in the plan.
- `ingest-prd --prd <id>` on a version newer than that PRD's adopted one stages
  a change report instead of adopting. That hands over to `tc-change-report`.
  Other PRDs are untouched.
- `ingest-prd` also refuses: a version directory with more than one candidate
  document, an empty document, a heading whose section file would be `index`
  or `log`, two sections with the same heading path, and a version lower than
  the adopted one. `--prd` is optional with exactly one registered PRD; with
  several, omitting it is refused and the refusal lists the ids. A new id
  needs `--title`. Only directories named `v<N>` count as versions.

A project can hold several PRDs. Triage asks which PRD a document belongs to
and which version it is, and refuses to guess either. A new PRD needs an id
and a title.

## Tips

- Prefer triage over placing files directly under `inputs/`. Direct placement
  skips the "already holds a document" check; two documents in one PRD version
  directory are then refused by `ingest-prd`.
- Keep exactly one document per PRD version directory.
