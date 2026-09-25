# DUMPING GROUND

Drop **anything** in this folder — a PRD (pdf, docx or md), Figma page
exports (png), decks (pptx), rule files, spreadsheets — in any order, with
no naming ceremony.

Then run:

```
py tools/wiki.py triage
```

Triage sorts what it can decide from the file type alone (png -> Figma,
pptx -> decks) and **asks about everything else**, one question per file,
plus one per folder that directly holds files. The questions land in
`build/cards/triage-NNN.json`.

The question is always the same: **does this document state acceptance
criteria?** If it does, it is the PRD. If it does not, it is reference
material — still kept, still hashed, still citable, but nothing generates
test cases from it.

Answer every question, then apply:

`triage` prints the exact two commands to run, with every question id already
filled in. Copy that block verbatim — ids carry a path digest suffix, so they
are not worth retyping:

```
py tools/wiki.py card revise build/cards/triage-001.json --by <you> \
  --answer q-folder-L-L-control-76d8ef=accept \
  --answer q-file-spec-docx-a1b2c3=reference
py tools/wiki.py triage --apply --card build/cards/triage-001.json
```

`--apply` refuses unless every question is answered, the dump has not changed
since the card was emitted, and the card still carries exactly the questions
`triage` asks — a hand-edited card is refused, never honoured. A folder answer settles its direct
files; answer `split` to walk them one by one; answer `ignore` to leave a
file here.

Triage still **refuses** rather than guesses when a name would become a
permanent identity — a Figma png called `Screenshot 2026-08-24.png` would
create the concept `figma#Screenshot 2026-08-24` forever. Rename it to what
the page actually is (`order-list-screen.png`) and re-run.

Nothing is ever deleted. Files you drop here are git-ignored until triage
moves them.
