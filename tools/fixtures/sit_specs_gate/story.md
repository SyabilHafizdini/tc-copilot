---
type: Story
id: US-FIXTURE-SIT-GATE
title: Fixture gate story (smoke test only)
description: >-
  Testability fixture for tools/smoke.py's SIT coverage-fence CLI check.
  coverage_status is deliberately not "confirmed" so the fence in
  tools/render_sit.py refuses to render against it. Lives beside its spec
  rather than in stories/ so the fence is exercisable in ANY bundle --
  including an empty base branch, which has no project stories at all.
coverage_status: proposed
acceptance_criteria:
  - id: AC01
    text: Fixture AC, never rendered -- the fence exits before this is read.
components: []
coverage_map: []
---

Fixture only. See tools/smoke.py's "SIT coverage fence" check.
