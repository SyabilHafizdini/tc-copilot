---
name: tc-align
description: Run a grill-me alignment session on a user story or flow — read PRD sections + Figma, draft the story (ACs, business rules, component table) or the flow journey, propose glossary terms, surface ambiguities WITH proposed answers, emit the alignment card, and gate on human assertion. Also handles the NO-PRD / source-less case — no `derived_from`, no acceptance criteria — where the human is interrogated directly and stands in as the source document, and the PRD-prose case — a `derived_from` PRD that describes behaviour without numbering ACs — where ACs are authored from that prose and confirmed by the human. Use when asked to align a story or flow, prepare a story for test generation, review PRD understanding, fix a wrong AC/rule/journey, or when there is no PRD/no acceptance criteria at all. Produces the ASSERTED SOURCE OF TRUTH, never test cases — generation is tc-generate-sit/tc-generate-uat.
---

# tc-align — alignment ("grill-me") session

One story per session. A completed session leaves three artifacts whose
shape you must match: the story file (`stories/<id>.md`), one Resolution per
adopted answer (`resolutions/R-<story>-NN.md`), and the session card
(`build/cards/session-<story>-NNN.json`). If this project already has an
aligned story, read its three artifacts first and imitate them exactly.

Three PREPARE branches, chosen by what the story's source looks like — pick
one, they are mutually exclusive:

| Branch | When | provenance |
| --- | --- | --- |
| Phase A | PRD states numbered ACs | `prd-verbatim` |
| Phase A′ | no source document at all | `human-stated` |
| Phase A″ | PRD describes behaviour in prose, numbers no ACs | `prd-interpreted` |

## Phase A — PREPARE (no human turn)

