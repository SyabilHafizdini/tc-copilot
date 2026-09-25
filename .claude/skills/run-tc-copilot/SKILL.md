---
name: run-tc-copilot
description: Run and verify the tc-copilot test-case co-authoring platform — `wiki next` (what to do now), smoke harness, wiki CLI (status, lint, gate, cascade, seal, suite compile, export, ingest), and where every artifact lives. Use when asked to run/verify the platform, check project status, run the smoke harness, or export a workbook. Does NOT decide the next step (that is `tc-help`), does NOT ingest a PRD/Figma/deck (that is `tc-intake`), and does NOT author content — alignment is tc-align, test-case generation is tc-generate-sit/tc-generate-uat, suite selection is tc-suite-author.
---

# Run tc-copilot

All paths relative to the repo root (`config.yaml` lives there). The "app" is a
deterministic CLI: `tools/wiki.py` (no LLM calls, spec §11). Python via the `py`
launcher (3.14; `python` is the WindowsApps store stub — never use it).
Needs pdfplumber, openpyxl, PyYAML (already installed system-wide).

## Start here

```
py tools/wiki.py next
```

Read-only, ~1s. Prints for every story and flow: its state, the **literal next
command**, and the **skill that owns it**. Use this instead of deriving the next
step yourself from `status` + `gate` + frontmatter. `--story <id>` narrows it.
It also raises banners for a staged-but-unadopted PRD and for W4 hand-edit drift.

## Which skill?

| You want to… | Skill |
|---|---|
| not know what to do next / just arrived / resuming | **`tc-help`** |
| route files dumped in `PUT_FILES_HERE/` into `inputs/` and ingest them | `tc-intake` |
| turn PRD sections into an aligned story (ACs, rules, components) or a flow journey | `tc-align` |
| propose/confirm a coverage map, then render **SIT** test cases | `tc-generate-sit` |
| render **UAT** test cases from an asserted flow journey | `tc-generate-uat` |
| pick/filter already-generated TCs into a workbook | `tc-suite-author` |
| word or re-word TC content | `tc-style` |
| retire / void / unretire a TC, or resolve W4 drift | `tc-lifecycle` |
| handle a new PRD version (change report) | `tc-change-report` |
| propagate a human correction through the wiki | `tc-correct` |
| run the platform, check health, export, find artifacts | **this skill** |

Normal order for one story: `tc-align` → `tc-generate-sit` → `tc-suite-author`.
A flow adds `tc-generate-uat` after its member stories are coverage-confirmed.
The human-operator day-to-day loop is `docs/playbook.md`; every skill has an in-depth guide under `docs/skills/`.

## Smoke

```
py tools/smoke.py --fast     # ~24s — everything except xlsx compiles + Node graph bake
py tools/smoke.py            # full run
```

Requires a clean working tree (fails fast otherwise). Covers manifest rebuild,
index regen, lint, generation gates (story + flow), SIT/UAT byte-stability, the
two enforced fences (below), `wiki next`, rtm build, coverage diagram, golden
eval `--strict`, suite compiles, dashboard, story export, `rtm --graph`
validation, and that the repo is left clean. Also runs the opencode plugin's
`bun test` and `bun selftest.ts` when `bun` is on PATH, and prints a `[SKIP]`
line (not a failure) when it isn't — smoke never becomes bun-dependent. Ends
`SMOKE OK`.

Also runs the vendored graph viewer's `npm test` (244 tests) in the full run
when `npm` is on PATH **and** `tools/app/web/node_modules` is installed,
`[SKIP]`ping otherwise. The bundle-freshness and viewer-path unit checks run
on both paths — if either fails, rebuild with
`cd tools/app/web && npm run build:viewer && py tools/app/bundle_check.py --write`.

Rebuilding the committed bundle needs `npm ci` plus Node. Baking a graph
(`wiki --graph`) shells out to the plain `node` binary (`scripts/validate.mjs`,
`scripts/bake.mjs`) but needs no `node_modules` and no second checkout —
everything else here is pure Python.

Use `--fast` in the edit loop; run the full suite before committing.

## The CLI

```
py tools/wiki.py next [--story US-XXXX]    # what to do next (read-only)
py tools/wiki.py status                    # story table, TC counts, adopted PRD version
py tools/wiki.py lint                      # L1-L13 / W1-W6; exit 1 on any L error (~3s)
py tools/wiki.py manifest                  # rebuild manifest.json from frontmatter
py tools/wiki.py index                     # regenerate every index.md
py tools/wiki.py gate --story US-XXXX      # hard generation gate (spec §7.1)
py tools/wiki.py gate --flow <flow-stem>
py tools/wiki.py coverage --story US-XXXX [--propose] [--graph]
py tools/wiki.py cascade [--graph]         # staleness flags only; never regenerates
py tools/wiki.py impact <ref> [--json] [--graph]   # downstream impact, before you change
py tools/wiki.py seal                      # hash-seal TC files into manifest (spec P6)
py tools/wiki.py rtm [--graph]             # build/rtm/{matrix,trace,graph.json,gaps}
py tools/wiki.py suite compile sit-all [--graph]
py tools/wiki.py dashboard                 # build/status/{dashboard.json,dashboard.html}
py tools/wiki.py app [--port 8765] [--no-open]   operator app (needs FastAPI)
py tools/test_app_visual.py                visual gate: app renders + styled (needs Playwright)
py tools/wiki.py next --json               structured next-action state
py tools/wiki.py export --story US-XXXX --name xxxx-sit-r1
py tools/wiki.py triage [--apply] [--prd-version N]   # PUT_FILES_HERE/ -> inputs/
py tools/wiki.py ingest-prd | ingest-figma | ingest-decks
py tools/wiki.py diff --prd                # adopted vs staged section diff
py tools/wiki.py migrate-ids               # ONLY sanctioned tc_format change (spec §10)
py tools/wiki.py migrate-provenance [--apply]   # backfill provenance on stories predating lint L13
py tools/eval_golden.py [--strict]         # wiki vs eval/golden workbooks (SIT + UAT)
py tools/wiki.py testmodel --story US-XXXX [--propose [--force]]   # 29119-4 test model: scaffold / show + C = N/T
py tools/eval_rubric.py --story US-XXXX --round N [--pack] [--strict]   # rubric score; --pack writes judge packs
py tools/eval_rubric.py --story US-XXXX --apply-patch build/rubric/US-XXXX-rN-patch.json   # improver patch -> spec
#   outputs: build/rubric/<id>-rN-score.json, <id>-rN-gaps.md, packs/<id>-rN-{A,B,C,D}.md,
#            judgments/<id>-rN-<lens>.json (written by judge subagents), <id>-rN-delta.json
```

