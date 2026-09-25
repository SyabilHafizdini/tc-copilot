# tc-correct

Propagates a correction you state in conversation through already-asserted
content. Your statement is human-stated at origin; the agent's propagation
of it can be wrong, so it is proposed and separately asserted.

## When to use it

- You spotted a wrong definition, business rule, AC interpretation or
  component fact in the wiki, and there is no new PRD behind the change.

Not for first-contact alignment (`tc-align`), not for a new PRD version
(`tc-change-report`), not for a test case that should simply go away
(`tc-lifecycle`).

## How it runs

1. **Capture.** `resolutions/R-<scope>-NN.md` is written immediately:
   `origin: human-stated`, `status: proposed`, your words verbatim under
   `# Human Statement`, `resolves:` pointing at the affected fragments.
2. **Locate.** The manifest's edges are walked from the corrected fragment:
   inbound `covers` and `verifies_rules` (test cases), `uses_terms` (stories,
   test cases), `stories` (flows). The list is deterministic.
3. **Propagate.** Affected story and glossary bodies are edited through the
   concept API. Story versions bump. A superseded Resolution gets
   `status: superseded` and the reciprocal `supersedes` link. Test-case
   files are never touched.
4. **Cascade.** `py tools/wiki.py cascade` flags precisely: aligned stories
   whose pinned sources changed become `needs-review`; test cases whose
   pinned fragments changed become `stale`.
5. **Present.** A card with four zones: what you said (verbatim), what the
   agent understood (the propagation-error tripwire), what it changed
   (per-file diffs), what this affects (staled ids and counts).
6. **You answer.** Assert: the Resolution becomes asserted, stories you
   re-assert run through `wiki assert`. Revise: loop with the delta.
   Discard: the propagation commits are reverted.

Asserting the card never regenerates anything. Batch corrections, then ask
for regeneration once.

## Reading the card

"What I understood" is your tripwire. If its restatement is off, the edits
are off. Say revise.

"What this affects" is computed, not guessed. Editing one AC stales exactly
the test cases that cover it and nothing else.

## Refusals and why

- The card does not offer "confirm and regenerate" as one action.
  Assertion and regeneration are separate human acts.
- Asserted Resolutions are never edited or deleted; a later correction is a
  new file with a `supersedes` link.
