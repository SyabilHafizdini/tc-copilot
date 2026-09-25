import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { State } from '../api'

const { getSuitePreview, runAction, runDownload } = vi.hoisted(() => ({
  getSuitePreview: vi.fn(async () => ({ count: 7, ids: ['a'], retired: 1, stale: 2 })),
  runAction: vi.fn(async () => ({ argv: [], rc: 0, stdout: '', stderr: '' })),
  runDownload: vi.fn(async () => {}),
}))
vi.mock('../api', () => ({ getSuitePreview, runAction, runDownload }))
import { SuitesPage } from './SuitesPage'

const state = {
  project: 'p', prd: { adopted: '0.3', staged: null }, stories: [], flows: [],
  cards: [], change_reports: [], totals: {}, next: { banners: [], rows: [] },
  suites: ['sit-vhld-p1', 'sit-all'],
  inventory: [{ file: 'sit-vhld-p1-latest.xlsx', story: null, kind: 'sit', mtime: '2026-08-10' }],
} as unknown as State

beforeEach(() => { vi.clearAllMocks() })

describe('SuitesPage', () => {
  it('lists existing suites and states selection-is-never-generation', () => {
    render(<SuitesPage state={state} />)
    expect(screen.getByText('sit-vhld-p1')).toBeInTheDocument()
    expect(screen.getByText('sit-all')).toBeInTheDocument()
    expect(screen.getByText(/selection is never generation/i)).toBeInTheDocument()
  })

  it('shows the resolved TC-count preview and refreshes it on filter change', async () => {
    render(<SuitesPage state={state} />)
    await waitFor(() => expect(screen.getByText('7')).toBeInTheDocument())
    expect(screen.getByText(/test cases resolved/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Priority/i), { target: { value: 'P1' } })
    await waitFor(() =>
      expect(getSuitePreview).toHaveBeenCalledWith(
        expect.objectContaining({ priorities: ['P1'] })))
  })

  it('compiles a suite through the allowlisted action, never generating', () => {
    render(<SuitesPage state={state} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    expect(runAction).toHaveBeenCalledWith('suite_compile', { name: 'sit-vhld-p1' })
  })

  it('downloads a compiled workbook via runDownload (Plan 2)', () => {
    render(<SuitesPage state={state} />)
    fireEvent.click(screen.getByRole('button', { name: /Download/ }))
    expect(runDownload).toHaveBeenCalledWith('sit-vhld-p1-latest.xlsx', {})
  })
})
