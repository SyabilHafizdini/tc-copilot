---
name: tc-change-report
description: Handle a NEW PRD VERSION — stage it, classify the change report section by section (editorial vs material), present conflicts against asserted Resolutions, and run approval or rejection at human instruction. Use when a new/updated PRD is uploaded or the human asks what changed between PRD versions. Handles the SOURCE document only: re-aligning the affected stories afterwards is tc-align, and a correction the human states in conversation (no new PRD) is tc-correct.
---

# tc-change-report — PRD re-ingestion (spec §12.3)

Nothing about a new PRD version touches adopted content until a human
approves the change report as a unit. Generation stays pinned to the adopted
version throughout (verified: gate + status show the divergence while staged).

## Protocol

1. Place the new PRD under `inputs/prd/v<N+1>/` (pdf or md), then:

   ```
   py tools/wiki.py ingest-prd
   ```

   Because a version is already adopted, this STAGES: parses sections, writes
   `staging/prd-v<N>.json` + `changereports/CR-NNN.md` (status pending), sets
   `staged_prd_version`. `sources/prd/` is untouched. Section matching is by
   heading number first, moved-detection by identical content hash, fuzzy
   title match (≥0.85) for renumbered-and-edited sections.
2. **Classify** (this is your LLM-proposed contribution, spec P5): edit the
   CR's Section Changes, replacing each `classification: unclassified` with
   `editorial` or `material` plus one sentence of reasoning. Refine the
   `# Summary` narrative. Commit as tc-agent.
3. **Present conflicts FIRST.** The CR's `# Conflicts` section lists asserted
   Resolutions inside affected stories — these are the dangerous class.
   (Verified on a real re-ingest: a v2 change to one PRD section flagged the resolution
   about that very section.) Walk the human through conflicts, then changes,
   then impact.
4. Human decides — run exactly one of:

   ```
   py tools/wiki.py approve-cr CR-NNN --by <user>
   py tools/wiki.py reject-cr CR-NNN --by <user>
   ```

   Approve = adopt as a unit: modified sections get the new body with the old
   preserved under `# Superseded (vN)`, added sections created, removed ones
   flagged `removed_in`, moved ones aliased via `also_known_as`;
   `adopted_prd_version` flips; the staleness cascade fires automatically
   (affected aligned stories → needs-review). Reject = staged version stays
   recorded, adoption unchanged, generation stays pinned.
5. After approval: affected stories need re-alignment (tc-align) or, if the
   human judges no material impact, a direct re-assert:
   `py tools/wiki.py assert story <id> --by <user>` (refreshes source pins;
   gate reopens — verified).

`py tools/wiki.py diff --prd` prints the adopted-vs-staged section diff on
demand without side effects.

## Not this skill

- The human corrected something in conversation, no new PRD file → `tc-correct`.
- Re-aligning a story the approved CR put into `needs-review` → `tc-align`.
- Regenerating the TCs the cascade staled → `tc-generate-sit` / `tc-generate-uat`.
- Deciding which TCs a dead requirement kills → `tc-lifecycle` (`void-ac`).
