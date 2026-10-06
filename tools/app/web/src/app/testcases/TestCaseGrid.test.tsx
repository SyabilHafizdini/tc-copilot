import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { TestCaseGrid } from './TestCaseGrid'
import { PAYLOAD } from './fixtures'
import type { TestCasesPayload } from './types'
import { getState } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual, editTestCase: vi.fn(), getWorkbooks: vi.fn(() => new Promise(() => {})),
    getState: vi.fn(() => Promise.reject(new Error('no state'))),
  }
})

afterEach(() => {
  window.location.hash = ''
  vi.mocked(getState).mockClear()
  vi.restoreAllMocks()
})

// Open a row's Test Steps editor and type into it: the panel now holds unsaved text.
function typeDraft(container: HTMLElement, id: string, text = 'my draft') {
  fireEvent.click(container.querySelector(`[data-tc="${id}"]`)!)
  fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Test Steps' }), { target: { value: text } })
}

// Two PRDs: 1.1-AC01-01 draws on rental-payment, 1.1-AC02-01 on rental-application,
// 1.1-AC01-02 on both, the rest on none.
const PRD_PAYLOAD: TestCasesPayload = {
  ...PAYLOAD,
  rows: PAYLOAD.rows.map((r) => ({
    ...r,
    prds: ({ '1.1-AC01-01': ['rental-payment'], '1.1-AC02-01': ['rental-application'],
      '1.1-AC01-02': ['rental-application', 'rental-payment'] } as Record<string, string[]>)[r.id] ?? [],
  })),
}
const ids = (container: HTMLElement) =>
  [...container.querySelectorAll('tr.tc-row')].map((tr) => tr.getAttribute('data-tc'))

// First-column text of every body row, in DOM order.
const firstCells = (container: HTMLElement) =>
  [...container.querySelectorAll('tbody tr:not(.tc-common-row)')].map((tr) => tr.querySelector('td')!.textContent!.trim())

