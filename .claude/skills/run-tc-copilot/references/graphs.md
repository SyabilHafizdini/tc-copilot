# graphs — run-tc-copilot reference

Loaded on demand from `.claude/skills/run-tc-copilot/SKILL.md`. All paths
relative to the repo root.

## Traceability (RTM + five scoped graphs)

`py tools/wiki.py rtm` writes the text views into `build/rtm/`
(`matrix.md`, `trace.md`, `graph.json`, `gaps.md`), all deterministic and
LLM-free.

- `matrix.md` — **AC -> TC** coverage matrix per story, plus per-component
  coverage and a retired-TC appendix. Read this to answer "is this AC tested?"
- `trace.md` — **TC -> source** chain, one row per TC:
  `TC | status | covers AC | story | PRD section(s) | Figma`. The reverse read
  of matrix.md; answers "what requirement is this test case for?" ACs carry no
  per-AC source refs in frontmatter, so PRD provenance is story-level (every
  a TC lists every one of that story's sections — that is the real data, not
  a bug).
- `gaps.md` — uncovered ACs, orphan TCs, version-pinned TCs, component gaps.
- `graph.json` — legacy D3 contract, kept for compatibility.

Five commands can each emit a **purpose-built** graph-viewer graph. Each
writes scoped viewer JSON to `build/rtm/graphs/<scope>.json` on every run
(pure Python, <1s); add `--graph` to also bake a standalone HTML (~10s of
Node, via `C:\Apps\graph-viewer`):

| Command | Graph answers | Output stem |
|---|---|---|
| `wiki rtm --graph` | the clean PRD→Story→AC→TC tree + the full audit graph | `graphs/traceability`, `graphs/rtm` |
| `wiki coverage --story X --graph` | what does this story cover (GAP/out-of-scope coloured) | `graphs/coverage-X` |
| `wiki cascade --graph` | the PRD moved — what must I re-verify (emitted only if something flags) | `graphs/cascade` |
| `wiki impact <ref> --graph` | if I change this, what breaks — before I change it | `graphs/impact-<ref>` |
| `wiki suite compile X --graph` | the shape of this regression run | `graphs/suite-X` |

`wiki rtm` emits **two** graphs:

- `graphs/traceability` — the clean **PRD → Story → AC → Test Case** hierarchy.
  Each story is anchored to its module's top-level PRD section (one root per
  module), so it reads as a real tree, not a 44-subsection fan-in. Carries an
  About-panel description and three preset lenses (Full chain / Coverage /
  Requirements). **Open it and switch VIEW to Indented** — that view lists the
  chain as a collapsible outline and is the clearest way to read coverage.
- `graphs/rtm` — the **full** audit graph (272 nodes): adds BusinessRule and
  Resolution nodes so `verifies_rules` (TC→BR) and `resolves`
  (Resolution→AC/BR/Term) render. Opens focused via its default
  "Traceability spine" preset; other presets (Business rules, Coverage map,
  Resolutions, Everything) reveal one edge family at a time. Best in Force /
  Arc / Matrix.

Open a baked graph:

```powershell
py tools/wiki.py rtm --graph --no-commit
Start-Process build\rtm\graphs\traceability.html   # then click VIEW → Indented
```

### Impact analysis — `wiki impact <ref>`

Answers "if I change this, what needs review?" **before** the change, using only
existing links + manifest pins. Read-only, LLM-free, no commit. `<ref>` is a
concept or fragment: `US-XXXX`, `stories/US-XXXX#BR-XXXX-04`,
`sources/prd/4-1-1-1` (or its id `prd#4-1-1-1`), `stories/US-XXXX#1.1.3.1.1-AC19`.

It walks dependency edges backwards (covers, verifies_rules, derived_from,
uses_terms, defined_in, journey) plus the manifest's `fragment_pins`/
`source_pins`, and tags each reached node with its **cascade verdict** — the
honest split between what the deterministic machinery guarantees to catch and
what a human must check:

- `cascade: stale` — a TC pinned the changed fragment; `cascade` WILL stale it.
- `cascade: needs-review` — a story pinned the changed source; `cascade` WILL flag it.
- `downstream` — reachable but NOT auto-flagged (the link is coarser than a hash
  pin — e.g. a PRD-section edit reaches every AC of the story, but cascade stops
  at the story). A human judges whether the edit actually touches these.
- `UNPINNED` — a TC references the target via covers/verifies_rules but never
  pinned it: a drift blind spot cascade misses. Latent on clean data (every
  covers/verifies edge is currently pinned); fires if a pin goes missing.

Verified on a real run: `impact stories/US-XXXX#BR-XXXX-04` → 3 TCs, all
`cascade: stale` (matches their pins exactly); `impact sources/prd/4-1-1-1` →
the pinning story `needs-review`, 0 TCs auto-flagged (correct: a source change
never directly stales a TC). Note `--json` for agent consumption. Impl:
`tools/wiki_impact.py`, reads frontmatter + manifest only. It reports links that
EXIST; it cannot infer a governance edge nobody authored (a TC that exercises a
rule but never declared `verifies_rules` is invisible to it — that gap is
authoring discipline, not a query bug).

