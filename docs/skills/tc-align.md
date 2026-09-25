# tc-align

The alignment ("grill-me") session. It turns PRD sections and a Figma page
into an asserted story: acceptance criteria, business rules, component table,
glossary proposals, and one Resolution per answered question. For a flow, it
produces the asserted journey and scenario model. It produces the source of
truth, never test cases.

## When to use it

- A story or flow is `draft`, `in-alignment` or `needs-review`.
- You want to review what the agent understood from the PRD.
- An AC, rule or journey is wrong and needs re-asserting.
- There is no PRD, or the PRD describes behaviour without numbering ACs.

Not for corrections to already-asserted content (`tc-correct`) or a new PRD
version (`tc-change-report` first).

## Three ways in

The branch is chosen by what the story's source looks like, and each
declares a `provenance` that lint L13 enforces.

| Source situation | Branch | provenance | Where the ACs come from |
|---|---|---|---|
| PRD numbers its ACs | Phase A | `prd-verbatim` | The PRD's own words under its own numbers |
| No source document | Phase A′ | `human-stated` | You are interrogated through a fixed checklist; each `HS-NN` AC has a Resolution holding your words verbatim |
| PRD describes behaviour in prose only | Phase A″ | `prd-interpreted` | The agent authors falsifiable ACs from the prose; each has a Resolution recording your confirmation of the reading |

A story with numbered ACs always takes Phase A. Paraphrasing numbered ACs is
a downgrade in evidence. Relabelling an interpreted story `prd-verbatim` to
skip the Resolutions is the one move that silently degrades the evidence
chain; lint cannot detect it, so it is forbidden by protocol.

## How a session runs

**Prepare (no human turn).** The agent reads the story, every cited PRD
section, the Figma page image, and the glossary. It rewrites the story:
summary, ACs, business rules (`BR-<story>-NN`), components (`CMP-<story>-NN`,
names verbatim from the PRD), proposed glossary terms, and `# Open
Questions`, each with a proposed answer and source citations.
Cross-section contradictions are a mandatory output.

**Interrogate and close.** Manifest and lint run as a gate. The proposal is
committed as `tc-agent`. The agent emits the alignment card
`build/cards/session-<story>-NNN.json` with four zones: what you said, what
it understood, what it changed, what this affects, plus the open questions.

**You answer the card.**

- **Assert**: each adopted answer becomes a Resolution under your name; the
  story's open questions are emptied; `py tools/wiki.py assert story <id>
  --by <you> --card <card>` runs; `gate` prints `GATE OPEN`.
- **Revise**: say which answer is wrong; the agent loops with the delta.
- **Discard**: the session's commits are reverted.

## Flows

A flow session ends with a proposed `journey:` (ordered entries `J01..JNN`,
each a story AC ref plus the end state it leaves the user in) and the flow's
scenario model: `SC-MAIN` over the journey plus one `role: alternative` item
per abnormal, exception or error path the ACs imply. Both are confirmed by
the same assert on the card. A flow whose model has only the main scenario is
graded INCOMPLETE later, so the alternatives are part of alignment.

`assert flow` refuses while any member story is not aligned.

## Refusals and why

- `assert story` refuses while `# Open Questions` has bullets. Deferred
  questions rot; answer or de-scope.
- `assert` refuses without `--card` naming the card you were shown.
- `gate` refuses a story with no acceptance criteria. Phase A′ exists so that
  never happens when generation is asked for.

## Known limitation

A `human-stated` story pins no source, so a later PRD ingest can never stale
it. If a PRD eventually covers that scope, re-align deliberately.

## Related

- `tc-generate-sit` and `tc-generate-uat` consume what this produces.
- `tc-correct` for corrections after assertion.
