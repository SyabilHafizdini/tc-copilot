# run-tc-copilot

Runs and verifies the platform: the next-action advisor, the smoke harness,
the CLI, exports, and where every artifact lives. It decides nothing about
content; that is the other skills.

## When to use it

- Run or verify the platform, check project status.
- Run the smoke harness before committing.
- Export a workbook or find an artifact.

Not for deciding the next step (`tc-help`), ingesting (`tc-intake`), or
authoring anything.

## Start here

```
py tools/wiki.py next
```

Read-only. For every story and flow: its state, the literal next command,
and the skill that owns it. Banners flag a staged PRD, an unanswered card,
hand-edit drift, and files in `PUT_FILES_HERE/`.

## Smoke

```
py tools/smoke.py --fast     # everything except xlsx compiles and the graph bake
py tools/smoke.py            # full run
```

Needs a clean working tree. Covers manifest rebuild, index regeneration,
lint, the generation gates, SIT and UAT byte-stability, the enforced fences,
`wiki next`, the RTM, the coverage diagram, the golden eval, the rubric unit
tests, suite compiles, the dashboard, story export, graph validation, the
operator app's HTTP surface and visual gate, and that the repo is left
clean. Ends `SMOKE OK`. Steps whose subject is absent print `[SKIP]`; steps
needing `bun`, `npm` or Playwright skip when those are not installed.

## The fences

Enforced in code, not just documented:

1. **Lint before commit.** Every auto-commit runs lint and refuses on an L
   error. `--allow-lint-errors` exists only to deliberately record a
   lint-invalid wiki.
2. **The card fence.** `assert story|flow` needs `--card <path>` naming an
   existing card for that scope; asserting stamps the human's answer into it.
3. **The coverage fence.** `render_sit.py` refuses while coverage is
   `proposed`.
4. **The test-model fence.** `eval_rubric.py` refuses a `proposed` or empty
   test model, and `--strict` refuses a PARTIAL score.
5. **The opencode plugin** (`.opencode/plugins/tc-copilot.ts`) injects live
   wiki state each turn and blocks a short list of unambiguous mistakes. A
   second net, never a replacement for the fences above.

Refusals are correct behaviour. Never route around one.

## Where things live

| Path | Contents |
|---|---|
| `sources/prd/*.md` | Verbatim PRD sections |
| `stories/*.md` | ACs, rules, components, coverage map, test model as frontmatter |
| `tools/sit_specs/*.yaml` | SIT test-case content |
| `testcases/sit/`, `testcases/uat/` | Rendered test cases |
| `manifest.json` | Hashes, bindings, counters |
| `build/cards/` | Alignment, coverage and triage cards |
| `build/rtm/` | Matrix, trace, graph, gaps |
| `build/rubric/` | Scores, gap reports, judge packs and verdicts |
| `build/inventory/` | Exported workbooks |
| `build/status/` | Dashboard |

The full command list is in [docs/cli.md](../cli.md).

## References inside the skill

- `references/xlsx-format.md`: the org workbook layout, header block,
  formulas, and how to recalc-verify it via Excel.
- `references/graphs.md`: the RTM text views and the scoped graph-viewer
  graphs.
- `references/gotchas.md`: YAML colons, frontmatter round-trips,
  byte-stability, `.gitattributes` and binaries, Excel sheet-name limits,
  rich text, headless screenshots.

## Known edges

- A Resolution whose prose links a discarded flow keeps a W1 warning; git
  history is the archive.
- SIT bindings carry no coverage-map pins, so a coverage-map edit does not
  stale SIT test cases. Re-render with `--force` after re-confirming.
- Deck ingestion is verified against a synthetic fixture only.
- docx PRD input is not implemented; pdf and md are.
