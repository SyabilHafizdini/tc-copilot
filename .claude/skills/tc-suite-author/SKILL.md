---
name: tc-suite-author
description: SELECT already-generated test cases into a suite and compile it to a workbook — parse natural language into suites/<name>.yaml, resolve module/flow names, present the resolved TC-count preview, compile on confirmation. Use when asked to build, compose, filter, or export a test SUITE ("SIT regression without module X, P1 only"). Selection is not generation: it never creates, edits, or re-words a test case — if the TCs do not exist yet, that is tc-generate-sit or tc-generate-uat.
---

# tc-suite-author — NL → suite YAML

Selection is not generation (spec P7): a suite is a filter over already-
generated TCs. Compiling MUST be instant, reversible, and write only under
`build/` — verified invariant (`tools/smoke.py` checks the repo stays clean).

## Protocol

1. Parse the human's intent into the suite schema. Resolve module/flow names
   against `modules/index.md` and `flows/index.md` — fuzzy matches get
   confirmed with the human before writing ("did you mean
   `<module-stem>`?"). Misresolution must die at the preview, not in
   the export.
2. Write `suites/<name>.yaml` (see `suites/sit-vhld-p1.yaml` for the shape):
   `kind`, `include_modules`/`exclude_modules` (module file stems),
   `include_flows`/`exclude_flows`, `priorities`, `extra_include`/
   `extra_exclude` (TC IDs; exclude wins), `created_by`, `created_via:
   nl-prompt`, and the verbatim `prompt` for provenance. The YAML is the
   artifact of record; the prompt is provenance only.
3. Compile and present the resolved preview BEFORE calling it done:

   ```
   py tools/wiki.py suite compile <name>
   ```

   Output format: `suite <name>: N active, N stale (excluded), N retired ->
   build/inventory/<kind>/<name>_<timestamp>.xlsx (+ <name>-latest.xlsx)`
   (kind = the suite yaml's `kind`; a timestamped pair plus a stable
   `-latest` pair land in `build/inventory/<kind>/`). Read the counts back
   to the human ("selects 14 active TCs, all P1, one module only").
4. Human confirms → commit the YAML as tc-agent. Human corrects → edit and
   recompile; compilation is free.

## Verified behaviors

- Priority filter: a `priorities: [P1]` suite selects only the P1 subset of a
  story's active TCs — verified on a story whose 39 active TCs yielded 24.
- Stale TCs are excluded from the active list but shown in the inventory's
  stale section; retired TCs render in a separate section (spec §13.4).
- `wiki lint` W5 warns when `extra_include` names retired or nonexistent TCs.

## Not this skill

- The TCs do not exist yet → `tc-generate-sit` (story) or `tc-generate-uat`
  (flow). A suite cannot select what was never generated.
- A selected TC's wording is wrong → `tc-style` + re-render the scope; never
  hand-edit the compiled workbook.
- A selected TC should not exist at all → `tc-lifecycle` (retire/void).
- Stale TCs are being excluded and you want them back → regenerate them with
  the matching tc-generate skill; the suite is a filter, not a fixer.
