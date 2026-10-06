import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ReviewPanel } from '../testcases/ReviewPanel'
import { TestCaseGrid } from '../testcases/TestCaseGrid'
import { PAYLOAD, row } from '../testcases/fixtures'
import type { WorkbookEntry } from './types'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getWorkbooks: vi.fn(), onChange: vi.fn(() => () => {}), editTestCase: vi.fn() }
})
import * as api from '../api'

const HREF = '#/workbook/sit/demo-latest.xlsx?sheet=C-TC-1+%28Main+flow%29&row=12'
const REF = 'testcases/sit/rental-desk/1.1-AC02-01'

const book = (over: Partial<WorkbookEntry>): WorkbookEntry => ({
  name: 'demo', kind: 'sit', file: 'demo-latest.xlsx', compiled_at: '2026-10-04T10:15:00+08:00',
  source: null, freshness: 'fresh', changed_count: 0, versions: [], tcs: {}, ...over,
})

describe('ReviewPanel "open in workbook"', () => {
  it('links to the workbook row when workbookHref is given', () => {
    render(<ReviewPanel row={row()} onClose={() => {}} workbookHref={HREF} />)
    expect(screen.getByRole('link', { name: /open in workbook/i }).getAttribute('href')).toBe(HREF)
  })

  it('offers no workbook link when the test case is in no compiled workbook', () => {
    render(<ReviewPanel row={row()} onClose={() => {}} workbookHref={null} />)
    expect(screen.queryByRole('link', { name: /open in workbook/i })).toBeNull()
  })
})

describe('TestCaseGrid supplies the panel link', () => {
  beforeEach(() => { vi.mocked(api.getWorkbooks).mockReset() })

  const open = (container: HTMLElement, id: string) =>
    fireEvent.click(container.querySelector(`[data-tc="${id}"]`)!)

  it('points at the newest workbook that holds the test case, at its sheet and row', async () => {
    vi.mocked(api.getWorkbooks).mockResolvedValue([
      book({ file: 'new-latest.xlsx', tcs: { [REF]: { sheet: 'C-TC-1 (Main flow)', row: 12 } } }),
      book({ file: 'old-latest.xlsx', tcs: { [REF]: { sheet: 'Old', row: 3 } } }),
    ])
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    open(container, '1.1-AC02-01')
    await waitFor(() => expect(screen.getByRole('link', { name: /open in workbook/i }).getAttribute('href'))
      .toBe('#/workbook/sit/new-latest.xlsx?sheet=C-TC-1+%28Main+flow%29&row=12'))
  })

  it('stays inert when no workbook holds the test case', async () => {
    vi.mocked(api.getWorkbooks).mockResolvedValue([book({ tcs: { 'testcases/sit/x/other': { sheet: 'S', row: 9 } } })])
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    open(container, '1.1-AC02-01')
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(1))
    await act(async () => {})
    expect(screen.queryByRole('link', { name: /open in workbook/i })).toBeNull()
    expect(screen.getByText('Not in a compiled workbook')).toBeInTheDocument()
  })

  it('claims nothing about a workbook before the inventory has been read', () => {
    vi.mocked(api.getWorkbooks).mockReturnValue(new Promise(() => {}))
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    open(container, '1.1-AC02-01')
    expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
    expect(screen.queryByText(/workbook/i)).toBeNull()
  })

  it('re-reads the inventory when the panel opens, not on every row change', async () => {
    vi.mocked(api.getWorkbooks).mockResolvedValue([])
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(api.getWorkbooks).not.toHaveBeenCalled()
    open(container, '1.1-AC02-01')
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(1))
    await act(async () => {})
    open(container, '1.1-AC01-02')
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    await act(async () => {})
    expect(screen.getByLabelText(/^Review /)).toBeInTheDocument()
    expect(api.getWorkbooks).toHaveBeenCalledTimes(1)
    // closing and opening again is a new open: one more read
    fireEvent.keyDown(window, { key: 'Escape' })
    open(container, '1.1-AC02-01')
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(2))
    await act(async () => {})
  })

  it('keeps the previous links when a re-read fails', async () => {
    vi.mocked(api.getWorkbooks).mockResolvedValueOnce([
      book({ tcs: { [REF]: { sheet: 'S', row: 4 } } }),
    ])
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    open(container, '1.1-AC02-01')
    const link = () => screen.getByRole('link', { name: /open in workbook/i })
    await waitFor(() => expect(link().getAttribute('href')).toBe('#/workbook/sit/demo-latest.xlsx?sheet=S&row=4'))
    vi.mocked(api.getWorkbooks).mockRejectedValue(new Error('GET /api/workbooks -> 500'))
    fireEvent.keyDown(window, { key: 'Escape' })
    open(container, '1.1-AC02-01')
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(2))
    await act(async () => {})
    expect(link().getAttribute('href')).toBe('#/workbook/sit/demo-latest.xlsx?sheet=S&row=4')
  })

  it('still works when the inventory request fails', async () => {
    vi.mocked(api.getWorkbooks).mockRejectedValue(new Error('GET /api/workbooks -> 500'))
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    open(container, '1.1-AC02-01')
    expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalled())
    await act(async () => {})
    // a failed read is not "in no workbook": nothing is claimed either way
    expect(screen.queryByText(/workbook/i)).toBeNull()
  })
})
