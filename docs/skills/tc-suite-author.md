# tc-suite-author

Selects already-generated test cases into a suite and compiles it to the org
workbook. Selection is a filter, never generation: instant, reversible, and
it writes only under `build/`.

## When to use it

- "SIT regression without module X, P1 only."
- Export a subset of test cases for a release or a test run.
- Exclude test cases from one run without retiring them.

Not when the test cases do not exist yet (`tc-generate-sit` /
`tc-generate-uat`), not for re-wording (`tc-style`), not for removing a test
case permanently (`tc-lifecycle`).

## How it runs

1. Your request is parsed into the suite schema. Module and flow names are
   resolved against `modules/index.md` and `flows/index.md`; a fuzzy match
   is confirmed with you before anything is written.
2. `suites/<name>.yaml` is written: `kind` (sit or uat),
   `include_modules` / `exclude_modules`, `include_flows` / `exclude_flows`,
   `priorities`, `extra_include` / `extra_exclude` (test-case ids; exclude
   wins), `created_by`, `created_via: nl-prompt`, and your verbatim prompt
   for provenance. The YAML is the artifact of record.
3. Compile and preview before calling it done:
   ```
   py tools/wiki.py suite compile <name>
   ```
   Output: `suite <name>: N active, N stale (excluded), N retired ->
   build/inventory/<kind>/<name>_<timestamp>.xlsx (+ <name>-latest.xlsx)`.
   The counts are read back to you.
4. You confirm; the YAML is committed as `tc-agent`. You correct; it is
   edited and recompiled. Compilation is free.

## What you get

The org workbook: for SIT, five sheets in the house lettering (contents,
document references, test cases with Test Case ID / Scenario / Test Steps /
Field-Values / Expected Results, statistics, change log). Display ids carry
the `TC-` prefix. Stale test cases are excluded from the active list but
shown in the stale section; retired ones in their own section.

## Notes

- Lint W5 warns when `extra_include` names a retired or nonexistent test
  case.
- Stale test cases come back only by regenerating them with the matching
  generate skill. The suite is a filter, not a fixer.
- The rubric's `--strict` gate is the quality check before an export; the
  suite does not re-check it.
