import { describe, expect, it } from 'vitest'
import type { ExplorerSnapshot } from '../explorer/types'
import { levelOf, parseTcSteps, storyTestCases } from './testcases'

// A real TC body (testcases/sit/production-monitoring/1.1.3.1.1-AC08-01.md), trimmed.
const BODY = `# Objective

Verify changing a global filter refreshes all widgets accordingly.

# Test Data

**Workshop** = add Workshop Y (keep Workshop X)

# Steps

1. Note the **'Total'** of the chart.
2. Add **Workshop Y** to the **'Workshop'** filter.
3. Observe all three widgets.

# Expected Results

1. Baseline total recorded.
2. Filter pill now includes Workshop Y.
3. All three widgets refresh.
4. Elements displayed and labelled correctly.

# Postconditions

No system state changed.
`

describe('levelOf', () => {
  it('derives the level from the ref path', () => {
    expect(levelOf('testcases/sit/production-monitoring/1.1.3.1.1-AC08-01')).toBe('sit')
    expect(levelOf('testcases/uat/production-monitoring/UAT-1.1.3.1.1-AC01-01')).toBe('uat')
    expect(levelOf('testcases/osat/foo/bar')).toBe('osat')
    expect(levelOf('stories/US-VHLD')).toBeNull()
  })
})

describe('parseTcSteps', () => {
  it('zips Steps and Expected Results by index and carries Test Data on the first row', () => {
    const rows = parseTcSteps(BODY)
    expect(rows).toHaveLength(4) // max(3 steps, 4 expected)
    expect(rows[0]).toEqual({
      n: 1,
      action: "Note the **'Total'** of the chart.",
      data: '**Workshop** = add Workshop Y (keep Workshop X)',
      expected: 'Baseline total recorded.',
    })
    expect(rows[3]).toEqual({ n: 4, action: '', data: '', expected: 'Elements displayed and labelled correctly.' })
  })

  it('returns an empty list when there are no step sections', () => {
    expect(parseTcSteps('# Objective\n\nnothing here')).toEqual([])
  })
})

describe('storyTestCases', () => {
  const snap: ExplorerSnapshot = {
    tree: [], graph: { nodes: [], links: [] },
    docs: {
      'testcases/sit/production-monitoring/1.1.3.1.1-AC08-01': {
        ref: 'testcases/sit/production-monitoring/1.1.3.1.1-AC08-01', kind: 'testcases',
        title: 'Changing filter options', status: 'active', version: 1, body_md: BODY,
        facets: { kind: 'testcases', status: 'active', origin_state: 'proposed', story: null,
          asserted_by: null, stale: false, staleness_causes: [] },
        fields: [{ key: 'covers', kind: 'links', refs: ['/stories/US-VHLD.md#1.1.3.1.1-AC8'] }],
      },
      'testcases/uat/production-monitoring/UAT-1.1.3.1.1-AC01-01': {
        ref: 'testcases/uat/production-monitoring/UAT-1.1.3.1.1-AC01-01', kind: 'testcases',
        title: 'Access the dashboard', status: 'active', version: 1, body_md: '# Steps\n\n1. Log in.\n',
        facets: { kind: 'testcases', status: 'active', origin_state: 'proposed', story: null,
          asserted_by: null, stale: false, staleness_causes: [] },
        fields: [{ key: 'covers', kind: 'link', ref: '/stories/US-VHLD.md#1.1.3.1.1-AC1', label: 'AC1' }],
      },
      'testcases/sit/production-monitoring-vdtl/1.1.3.1.2-AC01-01': {
        ref: 'testcases/sit/production-monitoring-vdtl/1.1.3.1.2-AC01-01', kind: 'testcases',
        title: 'Other story TC', status: 'active', version: 1, body_md: '# Steps\n\n1. x.\n',
        facets: { kind: 'testcases', status: 'active', origin_state: 'proposed', story: null,
          asserted_by: null, stale: false, staleness_causes: [] },
        fields: [{ key: 'covers', kind: 'links', refs: ['/stories/US-VDTL.md#1.1.3.1.2-AC1'] }],
      },
      'stories/US-VHLD': {
        ref: 'stories/US-VHLD', kind: 'stories', title: 'Vehicle Holding', status: 'aligned',
        version: 2, body_md: '', fields: [],
        facets: { kind: 'stories', status: 'aligned', origin_state: 'asserted', story: 'stories/US-VHLD',
          asserted_by: 'syabz', stale: false, staleness_causes: [] },
      },
    },
  }

  it('returns only the target story TCs, sorted by id, with level + ac + parsed steps', () => {
    const rows = storyTestCases(snap, 'US-VHLD')
    expect(rows.map((r) => r.id)).toEqual(['1.1.3.1.1-AC08-01', 'UAT-1.1.3.1.1-AC01-01'])
    expect(rows[0].level).toBe('sit')
    expect(rows[0].ac).toBe('1.1.3.1.1-AC8')
    expect(rows[0].steps).toHaveLength(4)
    expect(rows[1].level).toBe('uat')
    expect(rows[1].ac).toBe('1.1.3.1.1-AC1') // covers as a single 'link' field is also read
  })

  it('excludes TCs that cover a different story', () => {
    const rows = storyTestCases(snap, 'US-VHLD')
    expect(rows.some((r) => r.id === '1.1.3.1.2-AC01-01')).toBe(false)
  })
})