describe('TestCaseGrid', () => {
  it('has the workbook columns', () => {
    render(<TestCaseGrid payload={PAYLOAD} />)
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['ID', 'Scenario', 'Test Steps', 'Field / Values', 'Expected Results', 'Confidence', 'Remarks'])
  })

  it('groups rows per run / flow with a Section row where the section changes', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(firstCells(container)).toEqual([
      'Run: Main flow SIT',
      'Section: Login', 'TC-1.1-AC01-01',
      'Section: Self-check', 'TC-1.1-AC02-01', 'TC-1.1-AC02-02stale',
      'Run: Variant flow SIT',
      'Section: Login', 'TC-1.1-AC01-02',
      'Flow: Rental journey UAT',
      'Section: Login', 'TC-1.1-AC01-01',
    ])
  })

  it('shows the workbook cells with bold rendered and the overall level as a tag', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    const tr = container.querySelector('[data-tc="1.1-AC02-01"]') as HTMLElement
    const cells = tr.querySelectorAll('td')
    expect(cells[2].textContent).toContain('Continue from TC-1.1-AC01-01: Tenant logged in.')
    expect(cells[2].querySelector('strong')?.textContent).toBe('Login')
    expect(cells[4].textContent).toContain('a. Button : Login')
    expect(within(cells[5] as HTMLElement).getByText('Medium').className).toContain('conf-tag medium')
  })

  it('filters by level, confidence, status and group, and counts what is shown', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(screen.getByText('5 of 5 test cases')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'UAT' }))
    expect(firstCells(container)).toEqual(['Flow: Rental journey UAT', 'Section: Login', 'TC-1.1-AC01-01'])
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))
    expect(screen.getByText('1 of 5 test cases')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), { target: { value: 'stale' } })
    expect(firstCells(container)).toEqual(['Run: Main flow SIT', 'Section: Self-check', 'TC-1.1-AC02-02stale'])
    fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), { target: { value: '' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Run or flow' }), { target: { value: 'run:sit:Variant flow' } })
    expect(screen.getByText('1 of 5 test cases')).toBeInTheDocument()
  })

  it('shows no PRD filter when no test case draws on a PRD', () => {
    render(<TestCaseGrid payload={PAYLOAD} />)
    expect(screen.queryByRole('group', { name: 'PRD' })).toBeNull()
    expect(getState).not.toHaveBeenCalled()
  })

  it('filters the grid by PRD chips (any selected PRD), combines with the other filters and clears', () => {
    const { container } = render(<TestCaseGrid payload={PRD_PAYLOAD} />)
    const group = screen.getByRole('group', { name: 'PRD' })
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['rental-application', 'rental-payment'])
    fireEvent.click(within(group).getByRole('button', { name: 'rental-payment' }))
    expect(ids(container)).toEqual(['1.1-AC01-01', '1.1-AC01-02'])
    expect(screen.getByText('2 of 5 test cases')).toBeInTheDocument()
    fireEvent.click(within(group).getByRole('button', { name: 'rental-application' }))
    expect(ids(container)).toEqual(['1.1-AC01-01', '1.1-AC02-01', '1.1-AC01-02'])
    fireEvent.click(within(group).getByRole('button', { name: 'rental-application' }))
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))
    expect(ids(container)).toEqual(['1.1-AC01-01'])
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))
    fireEvent.click(within(group).getByRole('button', { name: 'rental-payment' }))
    expect(ids(container)).toHaveLength(5)
  })

  it('keeps every chip when another filter hides its rows, and starts filtered from initialFilters', () => {
    const { container } = render(<TestCaseGrid payload={PRD_PAYLOAD} initialFilters={{ prds: ['rental-application'], level: 'uat' }} />)
    expect(ids(container)).toEqual([])
    expect(within(screen.getByRole('group', { name: 'PRD' })).getAllByRole('button')).toHaveLength(2)
  })

  it('writes the PRD selection to the hash and reads it back; an unknown id is ignored', () => {
    window.location.hash = '#/testcases?prd=rental-payment'
    const first = render(<TestCaseGrid payload={PRD_PAYLOAD} />)
    expect(ids(first.container)).toEqual(['1.1-AC01-01', '1.1-AC01-02'])
    fireEvent.click(screen.getByRole('button', { name: 'rental-application' }))
    expect(window.location.hash).toBe('#/testcases?prd=rental-application%2Crental-payment')
    first.unmount()

    window.location.hash = '#/testcases?prd=rental-nope'
    const second = render(<TestCaseGrid payload={PRD_PAYLOAD} />)
    expect(ids(second.container)).toHaveLength(5)
    expect(window.location.hash).toBe('#/testcases')
    second.unmount()
  })

  it('labels the chips with the PRD titles from the project state', async () => {
    vi.mocked(getState).mockResolvedValueOnce({
      prds: [{ id: 'rental-payment', title: 'Rental payment', adopted: 1, staged: null }],
    } as Awaited<ReturnType<typeof getState>>)
    render(<TestCaseGrid payload={PRD_PAYLOAD} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Rental payment' }))
    expect(screen.getByRole('button', { name: 'rental-application' })).toBeInTheDocument()
    expect(screen.getByText('2 of 5 test cases')).toBeInTheDocument()
  })

  it('says so when nothing matches', () => {
    render(<TestCaseGrid payload={PAYLOAD} initialFilters={{ story: 'US-NOPE' }} />)
    expect(screen.getByText('No test cases match these filters.')).toBeInTheDocument()
  })

  it('an empty payload says there are no test cases yet, not that a filter hid them', () => {
    render(<TestCaseGrid payload={{ rows: [], groups: [] }} />)
    expect(screen.getByText('No test cases yet.')).toBeInTheDocument()
    expect(screen.queryByText('No test cases match these filters.')).toBeNull()
    expect(screen.getByText('0 of 0 test cases')).toBeInTheDocument()
  })

  it('a story with no test cases says so', () => {
    render(<TestCaseGrid payload={PAYLOAD} lockStory="US-NEW-001" />)
    expect(screen.getByText('This story has no test cases yet.')).toBeInTheDocument()
    expect(screen.queryByText('No test cases match these filters.')).toBeNull()
  })

  it('re-reads the filters when the hash changes while the grid is on screen', () => {
    window.location.hash = '#/testcases'
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(ids(container)).toHaveLength(5)
    act(() => {
      window.location.hash = '#/testcases?level=sit&confidence=Medium'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(ids(container)).toEqual(['1.1-AC02-01'])
    expect(screen.getByRole('button', { name: 'SIT' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Medium' })).toHaveAttribute('aria-pressed', 'true')
    // every key the hash carries is read: status, story, group and prd too
    act(() => {
      window.location.hash = '#/testcases?status=stale'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(ids(container)).toEqual(['1.1-AC02-02'])
    act(() => {
      window.location.hash = '#/testcases'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(ids(container)).toHaveLength(5)
  })

  it('a hash change to another page is not read as filters', () => {
    window.location.hash = '#/testcases?level=uat'
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(ids(container)).toEqual(['UAT-1.1-AC01-01'])
    act(() => {
      window.location.hash = '#/suites'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(ids(container)).toEqual(['UAT-1.1-AC01-01'])
    expect(window.location.hash).toBe('#/suites')
  })

  it('Enter and Space on a row open it; a click that ends a text selection does not', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    const first = container.querySelector('[data-tc="1.1-AC01-01"]') as HTMLElement
    const second = container.querySelector('[data-tc="1.1-AC02-01"]') as HTMLElement
    fireEvent.keyDown(first, { key: 'Enter' })
    expect(screen.getByLabelText('Review TC-1.1-AC01-01')).toBeInTheDocument()
    expect(first).toHaveAttribute('aria-current', 'true')
    expect(second).not.toHaveAttribute('aria-current')
    expect(first).not.toHaveAttribute('aria-selected')
    fireEvent.keyDown(second, { key: ' ' })
    expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
    vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => 'dragged text' } as Selection)
    fireEvent.click(first)
    expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
  })

  it('Close returns focus to the row the panel was opened from', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    const tr = container.querySelector('[data-tc="1.1-AC02-01"]') as HTMLElement
    fireEvent.click(tr)
    fireEvent.click(screen.getByRole('button', { name: 'Close review panel' }))
    expect(screen.queryByLabelText(/^Review /)).toBeNull()
    expect(document.activeElement).toBe(tr)
  })

  describe('with unsaved text in the open row', () => {
    it('another row asks first; "no" keeps the row and the draft, "yes" moves', () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
      typeDraft(container, '1.1-AC01-01')
      fireEvent.click(container.querySelector('[data-tc="1.1-AC02-01"]')!)
      fireEvent.keyDown(container.querySelector('[data-tc="1.1-AC01-02"]')!, { key: 'Enter' })
      expect(confirm).toHaveBeenCalledTimes(2)
      expect(screen.getByLabelText('Review TC-1.1-AC01-01')).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
      // the row already open is not a move: nothing is asked
      fireEvent.click(container.querySelector('[data-tc="1.1-AC01-01"]')!)
      expect(confirm).toHaveBeenCalledTimes(2)
      confirm.mockReturnValue(true)
      fireEvent.click(container.querySelector('[data-tc="1.1-AC02-01"]')!)
      expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
      expect(screen.queryByRole('textbox')).toBeNull()
    })

    it('Prev and Next ask first; "no" keeps the row and the draft', () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
      typeDraft(container, '1.1-AC02-01')
      fireEvent.click(screen.getByRole('button', { name: 'Next test case' }))
      fireEvent.click(screen.getByRole('button', { name: 'Previous test case' }))
      expect(confirm).toHaveBeenCalledTimes(2)
      expect(container.querySelector('tr.selected')!.getAttribute('data-tc')).toBe('1.1-AC02-01')
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
      confirm.mockReturnValue(true)
      fireEvent.click(screen.getByRole('button', { name: 'Next test case' }))
      expect(container.querySelector('tr.selected')!.getAttribute('data-tc')).toBe('1.1-AC02-02')
    })

    it('a filter cannot hide the open row; it goes once the draft is dropped', () => {
      const confirm = vi.spyOn(window, 'confirm')
      const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
      typeDraft(container, '1.1-AC01-01')
      fireEvent.click(screen.getByRole('button', { name: 'UAT' }))
      fireEvent.click(screen.getByRole('button', { name: 'High' }))
      // the SIT row stays beside the UAT rows the filter asked for
      expect(ids(container)).toEqual(['1.1-AC01-01', 'UAT-1.1-AC01-01'])
      expect(screen.getByLabelText('Review TC-1.1-AC01-01')).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
      expect(confirm).not.toHaveBeenCalled()
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
      expect(ids(container)).toEqual(['UAT-1.1-AC01-01'])
      expect(screen.queryByLabelText(/^Review /)).toBeNull()
    })

    it('a reload that hides or drops the open row keeps the panel and the draft', () => {
      const { container, rerender } = render(<TestCaseGrid payload={PAYLOAD} initialFilters={{ status: 'active' }} />)
      typeDraft(container, '1.1-AC01-01')
      // the row went stale elsewhere: it no longer passes the status filter
      const stale = { ...PAYLOAD, rows: PAYLOAD.rows.map((r) => (r.id === '1.1-AC01-01' ? { ...r, status: 'stale' } : r)) }
      rerender(<TestCaseGrid payload={stale} initialFilters={{ status: 'active' }} />)
      expect(ids(container)).toContain('1.1-AC01-01')
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
      // the row is gone from the wiki altogether
      const gone = { ...PAYLOAD, rows: PAYLOAD.rows.filter((r) => r.id !== '1.1-AC01-01') }
      rerender(<TestCaseGrid payload={gone} initialFilters={{ status: 'active' }} />)
      expect(ids(container)).not.toContain('1.1-AC01-01')
      expect(screen.getByLabelText('Review TC-1.1-AC01-01')).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
    })
  })

  it('marks a cell whose text is cut, and only that cell', () => {
    const heights = vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function (this: HTMLElement) {
      return this.textContent?.includes('Continue from') ? 400 : 20
    })
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(160)
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    const cells = [...(container.querySelector('[data-tc="1.1-AC02-01"]') as HTMLElement).querySelectorAll('.tc-cell')]
    expect(cells.map((c) => c.classList.contains('clipped'))).toEqual([false, true, false, false, false])
    expect(cells[1]).toHaveAttribute('title', 'More text: open the row to read all of it')
    expect(cells[0]).not.toHaveAttribute('title')
    heights.mockRestore()
  })

  it('keeps the filter state in the URL hash query and reads it back', () => {
    window.location.hash = '#/testcases?level=sit&confidence=Medium'
    const { container, unmount } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(firstCells(container)).toEqual(['Run: Main flow SIT', 'Section: Self-check', 'TC-1.1-AC02-01'])
    fireEvent.click(screen.getByRole('button', { name: 'Medium' }))
    fireEvent.click(screen.getByRole('button', { name: 'Low' }))
    expect(window.location.hash).toBe('#/testcases?level=sit&confidence=Low')
    unmount()
  })

  it('lockStory shows only that story, hides the story filter and leaves the hash alone', () => {
    window.location.hash = '#/story/US-DEMO-002'
    const { container } = render(<TestCaseGrid payload={PAYLOAD} lockStory="US-DEMO-002" />)
    expect(firstCells(container)).toEqual(['Run: Variant flow SIT', 'Section: Login', 'TC-1.1-AC01-02'])
    expect(screen.queryByRole('combobox', { name: 'Story' })).toBeNull()
    expect(screen.getByText('1 of 1 test cases')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'SIT' }))
    expect(window.location.hash).toBe('#/story/US-DEMO-002')
  })

  it('clicking a row opens the review panel; Escape closes it', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(screen.queryByLabelText(/^Review /)).toBeNull()
    fireEvent.click(container.querySelector('[data-tc="1.1-AC02-01"]')!)
    expect(screen.getByLabelText('Review TC-1.1-AC02-01')).toBeInTheDocument()
    expect(container.querySelector('[data-tc="1.1-AC02-01"]')!.className).toContain('selected')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByLabelText(/^Review /)).toBeNull()
  })

  it('Down / Up move through the VISIBLE rows and stop at the ends', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} initialFilters={{ confidence: ['High'] }} />)
    // visible: 1.1-AC02-02, 1.1-AC01-02, UAT-1.1-AC01-01
    fireEvent.click(container.querySelector('[data-tc="1.1-AC02-02"]')!)
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    expect(container.querySelector('tr.selected')!.getAttribute('data-tc')).toBe('1.1-AC01-02')
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    expect(container.querySelector('tr.selected')!.getAttribute('data-tc')).toBe('UAT-1.1-AC01-01')
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    expect(container.querySelector('tr.selected')!.getAttribute('data-tc')).toBe('1.1-AC02-02')
  })

  it('a filter that hides the open row closes the panel', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    fireEvent.click(container.querySelector('[data-tc="1.1-AC01-01"]')!)
    fireEvent.click(screen.getByRole('button', { name: 'UAT' }))
    expect(screen.queryByLabelText('Review TC-1.1-AC01-01')).toBeNull()
  })

  it('the open panel follows a reloaded payload', () => {
    const { container, rerender } = render(<TestCaseGrid payload={PAYLOAD} />)
    fireEvent.click(container.querySelector('[data-tc="1.1-AC01-01"]')!)
    const next = { ...PAYLOAD, rows: PAYLOAD.rows.map((r) => (r.id === '1.1-AC01-01' ? { ...r, title: 'Reworded title' } : r)) }
    rerender(<TestCaseGrid payload={next} />)
    expect(within(screen.getByLabelText('Review TC-1.1-AC01-01')).getByText('Reworded title')).toBeInTheDocument()
  })

  it('shows the shared pre-condition block per group, collapsed until opened', () => {
    const { container } = render(<TestCaseGrid payload={PAYLOAD} />)
    expect(screen.getAllByRole('button', { name: /Pre-condition/ })).toHaveLength(1)
    expect(screen.queryByText('Shared setup.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Pre-condition/ }))
    expect(screen.getByText('Shared setup.')).toBeInTheDocument()
    expect(container.querySelector('.tc-common-row strong')?.textContent).toBe('data')
    expect(screen.getByText('Shared by every test case in this group - defined once for the story')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Pre-condition/ }))
    expect(screen.queryByText('Shared setup.')).toBeNull()
  })

  it('has no pre-condition block or button when the group shares nothing', () => {
    const groups = PAYLOAD.groups.map((g) => ({ ...g, common: [] }))
    render(<TestCaseGrid payload={{ ...PAYLOAD, groups }} />)
    expect(screen.queryByRole('button', { name: /Pre-condition/ })).toBeNull()
  })

  it('arrow navigation scrolls the new row into view', () => {
    const original = Element.prototype.scrollIntoView
    const spy = vi.fn()
    Element.prototype.scrollIntoView = spy
    try {
      const { container } = render(<TestCaseGrid payload={PAYLOAD} initialFilters={{ confidence: ['High'] }} />)
      fireEvent.click(container.querySelector('[data-tc="1.1-AC02-02"]')!)
      spy.mockClear()
      fireEvent.keyDown(window, { key: 'ArrowDown' })
      expect(spy).toHaveBeenCalledWith({ block: 'nearest' })
      expect(spy.mock.contexts.at(-1)).toBe(container.querySelector('[data-tc="1.1-AC01-02"]'))
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })
})

