# tc-copilot — instructions for agents working in this repo

tc-copilot is a test-case co-authoring platform. **The agent proposes, the
human asserts, and the tooling enforces it.** Everything below follows from
that sentence.

## Start here

- Lost, resuming, or unsure which skill applies: invoke **`tc-help`**. It runs
  `py tools/wiki.py next` and names the one next command and the skill that
  owns it. Never derive the next step by hand.
- One skill per job. The routing table is in `docs/skills.md`; each skill has an
  in-depth guide under `docs/skills/`. Load `tc-style` alongside any skill that
  writes test-case text, and `tc-rubric` alongside any skill that generates.

## Rules that never bend

1. **Refusals are the product.** `gate`, `assert --card`, the coverage fence,
   the test-model fence, `--strict` and every lint L-error refuse for a reason.
   Fix the cause upstream (align, answer the card, confirm coverage). Never add
   a flag, edit a tool, or move a file to get past one.
2. **Only a human asserts.** Never write `status: aligned`, `asserted_by`,
   `coverage_status: confirmed` or `test_model.status: confirmed` yourself.
   Emit the card, present it, and run `wiki assert ... --by <human> --card
   <card>` only at the human's explicit instruction.
3. **Never hand-edit generated files.** `testcases/**`, `manifest.json`,
   `index.md` files and `build/**` are compiled views. Change the source
   (story, spec, glossary) and re-render; a spec-only edit needs
   `render_sit.py --force`.
4. **`tools/` is LLM-free.** Every command is deterministic and re-runnable.
   LLM judgement enters only through files the tools validate (cards,
   sit_specs, judge verdicts, improver patches).
5. **Commit as `tc-agent`.** Mutating `wiki` commands auto-commit as
   `tc-agent <tc-agent@internal>`; use the same identity for manual commits of
   wiki content. No AI attribution lines.

## Working conventions

- Python is the `py` launcher on Windows (`py tools/wiki.py ...`). Dependencies:
  `pdfplumber`, `openpyxl`, `PyYAML` (plus FastAPI for the operator app).
- Read and write concept files through `read_concept` / `write_concept` in
  `tools/wiki.py`, never `str.replace` on raw YAML.
- Before calling any work done: `py tools/wiki.py lint` (0 errors) and
  `py tools/smoke.py --fast` (`SMOKE OK`; needs a clean tree).
- `master` is the content-free platform base. Project content lives on a
  project branch. Platform fixes land on `master` and are merged or
  cherry-picked onto project branches, never the other way round.
- `standards/` is ignored except `standards/rubric/`. Never commit the ISO
  standard or any other copyrighted reference document.

## Where things are

| Path | What |
|---|---|
| `README.md` | Three-step start for humans; `docs/skills.md` holds the loop and the routing table |
| `docs/` | Playbook, CLI reference, one in-depth guide per skill |
| `.claude/skills/` | The skills themselves (the protocol the agent follows) |
| `tools/` | The deterministic CLI and render engines |
| `standards/rubric/` | The versioned ISO/IEC/IEEE 29119-4 rubric |
| `config.yaml` | Project identity, id formats, export headers, rubric settings |