Rendering:

```
py tools/render_sit.py --story US-XXXX [--force]      # SIT — one shared engine
py tools/render_production_monitoring_uat.py [--force] # UAT — journey-derived
```

SIT test-case **content** is data at `tools/sit_specs/<STORY>.yaml` (named keys,
validated before anything is written). Never copy the engine to open a new
scope — write a spec. See `tc-generate-sit`.

Human-gated lifecycle & change commands (`retire`, `void-ac`, `unretire`,
`release`, `revert`, `approve-cr`, `reject-cr`) are documented in the
`tc-lifecycle` and `tc-change-report` skills.

Every mutating command auto-commits as `tc-agent <tc-agent@internal>`; append
`--no-commit` to batch several steps into one commit.

## The fences (enforced in code, not just documented)

1. **Lint before commit.** `agent_commit` runs lint and refuses on any L error.
   Override with `--allow-lint-errors` only when you are deliberately recording
   a lint-invalid wiki.
2. **The card fence.** `assert story` and `assert flow` require
   `--card <path>` naming an existing card whose scope matches; asserting stamps
   `human_response` into that card. You cannot assert without having emitted and
   presented a card.
3. **The coverage fence.** `render_sit.py` refuses while the story's
   `coverage_status` is not `confirmed`. Override
   (`--allow-unconfirmed-coverage`) is not a substitute for the human's
   confirmation.
4. **The opencode plugin** (`.opencode/plugins/tc-copilot.ts`) injects live wiki
   state and any unfinished obligations into the model's context each turn, and
   blocks a short list of unambiguous mistakes. It is a **second net** — it does
   not intercept subagent tool calls, so it never replaces the fences above.
   Inert outside a tc-copilot wiki. Tests: `cd tools/opencode && bun test`.

Beyond these: `assert story` refuses while `# Open Questions` has bullets;
`gate` refuses while the story is not `aligned`. **All of these refusals are
correct behavior, not bugs — never route around one to unblock yourself**
(spec P3).

## Where things live

- `sources/prd/*.md` — verbatim PRD sections (tables preserved as markdown)
- `stories/*.md` — ACs/rules/components as frontmatter fragments
- `tools/sit_specs/*.yaml` — SIT test-case content (the generation run-record)
- `testcases/sit/<module>/*.md`, `testcases/uat/<flow>/*.md` — generated TCs
- `manifest.json` — hashes, scenario→TC bindings, counters (never hand-edit)
- `build/` — git-ignored compiled views (inventories, cards, rtm, dashboard)

## References (load on demand)

- `references/xlsx-format.md` — the org 5-sheet SIT workbook layout, header
  block, formulas, and how to recalc-verify it via Excel COM.
- `references/graphs.md` — the RTM text views and the five scoped graph-viewer
  graphs (`rtm`, `traceability`, `coverage-X`, `cascade`, `impact-X`, `suite-X`).
- `references/gotchas.md` — the battle scars: YAML colons, frontmatter
  round-trips, byte-stability, `.gitattributes` and binaries, Excel sheet-name
  limits, openpyxl rich text, headless Edge screenshots, graph readability.

## Remaining edges (do not pretend otherwise)

- A Resolution whose prose links a discarded flow throws a W1 lint warning
  and keeps throwing it — expected residue of a discard, a warning and never
  an error (git history is the discarded flow's archive).
- SIT bindings carry no `COVMAP:` pins, so a coverage_map edit does not stale
  SIT TCs — re-render with `--force` after re-confirming coverage. See
  `references/gotchas.md`.
- Deck ingestion is verified against a synthetic pptx fixture only.
- CR classification (editorial|material) is agent work by editing the CR — the
  tooling writes `unclassified`.
- docx PRD input is not implemented (pdf and md are).

## Not this skill

- Not sure what to do next / just arrived / resuming → `tc-help`.
- Files waiting in `PUT_FILES_HERE/`, or ingesting a PRD/Figma/deck →
  `tc-intake`.
- Aligning a story or flow → `tc-align`.
- Generating SIT or UAT test cases → `tc-generate-sit` / `tc-generate-uat`.
- Selecting TCs into a suite → `tc-suite-author`.
- TC wording/format → `tc-style`.
- Retiring/voiding/unretiring a TC → `tc-lifecycle`.
- A new PRD version's change report → `tc-change-report`.
- Propagating a human correction → `tc-correct`.
