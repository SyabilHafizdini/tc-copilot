import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PropertiesRail } from './PropertiesRail'
import type { Story } from './selectors'
import type { Field } from '../explorer/types'

const STORY: Story = {
  id: 'US-VHLD', title: 'Vehicle Holding', status: 'draft', module: 'm', acs: 25,
  open_questions: 0, asserted_by: null, tc: { active: 0, stale: 0, retired: 0 }, stale_causes: [],
  components: { total: 15, covered: 0, acs_without_tcs: 0, out_of_scope: 0, gaps: 15 },
}
const FIELDS: Field[] = [{ key: 'module', kind: 'link', ref: '/modules/production-monitoring.md', label: 'production-monitoring' }]

describe('PropertiesRail', () => {
  it('renders the status transitions, marking gated ones', () => {
    render(<PropertiesRail story={STORY} fields={FIELDS} onRun={vi.fn()} onNavigate={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'Assert alignment (gated)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Run lint' })).toBeInTheDocument()
  })

  it('firing a transition calls onRun with its action + params', () => {
    const onRun = vi.fn()
    render(<PropertiesRail story={STORY} fields={FIELDS} onRun={onRun} onNavigate={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: '0' } }) // first transition
    expect(onRun).toHaveBeenCalledWith('gate', { story: 'US-VHLD' })
  })

  it('renders the scoped coverage summary', () => {
    render(<PropertiesRail story={STORY} fields={FIELDS} onRun={vi.fn()} onNavigate={vi.fn()} />)
    expect(screen.getByText(/0\/15 covered/)).toBeInTheDocument()
    expect(screen.getByText(/15 gap/)).toBeInTheDocument()
  })

  it('renders the metadata fields via FrontmatterFields', () => {
    const onNavigate = vi.fn()
    render(<PropertiesRail story={STORY} fields={FIELDS} onRun={vi.fn()} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('button', { name: 'production-monitoring' }))
    expect(onNavigate).toHaveBeenCalledWith('modules/production-monitoring')
  })
})
