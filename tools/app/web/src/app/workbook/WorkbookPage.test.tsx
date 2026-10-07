import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MAIN, REF_1, REF_2, entry, payload } from './fixture'
import type { WbSkipped, WorkbookPayload } from './types'
import { setUnsavedDraft } from '../shell/unsaved'

const api = vi.hoisted(() => ({
  getWorkbook: vi.fn(),
  getWorkbooks: vi.fn(),
  getTestCases: vi.fn(),
  runAction: vi.fn(),
  runDownload: vi.fn(async () => {}),
  onChange: vi.fn((_cb: () => void) => () => {}),
  skipped: [] as WbSkipped[],
}))
// The page reads the inventory with what it skipped; the tests keep steering
// (and counting) the plain list.
vi.mock('../api', () => ({
  ...api,
  getWorkbookInventory: async () => ({ workbooks: await api.getWorkbooks(), skipped: api.skipped }),
}))

// The review panel belongs to the test-case-review-view plan; only its fixed
// props are exercised here.
vi.mock('../testcases/ReviewPanel', () => ({
  ReviewPanel: ({ row, onClose, onNavigate, workbookHref }: {
    row: { display_id: string }; onClose: () => void
    onNavigate?: (dir: -1 | 1) => void; workbookHref?: string | null
  }) => (
    <aside data-testid="panel" data-href={String(workbookHref)}>
      <span>panel:{row.display_id}</span>
      <button onClick={() => onNavigate?.(1)}>next</button>
      <button onClick={() => onNavigate?.(-1)}>prev</button>
      <button onClick={onClose}>close</button>
    </aside>
  ),
}))

import { WorkbookPage } from './WorkbookPage'

const ok = { argv: [], rc: 0, stdout: '', stderr: '' }

function setup(book: WorkbookPayload = payload()) {
  api.getWorkbook.mockResolvedValue(book)
  api.getWorkbooks.mockResolvedValue([entry()])
  api.getTestCases.mockResolvedValue({
    rows: [
      { ref: REF_1, id: '1.1-AC01-01', display_id: 'TC-1.1-AC01-01' },
      { ref: REF_2, id: '1.1-AC01-02', display_id: 'TC-1.1-AC01-02' },
    ],
    groups: [],
  })
  api.runAction.mockResolvedValue(ok)
}

beforeEach(() => { vi.clearAllMocks(); api.skipped = []; window.location.hash = '' })
afterEach(() => {
  window.location.hash = ''
  act(() => setUnsavedDraft('test-draft', false))
  vi.restoreAllMocks()
})

// What an open PartEditor with typed text reports (the panel is mocked here).
const typing = () => act(() => setUnsavedDraft('test-draft', true))

const page = (props: Partial<Parameters<typeof WorkbookPage>[0]> = {}) =>
  render(<WorkbookPage wbKind="sit" file="demo-latest.xlsx" {...props} />)

