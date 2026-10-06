# tc-change-report

Handles a new PRD version of one PRD (a project can hold several; every
step names which). Nothing about it touches adopted content until
you approve the change report as a unit. Generation stays pinned to the
adopted version throughout.

## When to use it

- A new or updated PRD was uploaded.
- You want to know what changed between PRD versions.

Not for a correction you state yourself (`tc-correct`), not for re-aligning
the stories afterwards (`tc-align`).

## How it runs

1. The new version arrives under `inputs/prd/<id>/v<N+1>/` through
   `tc-intake` (triage, with your PRD and version answers), or you place it
   there; the agent does not place it. Then `py
   tools/wiki.py ingest-prd --prd <id>` runs (`--prd` is optional while
   exactly one PRD is registered; with several, omitting it is refused and
   the ids are listed). Because that PRD already has an adopted version, this
   **stages**: sections are parsed to `staging/<id>/prd-v<N>.json`, a change
   report `changereports/<id>/CR-NNN.md` is written with status pending
   (report numbers are unique across the project), and that PRD's
   `staged_version` is set. `sources/prd/<id>/` is untouched, and so is every
   other PRD. Re-running on an already-staged version writes no second
   report; a changed document for a version with a pending report is refused;
   a version below the adopted one is refused. After a rejection,
   re-ingesting an identical document writes nothing, and a changed one
   produces a new pending report. The new report does not name the rejected
   one; the `ingest-prd` console output prints a note that does.
   Sections are matched by heading number, then by identical content hash
   for moves, then by fuzzy title for renumbered-and-edited sections.
2. **Classify.** The agent replaces each `classification: unclassified` with
   `editorial` or `material` plus one sentence of reasoning, and refines the
   summary. Committed as `tc-agent`.
3. **Conflicts first.** The report's `# Conflicts` section lists asserted
   Resolutions inside affected stories. These are the dangerous class and
   are walked through before changes and impact.
4. **You decide**, one command:
   ```
   py tools/wiki.py approve-cr CR-NNN --by <you> --prd <id>
   py tools/wiki.py reject-cr  CR-NNN --by <you> --prd <id>
   ```
   These run only when you say so, with `--by` your own name. The id must
   be `CR-<number>`; a report that belongs to another PRD is refused with the
   `--prd` to use. Approve adopts as a unit: modified sections get the new
   body with the old preserved under `# Superseded (vN)`, added sections are
   created, removed ones flagged, moved ones aliased; that PRD's
   `adopted_version` flips; the staleness cascade fires and aligned stories
   that cite a changed or removed section of that PRD become `needs-review`
   (once; the cause names a removal). Stories citing only other PRDs are not
   touched. Approval is one commit, and approving one PRD never touches
   another. Reject leaves adoption unchanged and generation pinned; the
   staged version stays, and `wiki next` reports the rejection and that a
   corrected document is awaited. Nothing happens until you supply one: it
   goes through triage as the next version number (a fresh change report), or,
   if you want the same version number, you replace the file under
   `inputs/prd/<id>/v<N>/` yourself and, once you say the file is in place,
   the agent runs `ingest-prd --prd <id>`, which writes a new pending report
   (the report does not name the rejected one; the console output prints a
   note that does). The agent never deletes, moves or
   replaces a document under `inputs/prd/`.

   A report can be approved only if it is for the PRD's currently staged
   version, newer than the adopted one, and written against the version still
   adopted. If v3 is staged while v2's report is still pending, v2's report
   cannot be approved any more (the output names the report to act on) and
   can only be rejected; the agent tells you and rejects it only when you
   say so.
5. After approval, each affected story is either re-aligned (`tc-align`,
   material change) or re-asserted directly when you judge no material
   impact:
   ```
   py tools/wiki.py assert story <id> --by <you> --card <card>
   ```
   (a re-assert also settles a removed-section flag).

`py tools/wiki.py diff --prd <id>` shows the adopted-versus-staged diff of one
PRD at any time with no side effects. The app's Changes page lists each PRD's staged version and its pending report id, with the
`diff --prd <id>` command to read the changes; it does not show the report body; approve and reject stay CLI commands.

## What follows

- Re-alignment: `tc-align`.
- Regenerating staled test cases: `tc-generate-sit` / `tc-generate-uat`.
- A requirement the new PRD removed: `tc-lifecycle` (`void-ac`).
