# CLI reference

Everything under `tools/` is deterministic and LLM-free. Python is the `py`
launcher. Every mutating `wiki` command auto-commits as `tc-agent`; add
`--no-commit` to batch steps. Commands marked **human** require `--by <name>`
and run only at a human's instruction.

## Orientation

```
py tools/wiki.py next [--story <id>] [--json]   # what to do now + owning skill (read-only)
py tools/wiki.py status                          # story table, TC counts, adopted PRD version
py tools/wiki.py dashboard                       # build/status/dashboard.{json,html}
py tools/wiki.py app [--port 8765]               # operator app (needs FastAPI)
py tools/smoke.py [--fast]                       # health check; needs a clean tree
```

## Intake

```
py tools/wiki.py triage [--apply] [--prd-version N] [--card <card>]
py tools/wiki.py ingest-prd | ingest-figma | ingest-decks | ingest-reference
py tools/wiki.py diff --prd                      # adopted vs staged PRD sections
py tools/wiki.py approve-cr CR-NNN --by <you>    # human
py tools/wiki.py reject-cr  CR-NNN --by <you>    # human
```

## Wiki integrity

```
py tools/wiki.py lint          # L1-L14 errors, W1-W7 warnings; exit 1 on any L
py tools/wiki.py manifest      # rebuild manifest.json from frontmatter
py tools/wiki.py index         # regenerate every index.md
py tools/wiki.py cascade       # staleness flags; never regenerates
py tools/wiki.py impact <ref>  # downstream impact of a concept or fragment
py tools/wiki.py rtm [--graph] # build/rtm/{matrix,trace,graph.json,gaps}
```

## Alignment and gates

```
py tools/wiki.py assert story|flow <id> --by <you> --card <card>   # human
py tools/wiki.py assert term|figma <id> --by <you>                 # human
py tools/wiki.py card revise|discard <card> --by <you> [--answer q=v]
py tools/wiki.py gate --story <id> | --flow <stem>                 # GATE OPEN or the reason
```

## Coverage and the test model

```
py tools/wiki.py coverage --story <id> [--propose] [--graph]
py tools/wiki.py testmodel --story <id> | --flow <id> [--propose [--force]]
```

`coverage --propose` writes a heuristic component-to-AC map at
`coverage_status: proposed`. `testmodel --propose` scaffolds the 29119-4 test
model at `status: proposed`. Both are confirmed by `assert --card`, never by
hand. `testmodel` without `--propose` shows the model and per-technique
`C = N / T`.

## Generation

```
py tools/render_sit.py --story <id> [--force]      # SIT from tools/sit_specs/<id>.yaml
py tools/render_<flow>_uat.py [--force]            # UAT from the flow's journey
py tools/wiki.py seal                               # hash-seal rendered TCs
```

`--force` re-renders even when the pinned AC fragments are unchanged. It is
required after a spec-only edit, such as adding `coverage_items` or applying
an improver patch.

## Grading (ISO/IEC/IEEE 29119-4 rubric)

```
py tools/eval_rubric.py --story <id> --round N [--pack]        # score, gaps, judge packs (+ <id>-rN-packed.json)
py tools/eval_rubric.py --story <id> --apply-patch <patch.json> # improver patch -> spec
py tools/eval_rubric.py --story <id> --round N --strict         # gate on config threshold; refuses if the set moved since --pack
py tools/eval_rubric.py --story <id> --diff   # draft snapshot -> current sealed set: build/rubric/<id>-changes.{md,json}
py tools/eval_golden.py [--strict]                              # compare with eval/golden
```

Outputs under `build/rubric/`: `<id>-rN-score.json`, `<id>-rN-gaps.md`,
`packs/<id>-rN-{A,B,C,D}.md`, `judgments/<id>-rN-<lens>.json` (written by the
judge subagents), `<id>-rN-delta.json`, `<id>-rN-packed.json`, `<id>-draft.json`,
`<id>-changes.md/json`, `judgments/<id>-rN-<L>.carried.json`.

## Suites and export

```
py tools/wiki.py export --story <id> [--name <n>] --draft   # DRAFT r0 workbook + snapshot, right after seal; refuses a graded set
py tools/wiki.py export --story <id> [--name <n>]           # final: refuses without a current strict score; fills Change Log
py tools/wiki.py export --flow <stem> [--name <n>] [--draft]
py tools/wiki.py suite compile <name>              # from suites/<name>.yaml
```

Workbooks land in `build/inventory/<kind>/` as a timestamped file plus a
stable `-latest` copy.

## Lifecycle (all human)

```
py tools/wiki.py retire <tc-id> --by <you> --reason superseded --superseded-by <tc-id>
py tools/wiki.py void-ac /stories/<id>.md#<AC> --by <you> --caused-by <src> --cause-version <n>
py tools/wiki.py unretire <tc-id> --by <you>
py tools/wiki.py release <tc-id> --by <you>        # keep a hand-edit (W4)
py tools/wiki.py revert <tc-id>                    # discard a hand-edit
```

## Migrations

```
py tools/wiki.py migrate-ids                       # the only sanctioned tc_format change
py tools/wiki.py migrate-provenance [--apply]      # backfill provenance (lint L13)
```

## Where things live

| Path | Contents |
|---|---|
| `sources/prd/`, `sources/figma/` | Verbatim ingested sections and pages |
| `stories/`, `flows/`, `glossary/`, `resolutions/` | The asserted wiki |
| `tools/sit_specs/<id>.yaml` | SIT test-case content, data only |
| `testcases/sit/`, `testcases/uat/` | Rendered test cases (never hand-edited) |
| `suites/*.yaml` | Suite definitions |
| `manifest.json` | Hashes, bindings, counters (never hand-edited) |
| `build/` | Git-ignored compiled views: cards, rtm, rubric, inventories |
