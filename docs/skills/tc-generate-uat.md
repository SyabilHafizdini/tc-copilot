# tc-generate-uat

Generates UAT test cases for one aligned flow by walking its asserted
journey: one test case per journey entry, each starting exactly where the
previous one ended.

## When to use it

- You want UAT test cases for a flow.
- A flow's journey was edited and its test cases went stale.

Not for SIT (`tc-generate-sit`), not for editing the journey or the scenario
model (`tc-align` on the flow), not for filtering existing test cases into a
workbook (`tc-suite-author`).

## Preconditions

- The flow is `aligned` and has a `journey:`. The journey is proposed and
  asserted in `tc-align`, never here.
- The flow's `test_model` (scenario model) is `confirmed`.
- Every member story is `coverage_status: confirmed`. The coverage map is
  UAT test content: each test case's element list is read from it, so a
  proposed map would bake the heuristic's mistakes into tester-facing text.

`py tools/wiki.py gate --flow <stem>` checks the first and third; the stem is
the flow's file name, not its id.

## How it runs

1. **Render the chain.** The flow gets its own run-record script, copied
   from `tools/render_production_monitoring_uat.py`. Per journey entry:
   - id from `ids.tc_format_uat` (`UAT-` prefix in the wiki; exports strip
     it);
   - `covers`: the story AC ref plus the journey ref `#JNN`, plus the flow
     branch ref where an entry realises one;
   - precondition: the previous entry's `end_state` ("Continue from TC-...:
     user is at ..."); the first entry uses the flow's entry condition;
   - expected results: the AC's Then-clause plus the element-verification
     block from the covered AC's confirmed coverage map;
   - `coverage_items`: `SC-MAIN` on every entry; an entry that realises an
     alternative scenario names that `SC-ALT-nn` too.
2. **Draft export.** Right after the first seal:

   ```
   py tools/wiki.py export --flow <stem> --name <stem>-uat --draft
   ```

   You receive the DRAFT round 0 workbook now and review it while the grade
   loop runs.
3. **Grade loop.** As in `tc-rubric`, with `--flow <id>`. The improver's
   patch applies to the run-record's wording tables, never to rendered
   files. Re-render with `--force`, re-seal, round 2.
4. **Seal and verify.** `seal`, `manifest`, `lint`. Re-render prints
   `rendered 0` unchanged. `eval_golden.py` must show 1:1 segmentation:
   journey entries equal active UAT test cases.
5. **Diff, then final export.**

   ```
   py tools/eval_rubric.py --flow <stem> --diff
   py tools/wiki.py export --flow <stem> --name <stem>-uat
   ```

   The final export refuses without a current strict score and fills the
   Change Log sheet from the diff. Use `suite compile <uat-suite>` for the
   multi-flow workbook.
6. Commit as `tc-agent`: `generate-uat(<flow>): N journey TCs`.

## Refusals and why

- No journey, or a journey touching a story still at `proposed` coverage:
  refused. Fix upstream.
- A test model with the main scenario only caps the coverage dimension at
  band 2. That is a finding about the model; surface it, do not hide it.

## Hard rules

- One test case per journey entry. Never one stuffed flow test case, never
  a step the journey does not contain.
- After any coverage re-confirmation on a member story, re-render the UAT
  scope with `--force`. The coverage map lives outside the AC fragment
  pins, so plain byte-stability would keep the old element lists.
- Superseding old-style flow test cases is a human retirement
  (`tc-lifecycle`), never automatic.
