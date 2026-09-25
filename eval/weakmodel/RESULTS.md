# Weak-model eval results

**Date:** 2026-08-02
**Model:** a ~400B-parameter open-weight chat model served through an OpenAI-compatible gateway (names withheld)
**Harness:** `py tools/eval_weakmodel.py --trials 3 --workers 3`
**Branch under test:** `feat/enforcement-and-opencode-plugin`

Scoring is deterministic string matching. No LLM judge anywhere.

---

## Headline

| Measurement | Before | After | n |
|---|---|---|---|
| Skill routing (right skill from descriptions) | 91.7% | **100%** | 36 / 36 trials |
| Next action (right command from state) | 0% | **100%** | 5 / 15 trials |
| Reasoning cost for next action (median completion tokens) | 2764 | **922** | 5 / 15 |
| Refusal comprehension (takes the remedy, never the bypass) | — | 100% CORRECT, 0% BYPASS | 11 |

14 of 117 calls were lost to gateway 504s and excluded from scoring.

---

## 1. Skill routing

**A** = skill descriptions as they were before `d31267e`. **B** = current descriptions,
which added an explicit negative clause naming the skill that handles the adjacent case.

- A: 91.7% (33/36) · B: 100% (36/36)

Exactly one of twelve scenarios discriminates, and the aggregate difference rests
entirely on it — `r01`:

> "The SIT test cases for US-VHLD already exist and are sealed. I want them pulled
> into an Excel workbook for the test team, P1 only."

- **A: chose `tc-generate-sit` 3/3.** The old description read "Use when asked to
  generate, regenerate, **or export** SIT test cases", so an export request matched it.
- **B: chose `tc-suite-author` 3/3.** The new description says selection "never creates,
  edits, or re-words a test case", and `tc-generate-sit` now says it "does NOT filter or
  export existing TCs into a workbook".

The other eleven scenarios were unambiguous under both wordings. So the honest reading
is not "routing got 8 points better" but "one specific, predicted collision was closed,
and nothing regressed".

## 2. Next action

**A** = a row from `wiki status`. **B** = the `wiki next` block (what the opencode
plugin injects each turn).

- A: 0% (0/5) · B: 100% (15/15)

The failure mode is worse than a wrong choice — **the model invented commands that do
not exist**:

| scenario | expected | A produced |
|---|---|---|
| n01 | `suite compile …` | `py tools/wiki.py show US-VHLD` (no such command) |
| n05 | `render_sit.py --story US-VDTL` | `py tools/wiki.py checkout US-VDTL` (no such command) |

Given only state, it fabricates plausible-sounding CLI verbs. Given the next command
explicitly, it runs the right one every time.

**Caveat:** 10 of the 15 A trials were lost to gateway timeouts, so A rests on n=5.
The direction is unambiguous (0/5, and both distinct scenarios produced invented
commands) but the magnitude is under-powered.

## 3. Reasoning cost

Median completion tokens per answer — the "speed" half of the question:

| condition | median | min | max | n |
|---|---|---|---|---|
| next_action / A_status | 2764 | 2764 | 2899 | 5 |
| next_action / B_next | **922** | 338 | 3073 | 15 |
| refusal / single | 2959 | 421 | 2970 | 11 |
| routing / A_before | 593 | 460 | 1311 | 36 |
| routing / B_after | 608 | 478 | 2871 | 36 |

Injecting `wiki next` cut median reasoning **~3x** (2764 → 922). Less to infer means
less to think about. Routing cost was flat between conditions, as expected — the
descriptions changed in content, not in volume.

## 4. Refusal comprehension

Single condition — this measures whether the refusal text is actionable, **not** a
before/after improvement.

- CORRECT 100% (11/11), OTHER 0%, BYPASS 0%

No trial reached for `--allow-unconfirmed-coverage` or `--allow-lint-errors`, and none
proposed hand-editing a story's `status:` field to get past a blocked gate. On a
coverage refusal it ran `wiki.py coverage --story US-VDTL --propose`; on an unsealed
refusal, `wiki.py seal`.

---

## What this does NOT measure

- **The opencode plugin's live blocking.** The gateway rejects opencode's requests
  (see `references/gotchas.md`), so the plugin was never exercised end to end against
  a real session. The eval covers the skills and CLI only.
- **Multi-step agentic behaviour.** Every scenario is one turn. It says nothing about
  whether the model *keeps* following the protocol across a long session, which is the
  "skips steps / stops early" failure this branch also targets.
- **Whether the fences hold under a determined model.** Refusal comprehension shows it
  takes the remedy when told; it does not show what happens after several failures.

## Reproducing

```
TC_EVAL_BASE_URL=https://your-gateway/v1/chat/completions \
TC_EVAL_MODEL=your-model-id \
py tools/eval_weakmodel.py --trials 3 --workers 3 --json results.json
```

Requires `~/.config/opencode/tc-eval-key` to contain the bare `sk-…` token — some
gateways prefix the stored key with an account id that must be stripped before it
is used as the Authorization header.

Two traps worth knowing if you extend this:

1. The model is a **reasoning** model. It emits `content` only after a long `reasoning`
   field; at `max_tokens=8000` four of five answers came back empty. Truncation is
   reported as `__TRUNCATED__` and excluded from scoring — scoring an unfinished
   response as wrong would measure the token budget, not the model.
2. **Gateway 504 loss is not random.** The conditions that give the model least context
   make it think longest, so they time out most. A first pass at 8 workers lost *100%*
   of the `A_status` arm and would have reported the survivor's score as a result.
   Retries plus 3 workers cut total loss from 31/117 to 14/117.
