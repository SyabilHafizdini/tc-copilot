# tc-copilot

Turn a requirements document into reviewed, graded test cases.

You drop in your PRD and screen designs. An AI agent reads them, drafts the
user stories and the test cases, and brings every decision to you on a card.
Nothing moves forward until you have said yes. The result is a test-case
workbook in your organisation's format, delivered twice: a draft minutes after
you confirm the coverage, and a final version graded against the
ISO/IEC/IEEE 29119-4 test-design standard, with a change log of what the
grading improved.

## Before you start

- Python 3.11 or newer (Windows: the `py` launcher).
- Git.
- An agent harness that runs the skills: [OpenCode](https://opencode.ai)
  (the repo ships its plugin) or [Claude Code](https://claude.com/claude-code).

## Three steps

**1. Install.** In the project folder:

```
py -m pip install -r requirements.txt
```

**2. Put your documents in the folder.** Copy your PRD or PRDs (pdf, docx or
md; each gets an id and a title when it is first ingested), your Figma screen
exports (png) and any decks (pptx) into `PUT_FILES_HERE/`. Any order, any
names.

**3. Run the skill.** Open OpenCode or Claude Code in the project folder and
type:

```
/tc-help
```

It tells you the one next thing to do and starts it when you agree. From
there the agent takes you through intake, alignment, generation and export,
one card at a time. Type `/tc-help` again whenever you are unsure where you
are.

## What happens along the way

- **Intake.** Your files are sorted and ingested. The agent asks about any
  file it cannot classify.
- **Alignment.** For each story the agent drafts acceptance criteria,
  business rules and the screen's components, and asks its questions with
  proposed answers. You assert, revise or discard.
- **Generation.** You confirm one coverage card per story. The draft workbook
  arrives right after. The agent then grades and improves the set while you
  review the draft, and hands you the final workbook with its change log.
- **The AI's doubts.** Every part of a test case the AI rated Medium or Low
  is a doubt. The agent groups them into questions you answer on a card; only
  your answer raises a part to High (`tc-resolve`).
- **Changes later.** Corrections, new PRD versions and retirements all go
  through the same cards. Nothing regenerates until you say so.

## The operator app

`py tools/wiki.py app` opens a local browser app over the same files (it needs
`py -m pip install -r tools/app/requirements.txt`). On the Test Cases page you
review every test case in the workbook's columns and reword one field
yourself; Save runs `wiki tc edit` under your name. The Workbook page opens a
compiled workbook as testers receive it, with the rows that changed since the
compile marked. The docked chat is Off by default; switch it on under
Settings.

A project written before the PRD registry is converted once with
`py tools/wiki.py migrate-prds`, at your instruction. All of this is in the
[command reference](docs/cli.md).

## Read more

- [Getting started](docs/getting-started.md): the first project, end to end.
- [Playbook](docs/playbook.md): day-to-day use, what refuses and why.
- [Skills](docs/skills.md): which skill does what, with a guide for each.
- [Command reference](docs/cli.md): the underlying commands, for when you
  want to run the tooling yourself.

## Ground rules the tooling enforces

- Only you can assert. The agent proposes; a card records your answer.
- Nothing generates from a story you have not asserted.
- The agent never raises a confidence level. The renderers refuse a raised
  level; only your answer, recorded by `wiki doubts answer`, lifts one.
- Generated files are never edited by hand. Change the source and re-render.
- Every change is a git commit, so the history is the audit trail.
