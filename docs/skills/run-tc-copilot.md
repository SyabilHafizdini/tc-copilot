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
and the skill that owns it. Banners flag a staged PRD (one per PRD, naming it), an unanswered card,
hand-edit drift, and files in `PUT_FILES_HERE/`.

`py tools/wiki.py migrate-prds [--id <id> --title "<title>"]` is a one-time,
one-way conversion of a project written before the PRD registry. The agent
proposes it, asks you for the PRD id and title (permanent, never inferred from
a file name), and runs it only at your explicit instruction. Its refusals are
fixed upstream, never bypassed.

On a schema-1 project every command except `migrate-prds`, `status` and `lint`
refuses and names `migrate-prds`; so do `render_sit.py` and `render_uat.py`.
`status` says the manifest is schema 1 and `lint` warns W10. `tc edit` makes the
refusal itself, after it has consumed its text file and before it writes
anything. `app` still opens (its views only read) and shows a migration notice
on every page; every action it runs is refused the same way.
`eval_rubric.py --apply-patch` refuses too (scoring does not).

`py tools/wiki.py tc edit <id> --field <field> --from <path> --by <you>` is
human-gated too. It is your own edit of one field of one test case: the agent
runs it from the command line only when you dictate the exact text and tell it
to save that text under your name; the `--from` file holds your words
verbatim. The agent never uses it for wording it composed: it rewords in the
spec and re-renders under its own commit (`tc-style`). The command edits the
spec, never a `testcases/` file, and never a confidence level or remark. It
refuses `--allow-lint-errors` and a `--by` that is empty, multi-line or a
flag. Rewording a part you had confirmed returns that part to its authored
level on the render, and the output, the log and the commit say so. In the
operator app it is the Save button of the review panel on the Test Cases page.

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
| `sources/prd/<prd-id>/*.md` | Verbatim PRD sections, one directory per PRD |
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
- PRD input is pdf, docx or md. A docx needs `python-docx` and Word heading
  styles on its section titles; one with no headings is refused.
