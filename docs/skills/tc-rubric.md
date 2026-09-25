# tc-rubric

The ISO/IEC/IEEE 29119-4 grade loop. It is loaded alongside
`tc-generate-sit` and `tc-generate-uat`, not run on its own. Three things it
adds to generation: the test model on the coverage card, `coverage_items` on
every test case, and one fixed improve round with four judge lenses.

## Why

Before the rubric, technique tags (UC, EP, BVA, DT, ST, ERR, PW) were labels
the renderer only checked for membership. Nothing enumerated the partitions,
boundaries, rules, transitions or scenarios a story contains, so nothing
could count what was covered. The standard defines every technique in three
steps: create a test model (TD1), identify test coverage items (TD2), derive
test cases (TD3). The platform had TD3 only.

## The rubric

`standards/rubric/tc-rubric-v1.yaml`, versioned and hashed. Two tiers, each
100 points, every dimension banded 0 to 4 and citing a clause.

**Tier 1, per test case**: coverage-item linkage (T1.1), test-basis
traceability (T1.2), input data specificity (T1.3), expected-result
determinacy (T1.4), expected result derived from the basis (T1.5), input
and state completeness (T1.7), technique fit (T1.8), one invalid input per
negative case (T1.9).

**Tier 2, per story or flow**: per-technique coverage `C = N / T x 100`
(T2.1), requirements coverage (T2.2), infeasible-item discipline (T2.4),
valid/invalid balance (T2.5), quality-characteristic spread (T2.6),
redundancy (T2.7).

Score = tier 1 mean x 0.40 + tier 2 x 0.60. Threshold in `config.yaml`
(`rubric.threshold`, default 70).

## The three artifacts

1. **Test model**, frontmatter `test_model:` on the story or flow. One item
   per coverage item: `{id, technique, kind, subject, desc, basis, feasible,
   justification}`. `basis` must name real AC or rule ids (lint L14).
   Proposed by the agent, confirmed by the human on the coverage card. No
   second gate.
2. **`coverage_items`** on every spec entry: the ids that test case
   exercises. The technique tag must fit the item kind (BVA on boundaries,
   EP on partitions, DT on rule rows, ST on transitions, UC on scenarios;
   ERR on any). The renderer refuses an unknown id.
3. **Judge verdicts**, `build/rubric/judgments/<scope>-r<N>-<lens>.json`,
   one per lens per round, written by a subagent that read its pack.

## The loop, exactly one round

```
a. evaluate     py tools/eval_rubric.py --story <id> --round 1 --pack
                -> score JSON (PARTIAL: no judges yet), gap report, 4 packs
b. judge        4 subagents in parallel, one per pack, each writes its JSON
                py tools/eval_rubric.py --story <id> --round 1   (merge)
c. improve      improver subagent reads the gap report, writes
                build/rubric/<id>-r1-patch.json; the main agent applies it:
                py tools/eval_rubric.py --story <id> --apply-patch <patch>
                py tools/render_sit.py --story <id> --force && py tools/wiki.py seal
d. re-evaluate  --round 2 --pack, 4 judges, merge -> delta printed
                round 2 packs list only test cases changed since round 1;
                unchanged verdicts are carried (judgments/<id>-r2-<L>.carried.json)
e. STOP         report both scores. Lower round 2 = restore round 1's spec.
```

The four lenses: **A** expected-result (T1.4, T1.5); **B**
input-completeness (T1.7); **C** technique-fit (T1.8); **D** set-level
(T2.5, T2.6). Each pack states the obligations, the material, the
mechanical ceilings, the rules and the exact file to write. A verdict on the
wrong dimension, an unknown test case, a different rubric hash, or without
a rationale is rejected with every error listed.

The improver proposes a patch list (`set` a field of an existing entry, or
`add` a test case for an uncovered item). `--apply-patch` validates every
patch against the spec's key set and writes nothing if any patch is bad.

## Draft, diff, final

```
py tools/wiki.py export --story <id> --name <n> --draft   # writes the DRAFT round 0
                                                            # workbook + build/rubric/<id>-draft.json
py tools/eval_rubric.py --story <id> --diff                # draft snapshot vs the
                                                            # sealed set -> <id>-changes.{md,json}
py tools/wiki.py export --story <id> --name <n>             # final export; refuses without
                                                            # a current strict score, fills
                                                            # the workbook's Change Log
```

## Reading a score

- **PARTIAL** means a judge lens is missing. A missing verdict is never
  band 0. A mechanical ceiling of 0 (empty expected results, no negative
  case in the set) is a measurement and stands without a judge.
- Where a dimension is mechanical plus judge, band = min(ceiling, judge).
- `coverage` lists `N / T` per technique. T counts feasible items; N counts
  items some active test case names.
- Two scores compare only under the same rubric hash.
- The gap report `build/rubric/<id>-rN-gaps.md` lists G1 (uncovered items),
  G2 (set-level dimensions below 3) and G3 (per-test-case dimensions below
  3 with the judge's rationale and suggested fix).

## Refusals and why

- A `proposed` or empty test model: the engine refuses. There is no honest
  denominator, and a proposed model is the agent's guess.
- `--strict` on a PARTIAL score: refused. Run the missing lens; do not reach
  for `--allow-partial`.
- Never a third round. Never keep a regressed round 2.
- Never edit `testcases/**` to close a gap. Gaps close through the spec and
  a forced re-render.

## Related

- `tc-evaluate` scores an existing set without generating.
- `tc-align` proposes a flow's alternative scenarios.