describe('index.css test case layout', () => {
  const css = readFileSync('src/index.css', 'utf8')

  it('stacks the panel under the grid in a narrow window', () => {
    const narrow = css.slice(css.indexOf('@media (max-width: 900px)', css.indexOf('.tc-split')))
    expect(narrow).toMatch(/\.tc-split\s*\{\s*flex-direction:\s*column;/)
    expect(narrow).toMatch(/\.tc-panel\s*\{[^}]*width:\s*auto;[^}]*max-height:\s*none;/)
  })

  it('shares one variable between the sticky group row and the row scroll margin', () => {
    expect(css).toMatch(/\.tc-group-row td\s*\{[^}]*top:\s*var\(--tc-head-h\)/)
    expect(css).toMatch(/\.tc-row\s*\{[^}]*scroll-margin-top:\s*calc\(var\(--tc-head-h\)/)
    // the header is one line, or it would be taller than --tc-head-h
    expect(css).toMatch(/\.tc-grid th\s*\{[^}]*white-space:\s*nowrap/)
  })

  it('keeps the stacked grid card inside the page width, scrolling inside itself', () => {
    const narrow = css.slice(css.indexOf('@media (max-width: 900px)', css.indexOf('.tc-split')))
    expect(narrow).toMatch(/\.tc-split\s*\{[^}]*align-items:\s*stretch/)
    expect(narrow).toMatch(/\.tc-grid-card\s*\{[^}]*flex:\s*none;[^}]*width:\s*100%/)
    expect(css).toMatch(/\.tc-grid-card\s*\{[^}]*overflow:\s*auto/)
  })

  it('keeps the ID column in view when the grid scrolls sideways', () => {
    expect(css).toMatch(/\.tc-grid td\.tc-id\s*\{[^}]*position:\s*sticky;[^}]*left:\s*0;[^}]*background:/)
    expect(css).toMatch(/\.tc-grid th:first-child\s*\{[^}]*left:\s*0/)
  })

  it('fades a clipped cell instead of cutting it without a sign', () => {
    expect(css).toMatch(/\.tc-cell\.clipped\s*\{[^}]*mask-image:\s*linear-gradient/)
  })
})

describe('index.css page height', () => {
  const css = readFileSync('src/index.css', 'utf8')

  it('constrains the page column to the viewport so a page owns its own scrolling', () => {
    // Without these the grid row grows to its content: the document scrolls,
    // the Workbook view's frozen header never sticks and its tabs sit at the
    // bottom of a page thousands of pixels tall.
    expect(css).toMatch(/\.app-body\s*\{[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\)/)
    expect(css).toMatch(/\.main\s*\{[^}]*min-height:\s*0/)
    expect(css).toMatch(/\.wb-page\s*\{[^}]*flex:\s*1;[^}]*min-height:\s*0/)
    expect(css).toMatch(/\.wb-body\s*\{[^}]*min-height:\s*0/)
    expect(css).toMatch(/\.wb-scroll\s*\{[^}]*overflow:\s*auto/)
    expect(css).toMatch(/\.wb-body > \.tc-panel\s*\{[^}]*max-height:\s*none/)
    expect(css).toMatch(/\.page\s*\{[^}]*overflow:\s*auto/)
  })
})
