import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, createEvent } from '@testing-library/react'
import { SheetView } from './SheetView'
import { linkPieces, workbookHrefFor } from './links'
import { MAIN, REF_1, entry, payload } from './fixture'

const book = payload()
const main = book.sheets[0]
const hrefForLoc = (loc: { sheet: string; row: number }) => `#loc/${loc.sheet}/${loc.row}`

function draw(over: Partial<Parameters<typeof SheetView>[0]> = {}) {
  const onOpenTc = vi.fn()
  const utils = render(
    <SheetView sheet={main} links={book.links} onOpenTc={onOpenTc} hrefForLoc={hrefForLoc} {...over} />)
  const cellAt = (r: number, c: number) =>
    utils.container.querySelector<HTMLElement>(`td[data-cell="${r}:${c}"]`)
  return { ...utils, onOpenTc, cellAt }
}

describe('SheetView', () => {
  it('sizes columns from the file and keeps the frozen rows in a sticky head', () => {
    const { container } = draw()
    const cols = [...container.querySelectorAll('col')].map((c) => (c as HTMLElement).style.width)
    expect(cols).toEqual(['187px', '362px', '397px'])
    expect(container.querySelectorAll('thead tr')).toHaveLength(1)
    expect(container.querySelector('thead')!.textContent).toContain('Test Case ID')
    expect(container.querySelectorAll('tbody tr')).toHaveLength(4)
  })

  it('draws fills, bold, alignment, borders, wrap and row height from the cell', () => {
    const { cellAt, container } = draw()
    const head = cellAt(1, 1)!
    expect(head.style.background).toBe('rgb(217, 217, 217)')
    expect(head.style.fontWeight).toBe('700')
    expect(head.style.textAlign).toBe('center')
    expect(head.style.verticalAlign).toBe('middle')
    expect(head.className).toContain('wb-b')
    expect(head.className).toContain('wb-wrap')
    expect(cellAt(1, 2)!.className).toContain('wb-nowrap')
    expect(container.querySelector<HTMLElement>('tr[data-row="1"]')!.style.height).toMatch(/^50\.6/)
  })

  it('clips an unwrapped cell only when the cell to its right holds text', () => {
    const { cellAt } = draw()
    // "Test Steps" (unwrapped) sits beside "Remarks": the spill stops at the border
    expect(cellAt(1, 2)!.className).toContain('wb-clip')
    // the formula row's neighbours are empty: its text may spill, as in Excel
    expect(cellAt(5, 1)!.className).toContain('wb-nowrap')
    expect(cellAt(5, 1)!.className).not.toContain('wb-clip')
    // the last cell of a row has no neighbour; a wrapped cell never spills
    expect(cellAt(1, 3)!.className).not.toContain('wb-clip')
    expect(cellAt(1, 1)!.className).not.toContain('wb-clip')
  })

  it('names the test case on its row, so focus can return to it', () => {
    const { container } = draw()
    expect(container.querySelector('tr[data-row="3"]')!.getAttribute('data-tc-ref')).toBe(REF_1)
    expect(container.querySelector('tr[data-row="2"]')!.hasAttribute('data-tc-ref')).toBe(false)
  })

  it('spans a merged cell and leaves the covered cells out', () => {
    const { cellAt } = draw()
    expect(cellAt(2, 1)!.getAttribute('colspan')).toBe('3')
    expect(cellAt(2, 2)).toBeNull()
    expect(cellAt(2, 3)).toBeNull()
  })

  it('renders bold runs inside a cell', () => {
    const { cellAt } = draw()
    const steps = cellAt(3, 2)!
    expect(steps.textContent).toBe('1. Click Save.')
    expect(steps.querySelector('b')!.textContent).toBe('Save')
  })

  it('links the id cell to the markdown file in Explore without opening the panel', () => {
    const { onOpenTc } = draw()
    // the same id also appears as a Continue-from link on the next row
    const id = screen.getAllByRole('link', { name: 'TC-1.1-AC01-01' })
      .find((a) => a.className === 'wb-id')!
    expect(id.getAttribute('href')).toBe(`#/explore/${REF_1}`)
    fireEvent.click(id)
    expect(onOpenTc).not.toHaveBeenCalled()
  })

  it('opens the review panel when a test case row is clicked elsewhere', () => {
    const { onOpenTc, cellAt } = draw()
    fireEvent.click(cellAt(3, 2)!)
    expect(onOpenTc).toHaveBeenCalledWith(main.rows[2].tc, 3)
    fireEvent.click(cellAt(2, 1)!)                 // a Section row is not a test case
    expect(onOpenTc).toHaveBeenCalledTimes(1)
  })

  it('makes only test case rows focusable, and opens them on Enter or Space', () => {
    const { onOpenTc, container } = draw()
    const tr = container.querySelector<HTMLElement>('tr[data-row="3"]')!
    expect(tr.getAttribute('tabindex')).toBe('0')
    expect(container.querySelector('tr[data-row="2"]')!.hasAttribute('tabindex')).toBe(false)
    fireEvent.keyDown(tr, { key: 'Enter' })
    expect(onOpenTc).toHaveBeenCalledWith(main.rows[2].tc, 3)
    const space = createEvent.keyDown(tr, { key: ' ' })
    fireEvent(tr, space)
    expect(space.defaultPrevented).toBe(true)
    expect(onOpenTc).toHaveBeenCalledTimes(2)
    fireEvent.keyDown(tr, { key: 'a' })
    fireEvent.keyDown(container.querySelector('tr[data-row="2"]')!, { key: 'Enter' })
    expect(onOpenTc).toHaveBeenCalledTimes(2)
  })

  it('leaves a key pressed on a link inside the row to the link', () => {
    const { onOpenTc } = draw()
    const id = screen.getAllByRole('link', { name: 'TC-1.1-AC01-01' }).find((a) => a.className === 'wb-id')!
    const enter = createEvent.keyDown(id, { key: 'Enter' })
    fireEvent(id, enter)
    expect(onOpenTc).not.toHaveBeenCalled()
    expect(enter.defaultPrevented).toBe(false)
  })

  it('does not open the panel when the click ends a text selection', () => {
    const { onOpenTc, cellAt } = draw()
    const sel = vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => 'some text' } as Selection)
    fireEvent.click(cellAt(3, 2)!)
    expect(onOpenTc).not.toHaveBeenCalled()
    sel.mockReturnValue({ toString: () => '' } as Selection)
    fireEvent.click(cellAt(3, 2)!)
    expect(onOpenTc).toHaveBeenCalledTimes(1)
    sel.mockRestore()
  })

  it('marks a changed row and the focused row', () => {
    const { container } = draw({ focusRow: 3 })
    expect(container.querySelector('tr[data-row="4"]')!.className).toContain('wb-changed')
    expect(container.querySelector('tr[data-row="3"]')!.className).toContain('wb-focus')
    expect(container.querySelector('tr[data-row="3"]')!.className).not.toContain('wb-changed')
  })

  it('links a question id and a Continue-from id to the rows they name', () => {
    draw()
    expect(screen.getByRole('link', { name: 'Q-US-X-01' }).getAttribute('href'))
      .toBe('#loc/AI Doubts/2')
    // row 4 continues from TC-...-01, which sits on row 3 of this sheet
    const cont = screen.getAllByRole('link', { name: 'TC-1.1-AC01-01' })
      .find((a) => a.className === 'wb-link')!
    expect(cont.getAttribute('href')).toBe(`#loc/${MAIN}/3`)
  })

  it('draws an unresolved formula muted with the Excel tooltip', () => {
    const { cellAt } = draw()
    const f = cellAt(5, 1)!
    expect(f.className).toContain('wb-formula')
    expect(f.getAttribute('title')).toBe('calculated in Excel')
    expect(f.textContent).toBe('=SUM(A1:A2)')
  })

  it('applies only 6-digit hex colours from the file', () => {
    const evil = { ...main, rows: [{ ...main.rows[0], cells: [
      { ...main.rows[0].cells[0], fill: 'red;background:url(x)', color: 'zzzzzz' },
      { ...main.rows[0].cells[1], fill: 'ff00aa', color: '0070C0' },
      main.rows[0].cells[2]] }] }
    const { cellAt } = draw({ sheet: { ...evil, frozen_rows: 0, merges: [] } })
    expect(cellAt(1, 1)!.style.background).toBe('')
    expect(cellAt(1, 1)!.style.color).toBe('')
    expect(cellAt(1, 2)!.style.background).toBe('rgb(255, 0, 170)')
    expect(cellAt(1, 2)!.style.color).toBe('rgb(0, 112, 192)')
  })

  it('ignores a focus row the sheet does not have', () => {
    const { container } = draw({ focusRow: 999 })
    expect(container.querySelector('.wb-focus')).toBeNull()
  })
})

describe('linkPieces', () => {
  it('leaves an id the workbook does not hold as plain text', () => {
    expect(linkPieces('See TC-9.9-AC01-01 and Q-US-X-99.', book.links))
      .toEqual([{ text: 'See TC-9.9-AC01-01 and Q-US-X-99.', loc: null }])
  })
  it('does not take a sentence-ending full stop into the id', () => {
    const pieces = linkPieces('Continue from TC-1.1-AC01-02.', book.links)
    expect(pieces.map((p) => p.text)).toEqual(['Continue from ', 'TC-1.1-AC01-02', '.'])
    expect(pieces[1].loc).toEqual({ sheet: MAIN, row: 4 })
  })
})

describe('workbookHrefFor', () => {
  it('targets the newest workbook that holds the test case, at its row', () => {
    const older = entry({ name: 'old', file: 'old-latest.xlsx' })
    const newest = entry({ tcs: {} })
    expect(workbookHrefFor(REF_1, [newest, older]))
      .toBe('#/workbook/sit/old-latest.xlsx?sheet=C-TC-1+%28Main+flow%29&row=3')
    expect(workbookHrefFor('testcases/sit/m/none', [newest, older])).toBeNull()
  })
})