describe('WorkbookPage', () => {
  it('shows the tabs in file order and opens on the first test case sheet', async () => {
    setup()
    page()
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual([MAIN, 'Doubts'])
    expect(screen.getByRole('tab', { name: MAIN })).toHaveAttribute('aria-selected', 'true')
    expect(api.getWorkbook).toHaveBeenCalledWith('sit', 'demo-latest.xlsx')
  })

  it('puts the selected tab in the URL and draws the sheet the URL names', async () => {
    setup()
    const { rerender } = page()
    fireEvent.click(await screen.findByRole('tab', { name: 'Doubts' }))
    expect(window.location.hash).toBe('#/workbook/sit/demo-latest.xlsx?sheet=Doubts')
    rerender(<WorkbookPage wbKind="sit" file="demo-latest.xlsx" sheet="Doubts" />)
    expect(screen.getByRole('tab', { name: 'Doubts' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('Which value?')).toBeInTheDocument()
  })

  it('falls back to the first test case sheet for a sheet name the file lacks', async () => {
    setup()
    page({ sheet: 'C-TC-9 (Renamed run)', row: 400 })
    expect(await screen.findByRole('tab', { name: MAIN })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens the review panel on a row click, steps through rows and closes', async () => {
    setup()
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(await screen.findByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    // on the Workbook page itself the panel is told nothing about a workbook
    // link, so it shows none (not an inert one)
    expect(screen.getByTestId('panel').dataset.href).toBe('undefined')
    fireEvent.click(screen.getByRole('button', { name: 'next' }))
    expect(screen.getByText('panel:TC-1.1-AC01-02')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'next' }))      // already the last row
    expect(screen.getByText('panel:TC-1.1-AC01-02')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'prev' }))
    expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'close' }))
    expect(screen.queryByTestId('panel')).toBeNull()
    // focus is back on the sheet row the panel was opened from
    expect(document.activeElement).toBe(container.querySelector('tr[data-row="3"]'))
  })

  it('does not say a test case is gone while the test cases are still being read', async () => {
    setup()
    let arrive!: (p: unknown) => void
    api.getTestCases.mockReturnValue(new Promise((res) => { arrive = res }))
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(await screen.findByRole('status', { name: 'Loading test case' })).toBeInTheDocument()
    expect(screen.queryByText(/no longer in the wiki/)).toBeNull()
    arrive({ rows: [{ ref: REF_1, id: '1.1-AC01-01', display_id: 'TC-1.1-AC01-01' }], groups: [] })
    expect(await screen.findByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading test case' })).toBeNull()
  })

  it('shows the error, not "no longer in the wiki", when the test cases cannot be read', async () => {
    setup()
    api.getTestCases.mockRejectedValue(new Error('GET /api/testcases -> 500'))
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(await screen.findByText(/could not be opened: the test cases could not be read \(GET \/api\/testcases -> 500\)/))
      .toBeInTheDocument()
    expect(screen.queryByText(/no longer in the wiki/)).toBeNull()
  })

  it('keeps the rows it holds when a later read of the test cases fails', async () => {
    setup()
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    await screen.findByText('panel:TC-1.1-AC01-01')
    api.getTestCases.mockRejectedValue(new Error('GET /api/testcases -> 500'))
    api.onChange.mock.calls[0][0]()
    await waitFor(() => expect(api.getTestCases).toHaveBeenCalledTimes(2))
    await new Promise((r) => setTimeout(r, 10))
    expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    expect(screen.queryByText(/no longer in the wiki/)).toBeNull()
  })

  describe('with unsaved text in the panel', () => {
    it('another row asks first; "no" keeps the panel on its row', async () => {
      setup()
      const { container } = page()
      await screen.findAllByRole('tab')
      fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
      await screen.findByText('panel:TC-1.1-AC01-01')
      typing()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      fireEvent.click(container.querySelector('td[data-cell="4:2"]')!)
      expect(confirm).toHaveBeenCalledTimes(1)
      expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
      // the row already open is not a move
      fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
      expect(confirm).toHaveBeenCalledTimes(1)
      confirm.mockReturnValue(true)
      fireEvent.click(container.querySelector('td[data-cell="4:2"]')!)
      expect(screen.getByText('panel:TC-1.1-AC01-02')).toBeInTheDocument()
    })

    it('another sheet tab asks first; "no" changes neither the panel nor the address', async () => {
      setup()
      const { container } = page()
      await screen.findAllByRole('tab')
      fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
      await screen.findByText('panel:TC-1.1-AC01-01')
      typing()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      fireEvent.click(screen.getByRole('tab', { name: 'Doubts' }))
      expect(confirm).toHaveBeenCalledTimes(1)
      expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
      expect(window.location.hash).toBe('')
      // the tab already shown asks nothing and keeps the panel
      fireEvent.click(screen.getByRole('tab', { name: MAIN }))
      expect(confirm).toHaveBeenCalledTimes(1)
      confirm.mockReturnValue(true)
      fireEvent.click(screen.getByRole('tab', { name: 'Doubts' }))
      expect(screen.queryByTestId('panel')).toBeNull()
      expect(window.location.hash).toBe('#/workbook/sit/demo-latest.xlsx?sheet=Doubts')
    })

    it('a re-read that drops the test case from the sheet or the wiki keeps the panel mounted', async () => {
      setup()
      const { container } = page()
      await screen.findAllByRole('tab')
      fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
      const panel = await screen.findByTestId('panel')
      typing()
      // recompiled without this test case, and retired in the wiki
      const book = payload()
      book.sheets[0].rows[2] = { ...book.sheets[0].rows[2], tc: null }
      api.getWorkbook.mockResolvedValue(book)
      api.getTestCases.mockResolvedValue({ rows: [], groups: [] })
      api.onChange.mock.calls[0][0]()
      await waitFor(() => expect(api.getWorkbook).toHaveBeenCalledTimes(2))
      await new Promise((r) => setTimeout(r, 10))
      expect(screen.getByTestId('panel')).toBe(panel)
      expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
      expect(screen.queryByText(/no longer in the wiki/)).toBeNull()
    })
  })

  it('keeps the open panel when the already-active tab is clicked', async () => {
    setup()
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(await screen.findByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: MAIN }))
    expect(screen.getByText('panel:TC-1.1-AC01-01')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Doubts' }))
    expect(screen.queryByTestId('panel')).toBeNull()
  })

  it('offers no panel for a TC- row the read model could not link', async () => {
    const book = payload()
    book.sheets[0].rows[2] = { ...book.sheets[0].rows[2], tc: null }
    setup(book)
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(screen.queryByTestId('panel')).toBeNull()
    // The linked row below it still opens, and "prev" stops at the first linked row.
    fireEvent.click(container.querySelector('td[data-cell="4:2"]')!)
    expect(await screen.findByText('panel:TC-1.1-AC01-02')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'prev' }))
    expect(screen.getByText('panel:TC-1.1-AC01-02')).toBeInTheDocument()
  })

  it('keeps the open panel mounted when the wiki changes and the file is re-read', async () => {
    setup()
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    const panel = await screen.findByTestId('panel')
    const fire = api.onChange.mock.calls[0][0]
    api.getWorkbook.mockResolvedValue(payload({ freshness: 'changed', changed_count: 1 }))
    fire()
    await screen.findByText('1 test case changed since this workbook was compiled')
    expect(screen.getByTestId('panel')).toBe(panel)
  })

  it('keeps the page and the panel when a re-read fails', async () => {
    setup()
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    await screen.findByTestId('panel')
    api.getWorkbook.mockRejectedValue(new Error('cannot read demo-latest.xlsx: BadZipFile'))
    api.onChange.mock.calls[0][0]()
    await waitFor(() => expect(api.getWorkbook).toHaveBeenCalledTimes(2))
    expect(screen.getByTestId('panel')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: MAIN })).toBeInTheDocument()
  })

  it('says so when the clicked test case is no longer in the wiki', async () => {
    setup()
    api.getTestCases.mockResolvedValue({ rows: [], groups: [] })
    const { container } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    expect(await screen.findByText(/1\.1-AC01-01 is no longer in the wiki/)).toBeInTheDocument()
  })

  it('shows no banner for a fresh workbook', async () => {
    setup()
    page()
    await screen.findAllByRole('tab')
    expect(screen.queryByRole('button', { name: 'Recompile' })).toBeNull()
    expect(screen.queryByText(/changed since this workbook was compiled/)).toBeNull()
  })

  it('counts the changed test cases and recompiles the suite, then re-reads the file', async () => {
    setup(payload({ freshness: 'changed', changed_count: 2 }))
    page()
    expect(await screen.findByText('2 test cases changed since this workbook was compiled'))
      .toBeInTheDocument()
    api.getWorkbook.mockResolvedValue(payload())
    fireEvent.click(screen.getByRole('button', { name: 'Recompile' }))
    await waitFor(() => expect(api.runAction).toHaveBeenCalledWith('suite_compile', { name: 'demo' }))
    await waitFor(() => expect(api.getWorkbook).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByText(/changed since this workbook/)).toBeNull())
  })

  it('uses the singular for one changed test case', async () => {
    setup(payload({ freshness: 'changed', changed_count: 1 }))
    page()
    expect(await screen.findByText('1 test case changed since this workbook was compiled'))
      .toBeInTheDocument()
  })

  it('shows a refusal verbatim and keeps the workbook on screen', async () => {
    setup(payload({ freshness: 'changed', changed_count: 1 }))
    api.runAction.mockResolvedValue({ argv: [], rc: 1, stdout: '', stderr: 'suite compile demo refused: 1 test case(s) not sealed.' })
    page()
    fireEvent.click(await screen.findByRole('button', { name: 'Recompile' }))
    expect(await screen.findByText(/refused: 1 test case\(s\) not sealed/)).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: MAIN })).toBeInTheDocument()
    expect(api.getWorkbook).toHaveBeenCalledTimes(1)
  })

  it('recompiles an export with its recorded story and name', async () => {
    setup(payload({
      name: 'US-X-sit', file: 'US-X-sit-latest.xlsx', freshness: 'changed', changed_count: 1,
      source: { type: 'export', name: 'US-X-sit', story: 'US-X' },
    }))
    page({ file: 'US-X-sit-latest.xlsx' })
    fireEvent.click(await screen.findByRole('button', { name: 'Recompile' }))
    await waitFor(() =>
      expect(api.runAction).toHaveBeenCalledWith('export', { story: 'US-X', name: 'US-X-sit' }))
  })

  it('offers no Recompile for an export that recorded no story', async () => {
    setup(payload({
      freshness: 'changed', changed_count: 1,
      source: { type: 'export', name: 'demo' },
    }))
    page()
    await screen.findByText('1 test case changed since this workbook was compiled')
    expect(screen.queryByRole('button', { name: 'Recompile' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
  })

  it('moves to the -latest file after recompiling from a timestamped one', async () => {
    setup(payload({ file: 'demo_20261003-090000.xlsx', freshness: 'unknown' }))
    page({ file: 'demo_20261003-090000.xlsx' })
    fireEvent.click(await screen.findByRole('button', { name: 'Recompile' }))
    await waitFor(() => expect(window.location.hash).toBe(
      '#/workbook/sit/demo-latest.xlsx?sheet=C-TC-1+%28Main+flow%29'))
  })

  it('offers only Download when freshness is unknown and no source is known', async () => {
    setup(payload({ freshness: 'unknown', source: null }))
    page()
    expect(await screen.findByText('freshness unknown — recompile to track changes'))
      .toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Recompile' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Download' }))
    expect(api.runDownload).toHaveBeenCalledWith('sit/demo-latest.xlsx')
  })

  it('switches compile from the version picker', async () => {
    setup()
    page()
    const compile = await screen.findByLabelText(/Compile/)
    expect([...compile.querySelectorAll('option')].map((o) => o.getAttribute('value')))
      .toEqual(['demo-latest.xlsx', 'demo_20261003-090000.xlsx'])
    fireEvent.change(compile, { target: { value: 'demo_20261003-090000.xlsx' } })
    expect(window.location.hash).toBe('#/workbook/sit/demo_20261003-090000.xlsx')
  })

  it('switches workbook from the name picker', async () => {
    setup()
    api.getWorkbooks.mockResolvedValue([
      entry(), entry({ name: 'uat-all', kind: 'uat', file: 'uat-all-latest.xlsx' })])
    page()
    const name = await screen.findByLabelText(/Workbook/)
    await waitFor(() => expect(name.querySelectorAll('option')).toHaveLength(2))
    fireEvent.change(name, { target: { value: 'uat/uat-all' } })
    expect(window.location.hash).toBe('#/workbook/uat/uat-all-latest.xlsx')
  })

  it('lands on the newest workbook from a bare #/workbook', async () => {
    setup()
    page({ wbKind: '', file: '' })
    await waitFor(() => expect(window.location.hash).toBe('#/workbook/sit/demo-latest.xlsx'))
    expect(api.getWorkbook).not.toHaveBeenCalled()
  })

  it('says nothing is compiled when the inventory is empty', async () => {
    setup()
    api.getWorkbooks.mockResolvedValue([])
    page({ wbKind: '', file: '' })
    expect(await screen.findByText(/Nothing compiled yet/)).toBeInTheDocument()
  })

  it('shows the error, not "Nothing compiled yet", when the inventory cannot be read', async () => {
    setup()
    api.getWorkbooks.mockRejectedValue(new Error('manifest.json has schema_version \'two\''))
    page({ wbKind: '', file: '' })
    expect(await screen.findByText(/could not be listed: manifest\.json has schema_version 'two'/))
      .toBeInTheDocument()
    expect(screen.queryByText(/Nothing compiled yet/)).toBeNull()
  })

  it('names the files the inventory could not read', async () => {
    setup()
    api.skipped = [{ kind: 'sit', file: 'broken-latest.xlsx', error: 'cannot read broken-latest.xlsx: BadZipFile' }]
    page()
    await screen.findAllByRole('tab')
    expect(await screen.findByText('sit/broken-latest.xlsx: cannot read broken-latest.xlsx: BadZipFile'))
      .toBeInTheDocument()
  })

  it('replaces the bare route instead of pushing over it, so Back does not bounce', async () => {
    setup()
    window.location.hash = '#/workbook'
    const entries = window.history.length
    page({ wbKind: '', file: '' })
    await waitFor(() => expect(window.location.hash).toBe('#/workbook/sit/demo-latest.xlsx'))
    // an assignment would have added a history entry on top of the bare route
    expect(window.history.length).toBe(entries)
  })

  it('shows the error, not a skeleton, when a re-read fails while the first read is still pending', async () => {
    setup()
    let late!: (b: WorkbookPayload) => void
    api.getWorkbook.mockReturnValueOnce(new Promise<WorkbookPayload>((res) => { late = res }))
    page()
    await waitFor(() => expect(api.getWorkbook).toHaveBeenCalledTimes(1))
    api.getWorkbook.mockRejectedValueOnce(new Error('cannot read demo-latest.xlsx: BadZipFile'))
    api.onChange.mock.calls[0][0]()
    late(payload())
    expect(await screen.findByText(/cannot read demo-latest\.xlsx: BadZipFile/)).toBeInTheDocument()
  })

  for (const outcome of ['success', 'refusal'] as const) {
    it(`ignores a recompile that settles after the operator moved to another workbook (${outcome})`, async () => {
      setup(payload({ freshness: 'changed', changed_count: 1 }))
      api.getWorkbook.mockImplementation(async (_k: string, f: string) =>
        f === 'other-latest.xlsx'
          ? payload({ name: 'other', file: f, freshness: 'changed', changed_count: 1,
              source: { type: 'suite', name: 'other' } })
          : payload({ freshness: 'changed', changed_count: 1 }))
      let settle!: (r: unknown) => void
      api.runAction.mockReturnValueOnce(new Promise((res) => { settle = res }))
      const { rerender } = page()
      fireEvent.click(await screen.findByRole('button', { name: 'Recompile' }))
      window.location.hash = ''
      rerender(<WorkbookPage wbKind="sit" file="other-latest.xlsx" />)
      await screen.findByRole('heading', { name: 'other' })
      settle(outcome === 'success'
        ? ok
        : { argv: [], rc: 1, stdout: '', stderr: 'suite compile demo refused: nope' })
      await waitFor(() => expect(api.getWorkbooks).toHaveBeenCalledTimes(outcome === 'success' ? 2 : 1))
      await new Promise((r) => setTimeout(r, 20))
      expect(window.location.hash).toBe('')
      expect(screen.queryByText(/refused: nope/)).toBeNull()
      expect(screen.getByRole('button', { name: 'Recompile' })).toBeInTheDocument()
    })
  }

  it('does not bring a closed panel back after switching tabs and returning', async () => {
    setup()
    const { container, rerender } = page()
    await screen.findAllByRole('tab')
    fireEvent.click(container.querySelector('td[data-cell="3:2"]')!)
    await screen.findByTestId('panel')
    fireEvent.click(screen.getByRole('tab', { name: 'Doubts' }))
    rerender(<WorkbookPage wbKind="sit" file="demo-latest.xlsx" sheet="Doubts" />)
    rerender(<WorkbookPage wbKind="sit" file="demo-latest.xlsx" sheet={MAIN} />)
    await screen.findByRole('tab', { name: MAIN })
    expect(screen.queryByTestId('panel')).toBeNull()
  })

  it("shows the server's words when the file cannot be read", async () => {
    setup()
    api.getWorkbook.mockRejectedValue(new Error('cannot read demo-latest.xlsx: BadZipFile'))
    page()
    expect(await screen.findByText(/cannot read demo-latest\.xlsx: BadZipFile/)).toBeInTheDocument()
  })
})
