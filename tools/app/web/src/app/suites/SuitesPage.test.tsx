import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { State } from '../api'

const { getSuitePreview, runAction, runDownload, getWorkbooks, onChange } = vi.hoisted(() => ({
  getSuitePreview: vi.fn(async () => ({ count: 7, ids: ['a'], retired: 1, stale: 2 })),
  runAction: vi.fn(async () => ({ argv: [], rc: 0, stdout: '', stderr: '' })),
  runDownload: vi.fn(async () => {}),
  getWorkbooks: vi.fn(),
  onChange: vi.fn(() => () => {}),
}))
vi.mock('../api', () => ({
  getSuitePreview, runAction, runDownload, getWorkbooks, onChange,
  getWorkbookInventory: async () => ({ workbooks: await getWorkbooks(), skipped: [] }),
}))
import { SuitesPage } from './SuitesPage'

const state = {
  schema1: false, notice: null, project: 'p',
  prds: [
    { id: 'rental-application', title: 'Rental application', adopted: 2, staged: null },
    { id: 'rental-payment', title: 'Rental payment', adopted: 1, staged: 2 },
  ], stories: [], flows: [],
  cards: [], change_reports: [], totals: {}, next: { banners: [], rows: [] },
  suites: ['sit-vhld-p1', 'sit-all'],
  inventory: [{ file: 'sit-vhld-p1-latest.xlsx', story: null, kind: 'sit', mtime: '2026-08-10' }],
} as unknown as State

const BOOK = {
  name: 'sit-vhld-p1', kind: 'sit', file: 'sit-vhld-p1-latest.xlsx',
  compiled_at: '2026-10-04T10:15:00+08:00', source: { type: 'suite', name: 'sit-vhld-p1' },
  freshness: 'changed', changed_count: 2, versions: [], tcs: {},
}

beforeEach(() => {
  vi.clearAllMocks()
  // The inventory read never settles unless a test supplies it, so no state
  // update lands outside act() in the tests that do not look at it.
  getWorkbooks.mockImplementation(() => new Promise(() => {}))
})

describe('SuitesPage', () => {
  it('lists existing suites and states selection-is-never-generation', async () => {
    render(<SuitesPage state={state} />)
    expect(screen.getByText('sit-vhld-p1')).toBeInTheDocument()
    expect(screen.getByText('sit-all')).toBeInTheDocument()
    expect(screen.getByText(/selection is never generation/i)).toBeInTheDocument()
    // the docked chat is Off by default: the copy must not send the operator to it
    expect(screen.getByText(/ask the agent for/)).toBeInTheDocument()
    expect(screen.queryByText(/in chat/)).toBeNull()
    await screen.findByText('7') // let the preview read settle
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

  it('narrows the preview to one PRD', async () => {
    render(<SuitesPage state={state} />)
    fireEvent.change(screen.getByLabelText(/^PRD/), { target: { value: 'rental-payment' } })
    await waitFor(() =>
      expect(getSuitePreview).toHaveBeenCalledWith(
        expect.objectContaining({ include_prds: ['rental-payment'] })))
  })

  it('offers no PRD filter when no PRD is registered', async () => {
    render(<SuitesPage state={{ ...state, prds: [] }} />)
    expect(screen.queryByLabelText(/^PRD/)).toBeNull()
    await screen.findByText('7') // let the preview read settle
  })

  it('shows the backend message when the preview is refused', async () => {
    getSuitePreview.mockRejectedValueOnce(new Error("unknown PRD id 'nope'"))
    render(<SuitesPage state={state} />)
    expect(await screen.findByRole('alert')).toHaveTextContent("unknown PRD id 'nope'")
  })

  it('compiles a suite through the allowlisted action, never generating', async () => {
    render(<SuitesPage state={state} />)
    await screen.findByText('7') // let the preview read settle
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    expect(runAction).toHaveBeenCalledWith('suite_compile', { name: 'sit-vhld-p1' })
    await waitFor(() => expect(getWorkbooks).toHaveBeenCalledTimes(2))
    expect(screen.queryByText(/did not go through/)).toBeNull()
  })

  it('shows a refused compile in the command\'s own words, and clears it on the next try', async () => {
    runAction.mockResolvedValueOnce({
      argv: [], rc: 1, stdout: '', stderr: 'suite compile sit-vhld-p1 refused: 2 test case(s) not sealed.\n  Run: py tools/wiki.py seal',
    })
    render(<SuitesPage state={state} />)
    await screen.findByText('7')
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    expect(await screen.findByText(/refused: 2 test case\(s\) not sealed/)).toBeInTheDocument()
    expect(screen.getByText('Compile sit-vhld-p1 did not go through:')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    await waitFor(() => expect(screen.queryByText(/not sealed/)).toBeNull())
  })

  it('shows a compile the server would not run, and one that could not be sent', async () => {
    runAction.mockResolvedValueOnce({ error: 'action not on the allowlist' } as never)
    render(<SuitesPage state={state} />)
    await screen.findByText('7')
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    expect(await screen.findByText('action not on the allowlist')).toBeInTheDocument()
    runAction.mockRejectedValueOnce(new Error('network down'))
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    expect(await screen.findByText('network down')).toBeInTheDocument()
  })

  it('downloads a compiled workbook via runDownload (Plan 2)', async () => {
    render(<SuitesPage state={state} />)
    await screen.findByText('7') // let the preview read settle
    fireEvent.click(screen.getByRole('button', { name: /Download/ }))
    expect(runDownload).toHaveBeenCalledWith('sit-vhld-p1-latest.xlsx', {})
  })

  it('offers Open beside a suite that has a compiled workbook, and flags changes', async () => {
    getWorkbooks.mockResolvedValue([BOOK])
    render(<SuitesPage state={state} />)
    const open = await screen.findByRole('link', { name: 'Open sit-vhld-p1' })
    expect(open.getAttribute('href')).toBe('#/workbook/sit/sit-vhld-p1-latest.xlsx')
    expect(screen.getByText('2 changed')).toBeInTheDocument()
    // sit-all has never been compiled: nothing to open
    expect(screen.queryByRole('link', { name: 'Open sit-all' })).toBeNull()
  })

  it('offers Open beside Download on every compiled workbook', async () => {
    render(<SuitesPage state={state} />)
    await screen.findByText('7') // let the preview read settle
    expect(screen.getByRole('link', { name: 'Open sit-vhld-p1-latest.xlsx' }).getAttribute('href'))
      .toBe('#/workbook/sit/sit-vhld-p1-latest.xlsx')
  })

  it('re-reads the workbook inventory after a compile', async () => {
    getWorkbooks.mockResolvedValue([BOOK])
    render(<SuitesPage state={state} />)
    await screen.findByRole('link', { name: 'Open sit-vhld-p1' })
    expect(getWorkbooks).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getAllByRole('button', { name: 'Compile' })[0])
    await waitFor(() => expect(getWorkbooks).toHaveBeenCalledTimes(2))
    await screen.findByRole('link', { name: 'Open sit-vhld-p1' })
  })
})
