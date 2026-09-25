import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { PhaseKanban } from './PhaseKanban'
import type { State, NextRow } from '../api'

function st(over: Partial<State>): State {
  return {
    project: 'DEMO', prd: { adopted: '1', staged: null },
    stories: [], flows: [], cards: [], change_reports: [],
    totals: { tcs: 0 }, next: { banners: [], rows: [] }, inventory: [], suites: [], ...over,
  }
}
function story(id: string, status: string, x: Record<string, unknown> = {}) {
  return { id, status, title: `${id} title`, acs: 0, open_questions: 0,
           tc: { active: 0, stale: 0, retired: 0 }, stale_causes: [], ...x }
}
function nrow(id: string, state: string, scope: 'story' | 'flow'): NextRow {
  return { id, state, command: null, skill: 'x', scope, arg: id }
}

const STATE = st({
  stories: [
    story('US-A', 'draft', { acs: 0 }),                                    // ingested
    story('US-C', 'in-alignment', { acs: 4, open_questions: 3 }),          // alignment
    story('US-E', 'aligned', { acs: 6 }),                                 // ready
    story('US-G', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } }), // generated + stale
  ],
  flows: [{ id: 'FLOW-pm', status: 'aligned' }],
  next: { banners: [], rows: [nrow('FLOW-pm', 'aligned · journey 6 entries · 0 UAT TCs', 'flow')] },
})

describe('PhaseKanban', () => {
  it('renders the four phase columns in order', () => {
    render(<PhaseKanban state={STATE} filter={null} />)
    const cols = screen.getAllByRole('region')
    expect(cols.map((c) => c.getAttribute('aria-label'))).toEqual([
      '① Ingested', '② In alignment', '③ Ready for generation', '④ Generated',
    ])
  })

  it('places each story in its computed column', () => {
    render(<PhaseKanban state={STATE} filter={null} />)
    const ready = screen.getByRole('region', { name: '③ Ready for generation' })
    expect(within(ready).getByText('US-E')).toBeInTheDocument()
    expect(within(ready).getByText('FLOW-pm')).toBeInTheDocument()
    const generated = screen.getByRole('region', { name: '④ Generated' })
    expect(within(generated).getByText('US-G')).toBeInTheDocument()
  })

  it('links a story card to its story view but leaves flow cards unlinked', () => {
    render(<PhaseKanban state={STATE} filter={null} />)
    expect(screen.getByRole('link', { name: /US-E/ })).toHaveAttribute('href', '#/story/US-E')
    expect(screen.queryByRole('link', { name: /FLOW-pm/ })).toBeNull()
  })

  it('shows a stale flag on a generated stale card', () => {
    render(<PhaseKanban state={STATE} filter={null} />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
  })

  it('filters cards when a filter is active', () => {
    render(<PhaseKanban state={STATE} filter="stale" />)
    expect(screen.getByText('US-G')).toBeInTheDocument()   // the only stale card
    expect(screen.queryByText('US-A')).toBeNull()
    expect(screen.queryByText('US-E')).toBeNull()
  })
})
