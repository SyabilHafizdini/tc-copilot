# Skills

Invoke a skill by name in OpenCode or Claude Code (`/tc-align`) or describe
the job and let `/tc-help` route it. One skill per job; each has an in-depth
guide.

| Skill | Use it when | Guide |
|---|---|---|
| `tc-help` | You do not know what to do next, or are resuming | [guide](skills/tc-help.md) |
| `tc-intake` | Files are waiting in `PUT_FILES_HERE/`, or triage refused one | [guide](skills/tc-intake.md) |
| `tc-align` | A story or flow needs its ACs, rules, components or journey asserted; or there is no PRD at all | [guide](skills/tc-align.md) |
| `tc-generate-sit` | You want SIT test cases for an aligned story | [guide](skills/tc-generate-sit.md) |
| `tc-generate-uat` | You want UAT test cases walking an aligned flow's journey | [guide](skills/tc-generate-uat.md) |
| `tc-rubric` | Loaded by the generate skills: the test model and the one-round grade loop | [guide](skills/tc-rubric.md) |
| `tc-evaluate` | Score an existing set of test cases without changing it | [guide](skills/tc-evaluate.md) |
| `tc-style` | Loaded when writing test-case text: the wording contract | [guide](skills/tc-style.md) |
| `tc-suite-author` | Filter generated test cases into a suite and export the workbook | [guide](skills/tc-suite-author.md) |
| `tc-correct` | You spotted an error in an asserted definition, rule or AC | [guide](skills/tc-correct.md) |
| `tc-change-report` | A new PRD version arrived | [guide](skills/tc-change-report.md) |
| `tc-lifecycle` | Retire, void, un-retire a test case, or resolve a hand-edit | [guide](skills/tc-lifecycle.md) |
| `run-tc-copilot` | Run the platform: health check, CLI, exports, where artifacts live | [guide](skills/run-tc-copilot.md) |

## The loop

```
intake  ->  align  ->  generate + grade  ->  select + export
tc-intake   tc-align    tc-generate-sit       tc-suite-author
                        tc-generate-uat
                        (+ tc-rubric, tc-style)
```

Corrections (`tc-correct`), new PRD versions (`tc-change-report`) and
retirements (`tc-lifecycle`) feed back into the loop without regenerating
anything until you say so. The workbook arrives twice: a labelled draft right
after the first seal, and the graded final with a change log when the rubric
round finishes.

## Verify the base

```
py tools/wiki.py lint         # 0 errors, 0 warnings
py tools/smoke.py --fast      # SMOKE OK, with [SKIP]s for absent content
```

Command reference: [cli.md](cli.md).
