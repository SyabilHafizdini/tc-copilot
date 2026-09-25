---
name: tc-lifecycle
description: Change a test case's LIFECYCLE STATE — retire, void-ac, unretire, and resolve W4 hand-edit drift (release/revert). All human-gated, with a coverage-impact check first. Use when a requirement dies, a TC is superseded, a retired TC must come back, or lint reports W4 drift. Does NOT write or re-word TC content (that is tc-generate-sit/uat) and does not act on stale TCs — stale is system-computed and resolved by regenerating.
---

# tc-lifecycle — retirement, voiding, drift

All commands are HUMAN-GATED (`--by` required): run them only at explicit
human instruction, after presenting the coverage impact. Stale is
system-computed; retired is human-asserted; the system never retires on its
own except the sanctioned void cascade (§13.3).

## Before any retirement: present coverage impact

Read the RTM (`py tools/wiki.py rtm`, then `build/rtm/matrix.md`) and tell
the human what retiring leaves uncovered vs inherited. Redundancy claims
without this check are unverifiable.

## Commands (all verified this repo)

```
# requirement replaced — successor must cover every active AC of the retiree
py tools/wiki.py retire <tc-id> --by <user> --reason superseded --superseded-by <tc-id>
# refuses (L5) if the successor's covers misses any of them; writes the
# reciprocal supersedes on the successor in the same commit (L9)

# requirement dead — void at the AC, the cascade does the retiring
py tools/wiki.py void-ac /stories/<id>.md#<AC-id> --by <user> \
    --caused-by /sources/prd/<sec>.md --cause-version <n> [--note "..."]
# TCs whose covers are ALL voided -> retired:voided (inherited authority);
# TCs with mixed coverage -> stale for human decision, NOT retired

# resurrection permit (spec §7.4-4)
py tools/wiki.py unretire <tc-id> --by <user>
# retirement record moves to retirement_history (append-only); TC -> stale;
# regeneration then recreates it under its ORIGINAL ID

# drift resolution (lint W4)
py tools/wiki.py release <tc-id> --by <user>   # accept hand-edit, re-hash, origin: human-stated
py tools/wiki.py revert <tc-id>                # restore file to sealed content
```

## Verified behaviors (scratch-tested)

- Void of an AC covered by TC-A (only that AC) and TC-B (that AC + one
  active): TC-A → retired:voided with inherited cause; TC-B → stale.
- Retire-as-superseded with a successor missing one covered AC → refused.
- Retired scenario → generation reports `SUPPRESSED`, never recreates;
  after unretire, regeneration recreates under the same ID.
- RTM: voided ACs render struck-through with cause (never as gaps); retired
  TCs appear in the Retired appendix with reason/successor/asserter.
- Files never move; no archive folder; `status: retired` IS the archive.

## Not this skill

- A TC is **stale**, not wrong → regenerate it (`tc-generate-sit` /
  `tc-generate-uat`). Stale is system-computed; nothing here applies.
- A TC's wording is wrong → `tc-style` + re-render the scope with `--force`.
- The requirement changed because a new PRD landed → `tc-change-report` first;
  its approval fires the cascade, which may make retirement unnecessary.
- Excluding TCs from one test run without retiring them → `tc-suite-author`
  (`exclude_modules` / `extra_exclude`).