1. `py tools/wiki.py status` — pick/confirm the story (human's choice wins).
2. Read, in this order: the story file, every `derived_from` PRD section
   (verbatim bodies — they are faithful transcriptions), the `illustrated_by`
   Figma page **png** (view the image, then write/refresh the
   `# Visual Description` body of the Figma concept, noting PRD/mock
   discrepancies), the full current glossary (`glossary/index.md` then files).
3. Rewrite the story: `# Summary` (short falsifiable statements),
   `acceptance_criteria` (IDs = the PRD's own AC numbers, e.g.
   `1.1.3.1.1-AC5`; text = PRD verbatim minus line-wrap artifacts),
   `business_rules` (BR-<story>-NN), `components` (CMP-<story>-NN — names
   VERBATIM from the PRD Field column; UI components never go in the
   glossary). Set `provenance: prd-verbatim` and `status: in-alignment`.
4. Propose glossary terms (domain terms only) at `status: proposed`,
   `origin: agent-proposed`. Scan for alias collisions against existing terms
   first — add aliases, never duplicates (lint L7 territory).
5. Write `# Open Questions` as bullets, each WITH a proposed answer and inline
   source citations. Cross-section contradictions are mandatory outputs — a
   real catch from an early run was one PRD term defined with `≥` in one
   numbered item and `<` in two others, three sections apart.

## Phase A′ — PREPARE when there is NO source document

Take this branch when the story has no `derived_from` and no
`acceptance_criteria` — a screen, feature, or fix the human wants tested
with no PRD behind it. **The human is the source document**, so you
interrogate instead of read. Only how the draft is obtained changes; step 7
below rejoins Phase A at its step 5 (Open Questions), and Phase B/C after
that is unchanged.

1. Ask the human what they want tested, in their words. Do not draft yet.
2. Walk this checklist ONCE, in order, batching what you can. It is fixed so
   the elicitation is repeatable rather than dependent on your inspiration:
   - **actor + entry point** — who does this, from where
   - **inputs** — each field, its valid range, and what invalid looks like
   - **expected outputs** — what the user sees/gets when it works
   - **states and transitions** — what changes, and what it changes to
   - **errors and edge cases** — empty, maximum, concurrent, permission-denied
   - **permissions** — which roles may and may not
   - **data preconditions** — what must exist before the test can run
3. Draft `acceptance_criteria` as a list of mappings, one per elicited fact:
   `{id: HS-01, text: "..."}`, `{id: HS-02, text: "..."}`, … A bare string
   entry is a lint error (L13), not a shortcut — the `id` is what a
   Resolution's `resolves:` ref has to target. Each `text` is a single
   falsifiable statement in the human's own vocabulary — never invented
   behaviour, never a detail they did not state. Where you must assume, it
   becomes an Open Question, not an AC.
4. As each `HS-NN` AC is drafted, immediately write its Resolution
   (`resolutions/R-<story>-NN.md`): `origin: agent-proposed`,
   `status: proposed` (not `asserted` yet — step 12 flips it alongside the
   story), `resolves:` pointing at `/stories/<id>.md#HS-NN`, and
   `# Human Statement` carrying the human's own words verbatim from steps
   1-2 — never your paraphrase. Do this AC-by-AC, not as a batch at the end:
   a `HS-NN` with no Resolution file behind it is an L13 error, and Phase
   B/C step 6 runs `lint` as a pass/fail gate.
5. Set `provenance: human-stated` and `status: in-alignment`. Do NOT write
   `derived_from` or `source_pins` — there is no source to pin, and do NOT
   write a `derived_from` pointing at a real PRD fragment the story does not
   actually come from, however loosely related, to make the ACs look
   PRD-sourced. There is no `derived_from` exemption in L13 — it requires
   `derived_from` on `prd-verbatim` and `prd-interpreted` stories and
   forbids it on `human-stated` ones, but it cannot tell a genuine citation
   from an invented one. The real remaining hole is mislabelling: calling an
   interpreted or invented story `prd-verbatim` instead. W6 checks a
   `prd-verbatim` AC's word-token overlap against the sections it cites, but
   it only warns and never blocks, so a confident mislabel still passes
   lint. If the story is source-less, it stays source-less and
   `human-stated`.
6. Write `business_rules` and `components` only where the human stated them.
   An empty component table is honest; a guessed one is not.
7. Before moving on, confirm every `HS-NN` AC drafted in step 3 has the
   Resolution from step 4 pointing back at it. **A Phase A′ story is not
   lint-clean until this holds** — Phase B/C step 6 runs `lint` as a real
   pass/fail gate, and a Resolution missing at that point fails on L13 with
   nothing telling you this was expected; do not treat that as a surprise.
   Then continue at step 5 of Phase A (Open Questions), and Phase B/C after
   that is unchanged.

**On "Assert", additionally:** every `HS-NN` AC's Resolution
(`resolutions/R-<story>-NN.md`, already written at Phase A′ step 4) flips
from `status: proposed` to `status: asserted` alongside the story — it is
not written fresh here. This is enforced by **lint L13**, which applies to
every User Story, not just source-less ones, and errors on any of: a story
with no `provenance` declared, or a value outside `prd-verbatim` /
`prd-interpreted` / `human-stated`; a `human-stated` story that also
carries `derived_from` (a story with a source is not human-stated); a
`prd-verbatim` or `prd-interpreted` story with no `derived_from`; an AC
entry that is not a mapping, or is a mapping with no `id` (checked
regardless of provenance, not just for `human-stated` stories); or — for
`prd-interpreted` and `human-stated` stories only — an AC `id` with no
Resolution pointing back at it. That last check is the fence that keeps an
invented AC from passing as a stated one — never route around it, and never
fake a `derived_from` to make L13 skip the check instead (Phase A′ step 5).
Separately, **`gate`** refuses any story whose `acceptance_criteria` list is
empty (`has no acceptance_criteria`) — Phase A′ exists precisely so that
list is never empty when generation is asked for.

**Known limitation, state it to the human:** cascade staleness for a story
runs off `source_pins`, which `assert` populates only from `derived_from`
and `illustrated_by` refs. A human-stated story has neither, so
`source_pins` stays empty and a later PRD ingest has nothing to compare
against — the story never flips to needs-review and its TCs never see a
reason to go stale, even if the PRD ends up covering this exact scope. If
that happens, the story needs deliberate re-alignment.

## Phase A″ — PREPARE when the PRD has no acceptance criteria

Take this branch when the story HAS `derived_from` sections, but those
sections describe behaviour in prose and number no ACs — no `AC 1.1.3.1.1`
anywhere in the cited text, only paragraphs. A PRD section that *does*
number its ACs belongs to Phase A, not here — paraphrasing a PRD's own
numbered ACs into your words is a downgrade in evidence, not a stylistic
choice, so take Phase A verbatim whenever the numbers exist. Only take this
branch when they genuinely do not.

A draft story that already carries a `provenance` value — most often
`prd-verbatim` stamped by `migrate-provenance` as a pre-alignment default —
is not the branch decision; the source is. Read the cited `derived_from`
sections and pick Phase A, A′, or A″ by what they actually contain, then
overwrite whatever `provenance` was already there.

1. Read the cited `derived_from` sections exactly as Phase A step 2 does —
   verbatim bodies, faithful transcriptions — plus the `illustrated_by`
   Figma page (view the image, write/refresh its `# Visual Description`,
   noting PRD/mock discrepancies).
2. Author `acceptance_criteria` as a list of mappings, one per falsifiable
   statement you can draw from the prose: `{id: <section-slug>-AC01, text:
   "..."}`, `{id: <section-slug>-AC02, text: "..."}`, … `<section-slug>` is
   the slug `ingest-prd` gave the cited section (section `4.1.1.3` files as
   `sources/prd/4-1-1-3.md`, so its ACs are `4-1-1-3-AC01`,
   `4-1-1-3-AC02`, …) — each id names its own origin. A bare string entry or
   a mapping missing `id` is an L13 error regardless of provenance.
3. As each AC is drafted, immediately write its Resolution
   (`resolutions/R-<story>-NN.md`): `origin: agent-proposed`,
   `status: proposed`, `resolves:` pointing at
   `/stories/<id>.md#<section-slug>-ACNN`, and a body recording the human's
   confirmation **of your interpretation** — the PRD already states the
   requirement in its own words (that is what `derived_from` preserves);
   what needs a human behind it here is your reading of that prose into a
   falsifiable AC. Write it as the AC is drafted, not deferred to the assert
   step — Phase A′ learned that lesson the hard way, and a Resolution
   written after the fact just races the Phase B/C step 6 lint gate.
4. Set `provenance: prd-interpreted` and `status: in-alignment`. Keep
   `derived_from` — do not clear it. Because `derived_from` stays set,
   `assert` (step 12) populates `source_pins` for this story exactly as it
   does for a Phase A story: a Phase A″ story stays inside the staleness
   cascade, unlike a Phase A′ `human-stated` story, which pins nothing and
   so cannot be staled by a later PRD ingest. Given a PRD exists at all,
   that difference is the main reason to prefer this branch over inventing
   a source-less one.
5. Write `business_rules` and `components` from the same prose and the
   Figma page, as Phase A does.
6. Continue at step 5 of Phase A (Open Questions), and Phase B/C after that
   is unchanged.

**Forbid the escape hatch:** never relabel an interpreted story
`prd-verbatim` to make the Resolution requirement (step 3) go away. L13
cannot detect the substitution — a `prd-verbatim` story only has to carry
`derived_from`, nothing checks its AC text against the cited sections — and
W6, which does check that, only warns; it does not block. Mislabeling is
the one move that silently degrades the evidence this whole scheme exists
to preserve — never do it to avoid writing Resolutions.

## Phase B/C — INTERROGATE and CLOSE

6. Validate: `py tools/wiki.py manifest --no-commit && py tools/wiki.py lint --no-commit`
   — L2 will catch any typo'd edge or fragment ref immediately.
7. Commit the proposal as tc-agent (`git -c user.name=tc-agent -c
   user.email=tc-agent@internal commit`), message
   `align(<story>): ... Session: <id>`.
8. Emit the alignment card `build/cards/session-<story>-NNN.json` — four
   zones (what-you-said / what-I-understood / what-I-changed /
   what-this-affects) + open questions with proposed answers. **The card is
   the mandatory terminal artifact — a session without one is a failed
   session, not a quietly-done one.**
9. Present the card to the human (AskUserQuestion or the dashboard):
   Assert / Revise / Discard. Never proceed past this point on your own.

## On "Assert"

10. Write one Resolution concept per adopted Open-Question answer
    (`resolutions/R-<story>-NN.md`): `origin: agent-proposed`,
    `status: asserted`, `resolves:` pointing at the exact fragments,
    `# Human Statement` VERBATIM (quote the card action if that is all the
    human said). Resolutions are append-only — corrections later get new
    files with `supersedes` links, never edits. For a Phase A′ story, this
    step does NOT create the `HS-NN` Resolutions — those already exist from
    Phase A′ step 4; here you only flip their `status: proposed` to
    `status: asserted`.
11. Update the story: `# Resolutions` links, `# Open Questions` emptied,
    `version` +1.
12. `py tools/wiki.py assert story <id> --by <username>` — refuses if any
    open-question bullet remains. Then batch
    `py tools/wiki.py assert term <slug> --by <username>` for terms the human
    confirmed (optional; unconfirmed terms only cost a W3 warning).
13. Rebuild + verify: `manifest`, `index`, `lint`, then
    `py tools/wiki.py gate --story <id>` must print `GATE OPEN`.
14. Adoption commit as tc-agent referencing the card
    (`Assertion-Event: card session-<id> answer '<label>'`).

## Flow sessions: the journey

A flow alignment session MUST end with a proposed `journey:` — ordered
entries `{id: JNN, ref: /stories/<id>.md#<AC-id>, end_state: "<where the
user is left>", note?: "<clarifier>", branch?: <flow branch ref>}` covering
the walk across the member stories (seed heuristic: access/view/verify/
navigate ACs in screen order; the human reorders/prunes on the card).
`branch` is optional — set it only where a journey entry realises a flow
branch. Asserting the flow asserts the journey; `assert flow` refuses while
`# Open Questions` has bullets OR any member story is not `aligned`. Journey
refs are lint-checked (L2 resolution, L12 membership).

A flow the human rejects (wrong walk, wrong stories) is **discarded** at
human instruction — the commits are reverted and git history is the archive.
Never silently edit a rejected flow into a different one; propose a fresh
flow.

## Flow sessions: the scenario model (29119-4 5.2.9)

Alongside the journey, propose the flow's `test_model` and put it on the
same card the human asserts (load **tc-rubric**, "Step 2", flow paragraph):
`py tools/wiki.py testmodel --flow <id> --propose` writes `SC-MAIN` (the
journey as the main scenario). Add one `role: alternative` item per abnormal
use, exception or error path the member stories' ACs imply ("approver
rejects at J03", "session expires mid-journey", "upload fails at J05"),
each with `basis` naming the journey entries it departs from. A flow whose
model has the main scenario only is graded INCOMPLETE (T2.1 capped at
band 2), so the alternatives are part of alignment, not an afterthought.
The human's assert on the card confirms the model.

## Hard rules

- You may set `draft → in-alignment` and write everything agent-proposed.
- Only step 12, at explicit human instruction, makes a story `aligned`.
- Never edit or delete an asserted Resolution; never touch TC files here.
- `assert story|flow` REQUIRES `--card <path>` naming the card you presented;
  asserting stamps the human's answer into it. If it refuses for want of a
  card, the card step was skipped — go emit and present one, do not hunt for a
  card that will satisfy the flag.

## Not this skill

- Generating test cases from an aligned story → `tc-generate-sit`.
- Generating UAT test cases from an asserted journey → `tc-generate-uat`.
- A human is correcting already-asserted content → `tc-correct` (it captures
  the statement verbatim and propagates it; alignment is for first contact).
- A new PRD version arrived → `tc-change-report` first; re-align after.
