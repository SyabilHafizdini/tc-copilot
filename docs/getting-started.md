# Getting started

From an empty base to the first exported workbook.

## 1. Branch and configure

```
git switch -c <project> master
py -m pip install -r requirements.txt
```

Open `config.yaml` and replace every `CHANGE ME` / `CHANGE-ME` value:

| Key | What it is |
|---|---|
| `project.name`, `project.code` | Identity used in ids and headers |
| `ids.tc_format` | Test-case id template. **Freezes at first generation**; changing it later requires `migrate-ids` |
| `export.*` | Header block of the org SIT workbook |
| `provenance.human` | Your name. It signs every assertion |
| `rubric.threshold` | The `--strict` pass mark for the 29119-4 grade (default 70) |

## 2. Intake

Drop everything into `PUT_FILES_HERE/`: the PRD (pdf or md), Figma page PNGs,
decks. Then:

```
py tools/wiki.py triage           # dry run: where would each file go?
py tools/wiki.py triage --apply   # move them
py tools/wiki.py ingest-prd
py tools/wiki.py ingest-figma     # if you have Figma pages
py tools/wiki.py ingest-decks     # if you have decks
```

Triage refuses a Figma file whose name would become a bad permanent id, and
asks whether an ambiguous document is the PRD or reference material. Those
refusals are answered on a card with the agent (`tc-intake`), never by moving
files around them.

## 3. Ask what to do next

```
py tools/wiki.py next
```

This prints, for every story and flow, its state, the literal next command
and the skill that owns it. The agent's `tc-help` skill reads the same output.
Use it whenever you are unsure.

## 4. Align a story

Tell the agent to align a story (`tc-align`). It drafts acceptance criteria,
business rules and a component table from the PRD sections, brings you
questions with proposed answers, and ends with a card. You answer the card:
assert, revise or discard. Assertion is what opens the generation gate.

No PRD? No numbered ACs? `tc-align` has a branch for each case; see its guide.

## 5. Generate and grade

Ask for SIT test cases (`tc-generate-sit`). Before rendering anything the agent
brings one coverage card carrying the component-to-AC map and the 29119-4
test model. You confirm it. Then it renders, seals, and runs one grade round:
four judge lenses, a gap report, one improve pass, a second score. The strict
gate refuses export below the threshold.

For a flow, `tc-align` asserts the journey and scenario model first, then
`tc-generate-uat` renders one test case per journey step.

## 6. Export

```
py tools/wiki.py export --story <id> --name <release>
```

or compose a suite in plain language (`tc-suite-author`) and compile it:

```
py tools/wiki.py suite compile <name>
```

Workbooks land under `build/inventory/`.

## Verify the platform at any time

```
py tools/wiki.py lint         # 0 errors is the gate
py tools/smoke.py --fast      # SMOKE OK; needs a clean working tree
py tools/wiki.py dashboard    # build/status/dashboard.html
```

On the empty base, steps whose subject does not exist yet print `[SKIP]`.
The seal fence and the UAT coverage fence cannot be exercised until a project
has content; smoke says `NOT VERIFIED in this bundle` for those.
