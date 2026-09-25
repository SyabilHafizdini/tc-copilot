# tc-help

**Start here when you do not know what to do next.** It reads the project's
real state and tells you the one next command and the skill that owns it. It
never writes anything.

## When to use it

- You just arrived, or are resuming after a break.
- You are asking "what now", "where were we", "which skill do I use".
- You have a goal in your own words ("I want to export a workbook") and want
  it mapped to the right skill without guessing.

## What it does

1. Runs `py tools/wiki.py next --json`, one read-only call.
2. Reports, in this order:
   - **Where you are**: the project phase (`n/3`) and story and test-case
     counts.
   - **Blockers first**: every banner. A staged PRD awaiting approval, a card
     awaiting an answer, hand-edit drift, files still in `PUT_FILES_HERE/`.
     Banners block everything after them.
   - **The one next thing**: the first row's state, its literal command, and
     the owning skill. The remaining rows follow, one line each, so you can
     pick a different scope.
3. Offers to invoke the owning skill. It does not invoke one without a yes.

Everything it says is computed by the CLI. If the CLI did not say it, the
skill does not say it.

## Goal routing

| You say | It routes to |
|---|---|
| "I dumped some files", "ingest this PRD" | `tc-intake` |
| "align this story", "the AC is wrong", "no PRD" | `tc-align` |
| "SIT test cases", "coverage map", "component gap" | `tc-generate-sit` |
| "UAT test cases", "walk the journey" | `tc-generate-uat` |
| "grade / score these test cases", "rubric" | `tc-evaluate`, or `tc-rubric` while generating |
| "export", "workbook", "regression suite" | `tc-suite-author` |
| "retire this TC", "someone hand-edited a TC" | `tc-lifecycle` |
| "new PRD version", "what changed" | `tc-change-report` |
| "that rule is wrong" (no new PRD) | `tc-correct` |
| "run the platform", "is it healthy" | `run-tc-copilot` |
| "re-word this test case" | `tc-style` |

If the state contradicts the request, for example SIT test cases on a story
still in `draft`, it says so and names the blocking step. It never routes
around a gate.

## What the states mean

`wiki next` walks each story through its preconditions and stops at the
first unmet one:

1. `draft` or `in-alignment` → align it (`tc-align`)
2. `aligned` with open questions → close them (`tc-align`)
3. coverage not confirmed → propose the map (`tc-generate-sit` step 2)
4. test model not confirmed → propose the model (`tc-generate-sit` step 2)
5. stale or zero test cases → render (`tc-generate-sit`)
6. rendered but not graded → grade loop (`tc-rubric`)
7. graded → export (`tc-suite-author`)

## Related

- `run-tc-copilot` for the platform's health, CLI and artifact locations.
- Every other skill for the actual work; `tc-help` only routes.
