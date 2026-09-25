# eval/golden — your project's golden test set

`tools/eval_golden.py` compares what this bundle generates against an
org-authored **golden** workbook, so you can measure the platform against
test cases a human already wrote. It is a calibration harness, not a gate.

Drop your project's own files here:

| File | What it is |
|---|---|
| `sit-v0.1.xlsx` | Golden SIT workbook (the org's hand-written SIT test cases) |
| `uat-v0.1.xlsx` | Golden UAT workbook (the org's UAT walkthrough rows) |
| `aliases.yaml`  | Optional. Records human ID renumbering, applied to golden tuples only — use it when the golden workbook numbers ACs differently from the PRD, rather than mutating wiki IDs (the PRD stays source of truth). |

The comparator is product-agnostic: golden facts are read from the workbook,
never hardcoded. With no workbooks present, `eval_golden.py` reports that and
exits 0 — including under `--strict` — so it never fails a project that has no
golden set.

A project's own golden workbooks live on that project's branch, if you want a
worked example of the format.
