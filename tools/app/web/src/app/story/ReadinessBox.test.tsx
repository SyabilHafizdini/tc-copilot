import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ReadinessBox } from './ReadinessBox'
import type { Story } from './selectors'

const READY: Story = {
  id: 'US-VHLD', title: 'Vehicle Holding', status: 'aligned', module: 'm', acs: 25,
  open_questions: 0, asserted_by: 'syabz', tc: { active: 39, stale: 0, retired: 0 }, stale_causes: [],
  components: { total: 15, covered: 13, acs_without_tcs: 0, out_of_scope: 2, gaps: 0 },
}
const BLOCKED: Story = { ...READY, status: 'draft', asserted_by: null, tc: { active: 0, stale: 0, retired: 0 },
  components: { total: 15, covered: 0, acs_without_tcs: 0, out_of_scope: 0, gaps: 15 } }

describe('ReadinessBox', () => {
  it('shows the sealed verdict and the four gate rollups when ready', () => {
    render(<ReadinessBox story={READY} onRun={vi.fn()} onExport={vi.fn()} />)
    expect(screen.getByText(/ready to export/i)).toBeInTheDocument()
    expect(screen.getByText('aligned')).toBeInTheDocument()
    expect(screen.getByText('coverage')).toBeInTheDocument()
    expect(screen.getByText('lint')).toBeInTheDocument()
    expect(screen.getByText('asserted')).toBeInTheDocument()
  })

  it('fires onExport with the export params when the Export button is clicked', () => {
    const onExport = vi.fn()
    render(<ReadinessBox story={READY} onRun={vi.fn()} onExport={onExport} />)
    fireEvent.click(screen.getByRole('button', { name: /Export/ }))
    expect(onExport).toHaveBeenCalledWith('export', { story: 'US-VHLD', name: 'US-VHLD-sit' })
  })

  it('shows the single blocker and fires the gate next-action when not ready', () => {
    const onRun = vi.fn()
    render(<ReadinessBox story={BLOCKED} onRun={onRun} onExport={vi.fn()} />)
    expect(screen.getByText("Not aligned — status 'draft'")).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Run gate check' }))
    expect(onRun).toHaveBeenCalledWith('gate', { story: 'US-VHLD' })
  })
})
