---
type: Flow
id: FLOW-fixture-gate
title: Fixture gate flow (smoke test only)
description: >-
  Testability fixture for tools/smoke.py's UAT coverage-fence CLI check (I1).
  Not a real flow: sits outside CONCEPT_DIRS so load_all() never sees it.
  Read only by tools/render_production_monitoring_uat.py when
  TC_UAT_FIXTURE_DIR points at this directory.
entry_condition: fixture entry
journey:
  - id: J01
    ref: /stories/__fixture-gate__.md#AC01
    end_state: fixture end
---

Fixture only. See tools/smoke.py's "UAT coverage fence" check.
