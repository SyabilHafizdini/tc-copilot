import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MetricCards } from './MetricCards'
import type { State } from '../api'

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

const STATE = st({
  stories: [
    story('US-C', 'in-alignment', { acs: 4, open_questions: 3 }),
    story('US-E', 'aligned', { acs: 6 }),
    story('US-G', 'aligned', { tc: { active: 10, stale: 2, retired: 0 } }),
  ],
  totals: { tcs: 91 },
})

describe('MetricCards', () => {
  it('renders all five metrics with their labels and values', () => {
    render(<MetricCards state={STATE} active={null} onFilter={vi.fn()} />)
    expect(screen.getByText('Open questions')).toBeInTheDocument()
    expect(screen.getByText('Ready to generate')).toBeInTheDocument()
    expect(screen.getByText('Test cases')).toBeInTheDocument()
    expect(screen.getByText('91')).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(5)
  })

  it('marks attention metrics with a tone class', () => {
    const { container } = render(<MetricCards state={STATE} active={null} onFilter={vi.fn()} />)
    expect(container.querySelector('.metric.critical')).not.toBeNull() // open questions
    expect(container.querySelector('.metric.attn')).not.toBeNull()     // ready / alignment
  })

  it('calls onFilter with the metric key when clicked', () => {
    const onFilter = vi.fn()
    render(<MetricCards state={STATE} active={null} onFilter={onFilter} />)
    fireEvent.click(screen.getByRole('button', { name: /Stale/i }))
    expect(onFilter).toHaveBeenCalledWith('stale')
  })

  it('reflects the active filter via aria-pressed', () => {
    render(<MetricCards state={STATE} active="stale" onFilter={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Stale/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Open questions/i })).toHaveAttribute('aria-pressed', 'false')
  })
})
