---
type: Story
id: US-FIXTURE-GATE
title: Fixture gate story (smoke test only)
description: >-
  Testability fixture for tools/smoke.py's UAT coverage-fence CLI check (I1).
  coverage_status is deliberately not "confirmed" so the fence in
  tools/render_production_monitoring_uat.py refuses to render against it.
coverage_status: proposed
acceptance_criteria:
  - id: AC01
    text: Fixture AC, never rendered -- the fence exits before this is read.
components: []
coverage_map: []
---

Fixture only. See tools/smoke.py's "UAT coverage fence" check.
