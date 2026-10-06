---
name: tc-change-report
description: Handle a NEW PRD VERSION — stage it, classify the change report section by section (editorial vs material), present conflicts against asserted Resolutions, and run approval or rejection at human instruction. Use when a new/updated PRD is uploaded or the human asks what changed between PRD versions. Handles the SOURCE document only: re-aligning the affected stories afterwards is tc-align, and a correction the human states in conversation (no new PRD) is tc-correct.
---

# tc-change-report — PRD re-ingestion (spec §12.3)

Nothing about a new PRD version touches adopted content until a human
approves the change report as a unit. Generation stays pinned to the adopted
version throughout (verified: gate + status show the divergence while staged).
A project can hold several PRDs; every version, report and approval belongs to
ONE of them, so name the PRD in every sentence you say to the human.

## Protocol

1. The new version (pdf, docx or md) arrives under
   `inputs/prd/<id>/v<N+1>/` through `tc-intake` (triage, with the human's PRD
   and version answers), or the human places it. Do not place it yourself.
   Then:

   ```
   py tools/wiki.py ingest-prd --prd <id>
   ```

   Because that PRD already has an adopted version, this STAGES: parses
   sections, writes `staging/<id>/prd-v<N>.json` +
   `changereports/<id>/CR-NNN.md` (status pending), and sets that PRD's
   `staged_version` in the manifest `prds` registry. `sources/prd/<id>/` is
   untouched, and so is every other PRD. `--prd` is optional while exactly
   one PRD is registered; with several, omitting it is refused and the
   refusal lists the ids. Report numbers (`CR-NNN`) are unique across the
   whole project. Section matching is by heading number first, moved-detection
   by identical content hash, fuzzy title match (≥0.85) for
   renumbered-and-edited sections.

   Re-running `ingest-prd --prd <id>` on a version that is already staged
   writes no second report (it says so and changes nothing); if the document
   differs from what was staged while the report is still pending, it is
   refused - approve or reject that report, or submit the changed document as
   the next version. A version lower than the adopted one is refused. If the
   report was rejected, re-ingesting the identical document writes nothing
   (a corrected document is awaited), and a changed document produces a NEW
   pending report. The new report does not name the rejected one; the
   `ingest-prd` console output prints a note that does.
2. **Classify** (this is your LLM-proposed contribution, spec P5): edit the
   CR's Section Changes, replacing each `classification: unclassified` with
   `editorial` or `material` plus one sentence of reasoning. Refine the
   `# Summary` narrative. Commit as tc-agent.
3. **Present conflicts FIRST.** The CR's `# Conflicts` section lists asserted
   Resolutions inside affected stories - these are the dangerous class.
   (Verified on a real re-ingest: a v2 change to one PRD section flagged the resolution
   about that very section.) Walk the human through conflicts, then changes,
   then impact.
4. Human decides - run exactly one, ONLY at the human's explicit instruction,
   with `--by` set to the human's own name (a real value, never blank):

   ```
   py tools/wiki.py approve-cr CR-NNN --by <user> --prd <id>
   py tools/wiki.py reject-cr CR-NNN --by <user> --prd <id>
   ```

   The report id must be `CR-<number>`; if it belongs to another PRD the
   command says which `--prd` to use. Approve = adopt as a unit: modified
   sections get the new body with the old preserved under `# Superseded (vN)`,
   added sections created, removed ones flagged `removed_in`, moved ones
   aliased via `also_known_as`; that PRD's `adopted_version` flips; the
   staleness cascade fires automatically (aligned stories citing a changed OR
   REMOVED section of that PRD → needs-review, once, with the removal named in
   the cause; stories citing only other PRDs are not touched). Approval is ONE
   commit carrying the assertion trailer, and approving one PRD never touches
   another. Reject = that PRD's staged version stays recorded, adoption
   unchanged, generation stays pinned; `py tools/wiki.py next` then reports
   the rejection and that a corrected document is awaited.

   After a rejection do nothing until the human supplies a corrected document.
   It goes either through triage as the NEXT version number (a fresh change
   report), or, if the human wants the same version number, the HUMAN replaces
   the file under `inputs/prd/<id>/v<N>/` themselves; once the human says the
   file is in place, you run `py tools/wiki.py ingest-prd --prd <id>`, which
   writes a new pending report (the report does not name the rejected one; the
   console output prints a note that does). The `wiki next` banner and the triage refusal each suggest
   placing or removing a file; do not act on either yourself - the agent never
   deletes, moves or replaces a document under `inputs/prd/`.

   A report can be approved only if it is for the PRD's currently staged
   version, newer than the adopted one, and written against the version still
   adopted. Staging v3 while v2's report is pending leaves v2's report
   pending but unapprovable: the staging output and `wiki next` say which
   report to act on (v3's), and the old one can only be rejected. Tell the
   human, and reject the old one only when they say so. Never edit a report's
   frontmatter to get past this refusal.
5. After approval: affected stories need re-alignment (tc-align) or, if the
   human judges no material impact, a direct re-assert (human-gated, needs the
   story's emitted card):
   `py tools/wiki.py assert story <id> --by <user> --card <card>`
   (refreshes source pins; a re-assert also settles a removed-section flag;
   gate reopens - verified).

`py tools/wiki.py diff --prd <id>` prints the adopted-vs-staged section diff
of one PRD on demand without side effects. `diff --prd` with no id still works
while exactly one PRD is registered; with several it is refused and lists the
ids. The app's Changes page lists each PRD's staged version and its pending report id, with the
`diff --prd <id>` command to read the changes; it does not show the report body;
approve and reject stay CLI commands, run only at the human's instruction.

## Red flags

- Two PRDs staged at once → handle one change report at a time, naming the PRD
  in every sentence to the human. Stop if you are about to approve a report
  without having said which PRD it belongs to.
- You are about to run `approve-cr` or `reject-cr` without the human's explicit
  instruction, or with a `--by` that is not the human → stop. Only a human
  approves or rejects.
- A refusal from `approve-cr` / `ingest-prd` → fix the cause upstream (present the
  report it names to the human, ask for a corrected document). Never add a flag, edit a
  report or a tool, or move a file to get past it.

## Not this skill

- The human corrected something in conversation, no new PRD file → `tc-correct`.
- Re-aligning a story the approved CR put into `needs-review` → `tc-align`.
- Regenerating the TCs the cascade staled → `tc-generate-sit` / `tc-generate-uat`.
- Deciding which TCs a dead requirement kills → `tc-lifecycle` (`void-ac`).
