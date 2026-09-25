import { describe, expect, it } from 'vitest'
import { kanbanColumns, dashboardMetrics, matchesFilter } from './kanban'
import type { State, NextRow } from '../api'

// Full State factory so every fixture type-checks under strict mode.
function st(over: Partial<State>): State {
  return {
    project: 'DEMO', prd: { adopted: '1', staged: null },
    stories: [], flows: [], cards: [], change_reports: [],
    totals: { tcs: 0 }, next: { banners: [], rows: [] }, inventory: [], suites: [], ...over,
  }
}
// Story rows satisfy `Record<string, unknown> & { id; status }`, so the extra
// gather() fields are legal to include verbatim.
function story(id: string, status: string, x: Record<string, unknown> = {}) {
  return { id, status, title: `${id} title`, acs: 0, open_questions: 0,
           tc: { active: 0, stale: 0, retired: 0 }, stale_causes: [], ...x }
}
function nrow(id: string, state: string, scope: 'story' | 'flow'): NextRow {
  return { id, state, command: null, skill: 'x', scope, arg: id }
}

describe('kanbanColumns — story column derivation', () => {
  it('places a draft story with no ACs in Ingested', () => {
    const cols = kanbanColumns(st({ stories: [story('US-A', 'draft', { acs: 0 })] }))
    expect(cols.ingested.map((c) => c.id)).toEqual(['US-A'])
    expect(cols.ingested[0].phase).toBe('ingested')
  })

  it('places a draft story that already has ACs in In alignment', () => {
    const cols = kanbanColumns(st({ stories: [story('US-B', 'draft', { acs: 5 })] }))
    expect(cols.alignment.map((c) => c.id)).toEqual(['US-B'])
  })

  it('places an in-alignment story with open questions in In alignment', () => {
    const cols = kanbanColumns(st({ stories: [story('US-C', 'in-alignment', { acs: 4, open_questions: 3 })] }))
    expect(cols.alignment[0].id).toBe('US-C')
    expect(cols.alignment[0].openQuestions).toBe(3)
  })

  it('places a needs-review story in In alignment', () => {
    const cols = kanbanColumns(st({ stories: [story('US-D', 'needs-review', { acs: 4 })] }))
    expect(cols.alignment.map((c) => c.id)).toEqual(['US-D'])
  })

  it('places an aligned story with 0 pending and 0 TCs in Ready for generation', () => {
    const cols = kanbanColumns(st({ stories: [story('US-E', 'aligned', { acs: 6, open_questions: 0 })] }))
    expect(cols.ready.map((c) => c.id)).toEqual(['US-E'])
  })

  it('keeps an aligned story with open questions OUT of Ready (In alignment instead)', () => {
    const cols = kanbanColumns(st({ stories: [story('US-F', 'aligned', { acs: 6, open_questions: 2 })] }))
    expect(cols.ready).toHaveLength(0)
    expect(cols.alignment.map((c) => c.id)).toEqual(['US-F'])
  })

  it('places an aligned story with active TCs in Generated', () => {
    const cols = kanbanColumns(st({ stories: [story('US-G', 'aligned', { acs: 6, tc: { active: 39, stale: 0, retired: 1 } })] }))
    expect(cols.generated.map((c) => c.id)).toEqual(['US-G'])
    expect(cols.generated[0].tcActive).toBe(39)
    expect(cols.generated[0].staleFlag).toBe(false)
  })

  it('flags a Generated story stale via tc.stale', () => {
    const cols = kanbanColumns(st({ stories: [story('US-H', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } })] }))
    expect(cols.generated[0].staleFlag).toBe(true)
  })

  it('flags a Generated story stale via stale_causes', () => {
    const cols = kanbanColumns(st({ stories: [story('US-I', 'aligned', { tc: { active: 10, stale: 0, retired: 0 }, stale_causes: ['glossary changed'] })] }))
    expect(cols.generated[0].staleFlag).toBe(true)
  })

  it('does NOT set staleFlag on a non-generated card', () => {
    const cols = kanbanColumns(st({ stories: [story('US-J', 'aligned', { acs: 6, stale_causes: ['x'] })] }))
    expect(cols.ready[0].staleFlag).toBe(false)
  })
})

describe('kanbanColumns — flow column derivation (status + next row)', () => {
  it('routes an aligned flow whose next-row says 0 UAT TCs to Ready', () => {
    const cols = kanbanColumns(st({
      flows: [{ id: 'FLOW-pm', status: 'aligned' }],
      next: { banners: [], rows: [nrow('FLOW-pm', 'aligned · journey 6 entries · 0 UAT TCs', 'flow')] },
    }))
    expect(cols.ready.map((c) => c.id)).toEqual(['FLOW-pm'])
    expect(cols.ready[0].scope).toBe('flow')
  })

  it('routes a flow with active UAT TCs to Generated', () => {
    const cols = kanbanColumns(st({
      flows: [{ id: 'FLOW-pm', status: 'aligned' }],
      next: { banners: [], rows: [nrow('FLOW-pm', 'aligned · journey 6 entries · 4 active UAT TC(s) — ready', 'flow')] },
    }))
    expect(cols.generated.map((c) => c.id)).toEqual(['FLOW-pm'])
    expect(cols.generated[0].staleFlag).toBe(false)
  })

  it('routes a flow with STALE UAT TCs to Generated + staleFlag', () => {
    const cols = kanbanColumns(st({
      flows: [{ id: 'FLOW-pm', status: 'aligned' }],
      next: { banners: [], rows: [nrow('FLOW-pm', 'aligned · journey 6 entries · 2 STALE UAT TC(s)', 'flow')] },
    }))
    expect(cols.generated[0].staleFlag).toBe(true)
  })

  it('routes a draft flow (no matching next row) to In alignment', () => {
    const cols = kanbanColumns(st({ flows: [{ id: 'FLOW-x', status: 'draft' }] }))
    expect(cols.alignment.map((c) => c.id)).toEqual(['FLOW-x'])
  })

  it('never places a flow in Ingested', () => {
    const cols = kanbanColumns(st({ flows: [{ id: 'FLOW-x', status: 'draft' }] }))
    expect(cols.ingested).toHaveLength(0)
  })
})

