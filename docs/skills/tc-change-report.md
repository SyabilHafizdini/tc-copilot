# tc-change-report

Handles a new PRD version. Nothing about it touches adopted content until
you approve the change report as a unit. Generation stays pinned to the
adopted version throughout.

## When to use it

- A new or updated PRD was uploaded.
- You want to know what changed between PRD versions.

Not for a correction you state yourself (`tc-correct`), not for re-aligning
the stories afterwards (`tc-align`).

## How it runs

1. The new PRD goes under `inputs/prd/v<N+1>/` and `py tools/wiki.py
   ingest-prd` runs. Because a version is already adopted, this **stages**:
   sections are parsed to `staging/prd-v<N>.json`, a change report
   `changereports/CR-NNN.md` is written with status pending, and
   `staged_prd_version` is set. `sources/prd/` is untouched.
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
   py tools/wiki.py approve-cr CR-NNN --by <you>
   py tools/wiki.py reject-cr  CR-NNN --by <you>
   ```
   Approve adopts as a unit: modified sections get the new body with the
   old preserved under `# Superseded (vN)`, added sections are created,
   removed ones flagged, moved ones aliased; `adopted_prd_version` flips;
   the staleness cascade fires and affected aligned stories become
   `needs-review`. Reject leaves adoption unchanged and generation pinned.
5. After approval, each affected story is either re-aligned (`tc-align`,
   material change) or re-asserted directly when you judge no material
   impact:
   ```
   py tools/wiki.py assert story <id> --by <you> --card <card>
   ```

`py tools/wiki.py diff --prd` shows the adopted-versus-staged diff at any
time with no side effects.

## What follows

- Re-alignment: `tc-align`.
- Regenerating staled test cases: `tc-generate-sit` / `tc-generate-uat`.
- A requirement the new PRD removed: `tc-lifecycle` (`void-ac`).
