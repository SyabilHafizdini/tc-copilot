import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Dashboard } from './Dashboard'
import type { State } from '../api'

function st(over: Partial<State>): State {
  return {
    schema1: false, notice: null, project: 'DEMO', prds: [],
    stories: [], flows: [], cards: [], change_reports: [],
    totals: { tcs: 0 }, next: { banners: [], rows: [] }, inventory: [], suites: [], ...over,
  }
}
function story(id: string, status: string, x: Record<string, unknown> = {}) {
  return { id, status, title: `${id} title`, acs: 0, open_questions: 0,
           tc: { active: 0, stale: 0, retired: 0 }, stale_causes: [], ...x }
}

const STATE = st({
  stories: [
    story('US-A', 'draft', { acs: 0 }),                                    // ingested
    story('US-G', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } }), // generated + stale
  ],
  totals: { tcs: 40 },
})

describe('Dashboard', () => {
  it('renders the metric row and the phase board together', () => {
    render(<Dashboard state={STATE} />)
    expect(screen.getByText('Open questions')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '① Ingested' })).toBeInTheDocument()
    expect(screen.getByText('US-A')).toBeInTheDocument()
  })

  it('filters the board when a metric is clicked, and clears on a second click', () => {
    render(<Dashboard state={STATE} />)
    // Before filtering, the ingested card is visible.
    expect(screen.getByText('US-A')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Stale/i }))
    // Stale filter -> only the stale generated card remains.
    expect(screen.getByText('US-G')).toBeInTheDocument()
    expect(screen.queryByText('US-A')).toBeNull()
    // Clicking Stale again clears the filter.
    fireEvent.click(screen.getByRole('button', { name: /Stale/i }))
    expect(screen.getByText('US-A')).toBeInTheDocument()
  })

  it('lists the PRDs above the board', () => {
    render(<Dashboard state={st({ prds: [{ id: 'rental-payment', title: 'Rental payment', adopted: 1, staged: 2 }] })} />)
    expect(screen.getByRole('row', { name: /rental-payment/ })).toBeInTheDocument()
  })

  it('says no PRD is registered on a migrated project with none', () => {
    render(<Dashboard state={st({})} />)
    expect(screen.getByText('No PRD registered.')).toBeInTheDocument()
  })

  it('does not say "No PRD registered." on a project that is not migrated yet', () => {
    render(<Dashboard state={st({ schema1: true, notice: 'manifest.json is schema 1' })} />)
    expect(screen.getByText('PRD state is not shown until the project is migrated.')).toBeInTheDocument()
    expect(screen.queryByText('No PRD registered.')).toBeNull()
  })
})