describe('kanbanColumns — mixed board integrity', () => {
  it('partitions every story/flow into exactly one column and preserves ids', () => {
    const cols = kanbanColumns(st({
      stories: [
        story('US-A', 'draft', { acs: 0 }),
        story('US-E', 'aligned', { acs: 6 }),
        story('US-G', 'aligned', { tc: { active: 5, stale: 0, retired: 0 } }),
      ],
      flows: [{ id: 'FLOW-pm', status: 'aligned' }],
      next: { banners: [], rows: [nrow('FLOW-pm', 'aligned · journey 6 entries · 0 UAT TCs', 'flow')] },
    }))
    const all = [...cols.ingested, ...cols.alignment, ...cols.ready, ...cols.generated]
    expect(all).toHaveLength(4)
    expect(all.map((c) => c.id).sort()).toEqual(['FLOW-pm', 'US-A', 'US-E', 'US-G'])
    expect(cols.ingested.map((c) => c.id)).toEqual(['US-A'])
    expect(cols.ready.map((c) => c.id)).toEqual(['US-E', 'FLOW-pm'])
    expect(cols.generated.map((c) => c.id)).toEqual(['US-G'])
  })
})

describe('dashboardMetrics', () => {
  const state = st({
    stories: [
      story('US-A', 'draft', { acs: 0 }),                                  // ingested
      story('US-C', 'in-alignment', { acs: 4, open_questions: 3 }),        // alignment, 3 open
      story('US-E', 'aligned', { acs: 6 }),                               // ready
      story('US-G', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } }), // generated + stale
    ],
    totals: { tcs: 91 },
  })

  it('emits the five metrics in fixed order', () => {
    expect(dashboardMetrics(state).map((m) => m.key)).toEqual(['open', 'alignment', 'ready', 'tcs', 'stale'])
  })

  it('sums open questions across cards and marks them critical', () => {
    const open = dashboardMetrics(state).find((m) => m.key === 'open')!
    expect(open.value).toBe(3)
    expect(open.tone).toBe('critical')
  })

  it('counts the In alignment and Ready columns with attn tone when non-zero', () => {
    const m = dashboardMetrics(state)
    expect(m.find((x) => x.key === 'alignment')).toMatchObject({ value: 1, tone: 'attn' })
    expect(m.find((x) => x.key === 'ready')).toMatchObject({ value: 1, tone: 'attn' })
  })

  it('reads Test cases from totals.tcs (neutral) and counts Stale (critical)', () => {
    const m = dashboardMetrics(state)
    expect(m.find((x) => x.key === 'tcs')).toMatchObject({ value: 91, tone: 'neutral' })
    expect(m.find((x) => x.key === 'stale')).toMatchObject({ value: 1, tone: 'critical' })
  })

  it('keeps quiet (neutral, 0) when nothing needs attention', () => {
    const quiet = dashboardMetrics(st({ stories: [story('US-G', 'aligned', { tc: { active: 5, stale: 0, retired: 0 } })], totals: { tcs: 5 } }))
    for (const key of ['open', 'alignment', 'ready', 'stale'] as const) {
      expect(quiet.find((m) => m.key === key)).toMatchObject({ value: 0, tone: 'neutral' })
    }
  })
})

describe('matchesFilter', () => {
  const cols = kanbanColumns(st({
    stories: [
      story('US-C', 'in-alignment', { acs: 4, open_questions: 3 }),
      story('US-E', 'aligned', { acs: 6 }),
      story('US-G', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } }),
    ],
  }))
  const alignmentCard = cols.alignment[0]
  const readyCard = cols.ready[0]
  const generatedCard = cols.generated[0]

  it('null filter matches everything', () => {
    expect(matchesFilter(alignmentCard, null)).toBe(true)
  })
  it('open matches only cards with open questions', () => {
    expect(matchesFilter(alignmentCard, 'open')).toBe(true)
    expect(matchesFilter(readyCard, 'open')).toBe(false)
  })
  it('phase filters match their column', () => {
    expect(matchesFilter(alignmentCard, 'alignment')).toBe(true)
    expect(matchesFilter(readyCard, 'ready')).toBe(true)
    expect(matchesFilter(generatedCard, 'tcs')).toBe(true)
  })
  it('stale matches only staleFlag cards', () => {
    expect(matchesFilter(generatedCard, 'stale')).toBe(true)
    expect(matchesFilter(readyCard, 'stale')).toBe(false)
  })
})
