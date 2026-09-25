# tc-lifecycle

Changes a test case's lifecycle state: retire, void an AC, un-retire, and
resolve hand-edit drift. Every command is human-gated (`--by <you>`) and is
preceded by a coverage-impact check.

## When to use it

- A requirement is dead.
- A test case was superseded by another.
- A retired test case must come back.
- Lint reports W4 hand-edit drift.

Not for stale test cases (system-computed; regenerate them), not for
re-wording (`tc-style` and a forced re-render), not for excluding test cases
from one run (`tc-suite-author`).

## One question decides the path

**Does the coverage obligation still exist?**

**No, the requirement is dead.** Void the AC, not the test case:

```
py tools/wiki.py void-ac /stories/<id>.md#<AC-id> --by <you> --caused-by /sources/prd/<sec>.md --cause-version <n>
```

Test cases whose covers are all voided retire automatically with inherited
authority. Test cases with mixed coverage go stale for your decision. Voided
ACs render struck-through in the RTM, never as gaps.

**Yes, a new test case took over.** Retire with a successor:

```
py tools/wiki.py retire <tc-id> --by <you> --reason superseded --superseded-by <new-tc-id>
```

Refused (lint L5) if the successor's covers miss any active AC of the
retiree. The reciprocal `supersedes` is written on the successor in the same
commit.

## Coming back

```
py tools/wiki.py unretire <tc-id> --by <you>
```

The retirement record moves to an append-only history, the test case goes
stale, and regeneration recreates it under its original id. Without this
permit, generation reports the scenario as SUPPRESSED and never recreates
it.

## Hand-edit drift (lint W4)

A generated test-case file that differs from its sealed hash blocks
regeneration of that file until you choose:

```
py tools/wiki.py release <tc-id> --by <you>   # keep the edit; re-hash; origin becomes human-stated
py tools/wiki.py revert <tc-id>               # restore the sealed content
```

## Before any retirement

The agent reads the RTM (`py tools/wiki.py rtm`, then `build/rtm/matrix.md`)
and tells you what retiring leaves uncovered versus inherited. A redundancy
claim without this check is unverifiable.

## Invariants

- Files never move; there is no archive folder. `status: retired` is the
  archive.
- Retired test cases keep their ids forever and appear in the RTM's retired
  appendix with reason, successor and asserter.
