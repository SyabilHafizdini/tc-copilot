---
name: tc-correct
description: Propagate a HUMAN CORRECTION to already-asserted content through the wiki — capture the statement verbatim as a Resolution, locate affected concepts via manifest edges, propagate edits, run the staleness cascade, emit the card, and gate on human assertion. Use when the human corrects a definition, business rule, AC interpretation, or component fact. Flags staled TCs but never regenerates them (that is tc-generate-sit/uat, later, at the human's call) and never edits TC files.
---

# tc-correct — correction propagation

The fence sits between *statement* and *propagation*: the correction is
human-stated at origin, but your propagation of it can be wrong, so it is
proposed and separately asserted (spec §6.5).

## Protocol

1. **CAPTURE** — write `resolutions/R-<scope>-NN.md` immediately:
   `origin: human-stated`, `status: proposed`, `# Human Statement` VERBATIM
   (never paraphrase), `resolves:` pointing at the affected fragments.
   Commit (tc-agent).
2. **LOCATE** — traverse `manifest.json` `edges` from the corrected
   fragment/concept: inbound `covers`/`verifies_rules` (TCs),
   `uses_terms` (stories, TCs), `stories` (flows). Deterministic list; you
   only rank which need textual change vs mere staleness.
3. **PROPAGATE** — edit affected story/glossary bodies and fragments via the
   concept API (`read_concept`/`write_concept` from `tools/wiki.py` —
   NEVER `str.replace` on raw file text: YAML re-wrapping makes string
   matches silently no-op). Bump story versions; superseded resolutions get
   `status: superseded` + `superseded_by` (write the reciprocal `supersedes`
   in the same commit — lint L9 checks). Fill the Resolution's
   `# Propagation` list. **Never touch TC files.**
4. **CASCADE** — `py tools/wiki.py cascade` flags precisely: aligned stories
   whose pinned sources changed → `needs-review`; TCs whose pinned fragment
   hashes changed → `stale` with `stale_because`. Verified behavior: editing
   one AC staled exactly the 1 covering TC and left the other 29 untouched.
   Then `manifest`, `lint`. Commit (proposal commit).
5. **PRESENT** — alignment card (same contract as tc-align):
   what-you-said (verbatim) / what-I-understood (your restatement — the
   propagation-error tripwire) / what-I-changed (per-file diffs) /
   what-this-affects (cascade output: staled TC IDs + counts). The card MUST
   NOT offer "confirm + regenerate" as one action — assertion and
   regeneration are separate human acts.
6. **ASSERT** — on human confirmation: mark the Resolution asserted, run
   `py tools/wiki.py assert story <id> --by <user>` for stories the human
   re-asserts, adoption commit referencing the card. On "revise": loop to 3
   with the delta. On "discard": forward-revert the propagation commits
   (`git revert`, history preserved — never reset/amend).

Regeneration of the staled TCs happens later, when the human runs
tc-generate — testers batch corrections before regenerating anything.

## Not this skill

- First-contact alignment of a draft story or flow → `tc-align`.
- Regenerating the TCs this correction staled → `tc-generate-sit` /
  `tc-generate-uat`, when the human asks.
- The correction came from a new PRD version → `tc-change-report`.
- A TC is simply wrong and should go away → `tc-lifecycle`.
