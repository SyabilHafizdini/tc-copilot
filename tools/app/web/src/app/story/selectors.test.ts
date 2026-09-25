import { describe, expect, it } from 'vitest'
import type { State } from '../api'
import { storyFromState, readiness, allowedTransitions, storyPhase, type Story } from './selectors'

// A fully generated, export-ready story.
const READY: Story = {
  id: 'US-VHLD', title: 'Vehicle Holding', status: 'aligned', module: 'production-monitoring.md',
  acs: 25, open_questions: 0, asserted_by: 'syabz',
  tc: { active: 39, stale: 0, retired: 0 },
  stale_causes: [],
  components: { total: 15, covered: 13, acs_without_tcs: 0, out_of_scope: 2, gaps: 0 },
}
const DRAFT: Story = { ...READY, status: 'draft', asserted_by: null, tc: { active: 0, stale: 0, retired: 0 },
  components: { total: 15, covered: 0, acs_without_tcs: 0, out_of_scope: 0, gaps: 15 } }
const OPEN_Q: Story = { ...READY, open_questions: 3 }
const COVERAGE_GAP: Story = { ...READY, components: { total: 15, covered: 10, acs_without_tcs: 0, out_of_scope: 2, gaps: 3 } }
const STALE: Story = { ...READY, tc: { active: 39, stale: 2, retired: 0 }, stale_causes: ['prd changed'] }
const NOT_ASSERTED: Story = { ...READY, asserted_by: null }
const READY_TO_GENERATE: Story = { ...READY, tc: { active: 0, stale: 0, retired: 0 },
  components: { total: 15, covered: 0, acs_without_tcs: 13, out_of_scope: 2, gaps: 0 } }

describe('readiness', () => {
  it('a generated, sealed story is ready and its next action is a download export', () => {
    const r = readiness(READY)
    expect(r.ready).toBe(true)
    expect(r.gates).toEqual({ aligned: true, coverage: true, lint: true, asserted: true })
    expect(r.blocker).toBeUndefined()
    expect(r.nextAction).toEqual({ label: 'Export ↓', action: 'export', params: { story: 'US-VHLD', name: 'US-VHLD-sit' } })
  })

  it('a draft story is blocked on alignment first (first unmet gate wins)', () => {
    const r = readiness(DRAFT)
    expect(r.ready).toBe(false)
    expect(r.gates.aligned).toBe(false)
    expect(r.blocker).toBe("Not aligned — status 'draft'")
    expect(r.nextAction).toEqual({ label: 'Run gate check', action: 'gate', params: { story: 'US-VHLD' } })
  })

  it('an aligned story with open questions is blocked on the questions', () => {
    const r = readiness(OPEN_Q)
    expect(r.gates.aligned).toBe(false)
    expect(r.blocker).toBe('Aligned but 3 open question(s) remain')
  })

  it('a coverage gap blocks after alignment', () => {
    const r = readiness(COVERAGE_GAP)
    expect(r.gates.aligned).toBe(true)
    expect(r.gates.coverage).toBe(false)
    expect(r.blocker).toBe('Coverage incomplete — 3 component gap(s)')
  })

  it('a ready-to-generate story (no TCs yet) blocks on missing test cases', () => {
    const r = readiness(READY_TO_GENERATE)
    expect(r.gates.coverage).toBe(false)
    expect(r.blocker).toBe('13 component(s) not yet covered by an active test case — generate')
  })

  it('stale TCs block the lint gate even when coverage holds', () => {
    const r = readiness(STALE)
    expect(r.gates.coverage).toBe(true)
    expect(r.gates.lint).toBe(false)
    expect(r.blocker).toBe('2 stale test case(s) — regenerate')
  })

  it('an unasserted-but-otherwise-complete story blocks on assertion last', () => {
    const r = readiness(NOT_ASSERTED)
    expect(r.gates.asserted).toBe(false)
    expect(r.blocker).toBe('Not asserted by a human yet')
  })
})

describe('storyFromState', () => {
  const state = {
    project: 'p', prd: { adopted: '1', staged: null }, flows: [], cards: [], change_reports: [],
    totals: {}, next: { banners: [], rows: [] },
    stories: [{
      id: 'US-VHLD', title: 'Vehicle Holding', status: 'aligned', module: 'production-monitoring.md',
      acs: 25, open_questions: 0, asserted_by: 'syabz', stale_causes: [],
      tc: { active: 39, stale: 0, retired: 0 },
      components: { total: 15, covered: 13, acs_without_tcs: 0, out_of_scope: 2, gaps: 0 },
    }],
  } as unknown as State

  it('narrows a dashboard row into a typed Story', () => {
    const s = storyFromState(state, 'US-VHLD')
    expect(s?.status).toBe('aligned')
    expect(s?.tc.active).toBe(39)
    expect(s?.components.gaps).toBe(0)
  })

  it('returns null for an unknown id', () => {
    expect(storyFromState(state, 'US-NOPE')).toBeNull()
  })
})

describe('allowedTransitions', () => {
  it('a draft story offers a gated "Assert alignment" plus the read-only checks', () => {
    const t = allowedTransitions(DRAFT)
    expect(t[0]).toEqual({ label: 'Assert alignment', action: 'gate', params: { story: 'US-VHLD' }, gated: true })
    // universal read-only checks always last, never gated
    expect(t.slice(-2)).toEqual([
      { label: 'Run gate check', action: 'gate', params: { story: 'US-VHLD' }, gated: false },
      { label: 'Run lint', action: 'lint', params: {}, gated: false },
    ])
  })

  it('an aligned story with a coverage gap offers a gated "Confirm coverage"', () => {
    const t = allowedTransitions(COVERAGE_GAP)
    expect(t[0]).toEqual({ label: 'Confirm coverage', action: 'gate', params: { story: 'US-VHLD' }, gated: true })
  })

  it('an aligned story with stale TCs offers a gated "Regenerate stale test cases"', () => {
    const t = allowedTransitions(STALE)
    expect(t[0]).toEqual({ label: 'Regenerate stale test cases', action: 'gate', params: { story: 'US-VHLD' }, gated: true })
  })

  it('a fully ready story offers no status-advancing transition — only the read-only checks', () => {
    const t = allowedTransitions(READY)
    expect(t.every((x) => x.gated === false)).toBe(true)
    expect(t.map((x) => x.label)).toEqual(['Run gate check', 'Run lint'])
  })

  it('a needs-review story offers a gated "Re-align"', () => {
    const t = allowedTransitions({ ...DRAFT, status: 'needs-review' })
    expect(t[0]).toEqual({ label: 'Re-align', action: 'gate', params: { story: 'US-VHLD' }, gated: true })
  })
})

describe('storyPhase', () => {
  it('draft → phase 0 (Ingest)', () => {
    expect(storyPhase(DRAFT)).toBe(0)
  })
  it('in-alignment / needs-review → phase 1 (Alignment)', () => {
    expect(storyPhase({ ...DRAFT, status: 'in-alignment' })).toBe(1)
    expect(storyPhase({ ...DRAFT, status: 'needs-review' })).toBe(1)
  })
  it('aligned but with open questions → phase 1 (still Alignment)', () => {
    expect(storyPhase(OPEN_Q)).toBe(1)
  })
  it('aligned, 0 open questions, no active TCs → phase 2 (Ready for generation)', () => {
    expect(storyPhase(READY_TO_GENERATE)).toBe(2)
  })
  it('aligned with active TCs → phase 3 (Generated)', () => {
    expect(storyPhase(READY)).toBe(3)
  })
})
