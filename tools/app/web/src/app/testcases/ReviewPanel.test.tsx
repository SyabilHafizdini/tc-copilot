import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { ReviewPanel } from './ReviewPanel'
import { editTestCase } from '../api'
import { PAYLOAD, row } from './fixtures'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, editTestCase: vi.fn() }
})

const part = (container: HTMLElement, key: string) =>
  container.querySelector(`[data-part="${key}"]`) as HTMLElement

describe('ReviewPanel', () => {
  it('renders from a row alone: id, title, objective, priority, technique, covered AC', () => {
    render(<ReviewPanel row={row()} onClose={() => {}} />)
    expect(screen.getByLabelText('Review TC-1.1-AC01-01')).toBeInTheDocument()
    expect(screen.getByText('Log in as the tenant')).toBeInTheDocument()
    expect(screen.getByText('Verify the tenant can log in.')).toBeInTheDocument()
    expect(screen.getByText('P1')).toBeInTheDocument()
    expect(screen.getByText('UC')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'US-DEMO-001 # HS-01' })).toHaveAttribute('href', '#/story/US-DEMO-001')
  })

  it('shows each of the four parts with its own level and remark', () => {
    const { container } = render(<ReviewPanel row={row()} onClose={() => {}} />)
    expect(within(part(container, 'scenario')).getByText('High')).toBeInTheDocument()
    expect(within(part(container, 'steps')).getByText('Medium')).toBeInTheDocument()
    expect(within(part(container, 'steps')).getByText(/Verify: the button/)).toBeInTheDocument()
    expect(within(part(container, 'data')).getByText('Low')).toBeInTheDocument()
    expect(within(part(container, 'expected')).getByText('High')).toBeInTheDocument()
  })

  it('derived parts are read-only, say where they are defined and expose no editor', () => {
    const { container } = render(<ReviewPanel row={row()} onClose={() => {}} />)
    const scenario = part(container, 'scenario')
    expect(within(scenario).queryByRole('button', { name: /Edit/ })).toBeNull()
    expect(within(scenario).getByText(/change it in the story/)).toBeInTheDocument()
    const block = container.querySelector('[data-readonly="Element block"]') as HTMLElement
    expect(block.className).toContain('readonly')
    expect(within(block).queryByRole('button')).toBeNull()
    expect(within(block).getByText(/coverage map/)).toBeInTheDocument()
    const chain = container.querySelector('[data-readonly="Starts from"]') as HTMLElement
    expect(within(chain).getByText(/Start of run/)).toBeInTheDocument()
    expect(within(chain).queryByRole('button')).toBeNull()
  })

  it('a SIT row offers every editable field; no level or remark is ever editable', () => {
    render(<ReviewPanel row={row()} onClose={() => {}} />)
    const names = screen.getAllByRole('button', { name: /^Edit / }).map((b) => b.getAttribute('aria-label'))
    expect(names).toEqual(['Edit Title', 'Edit Objective', 'Edit Priority', 'Edit Test Steps',
      'Edit Field / Values', 'Edit Extra precondition', 'Edit Expected Results', 'Edit Postcondition'])
    expect(screen.queryByRole('button', { name: /Confirm/ })).toBeNull()   // phase 2
  })

  it('a UAT row has no Field / Values, precondition or postcondition editor', () => {
    const uat = PAYLOAD.rows.find((r) => r.level === 'uat')!
    render(<ReviewPanel row={uat} onClose={() => {}} />)
    const names = screen.getAllByRole('button', { name: /^Edit / }).map((b) => b.getAttribute('aria-label'))
    expect(names).toEqual(['Edit Title', 'Edit Objective', 'Edit Priority', 'Edit Test Steps', 'Edit Expected Results'])
    expect(screen.getByText(/carries its values inside the steps/)).toBeInTheDocument()
  })

  it('a row that is not editable shows no editor at all and says why', () => {
    render(<ReviewPanel row={row({ status: 'stale', editable: [] })} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: /^Edit / })).toBeNull()
    expect(screen.getByText(/This test case is stale; it is read-only here/)).toBeInTheDocument()
  })

  it('warns before the save when the edited part was confirmed', () => {
    const r = row()
    // a rendered confirmation: the part reads High and carries the level it
    // was authored at, which is the level a rewording returns it to
    const confirmed: typeof r = { ...r, parts: { ...r.parts,
      data: { ...r.parts.data, state: 'closed', level: 'High', authored: 'Low' } } }
    render(<ReviewPanel row={confirmed} onClose={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Extra precondition' }))
    const note = screen.getByRole('note').textContent
    expect(note).toContain('Confirmed part: Field / Values (authored Low).')
    expect(note).toContain('returns the part to its authored level')
    expect(note).not.toContain('(High)')
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    expect(screen.queryByRole('note')).toBeNull()      // steps part is still open
  })

  it('names no level it does not know: a confirmed part without an authored level', () => {
    const r = row()
    const confirmed = { ...r, parts: { ...r.parts, data: { ...r.parts.data, state: 'closed' } } }
    render(<ReviewPanel row={confirmed} onClose={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Extra precondition' }))
    expect(screen.getByRole('note').textContent).toContain('Confirmed part: Field / Values. A confirmation')
  })

  describe('with unsaved text in an editor', () => {
    const typing = () => {
      const onClose = vi.fn()
      const onNavigate = vi.fn()
      render(<ReviewPanel row={row()} onClose={onClose} onNavigate={onNavigate} />)
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      fireEvent.change(screen.getByRole('textbox', { name: 'Test Steps' }), { target: { value: 'my draft' } })
      return { onClose, onNavigate }
    }
    afterEach(() => { vi.restoreAllMocks() })

    it('Prev, Next and Close ask first, and a "no" changes nothing', () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const { onClose, onNavigate } = typing()
      fireEvent.click(screen.getByRole('button', { name: 'Next test case' }))
      fireEvent.click(screen.getByRole('button', { name: 'Previous test case' }))
      fireEvent.click(screen.getByRole('button', { name: 'Close review panel' }))
      expect(confirm).toHaveBeenCalledTimes(3)
      expect(confirm).toHaveBeenCalledWith('You have unsaved text in an editor. Discard it?')
      expect(onNavigate).not.toHaveBeenCalled()
      expect(onClose).not.toHaveBeenCalled()
      expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('my draft')
    })

    it('a "yes" lets them through', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      const { onClose, onNavigate } = typing()
      fireEvent.click(screen.getByRole('button', { name: 'Next test case' }))
      fireEvent.click(screen.getByRole('button', { name: 'Close review panel' }))
      expect(onNavigate).toHaveBeenCalledWith(1)
      expect(onClose).toHaveBeenCalledOnce()
    })

    it('an editor that is open with nothing typed asks nothing', () => {
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const onNavigate = vi.fn()
      render(<ReviewPanel row={row()} onClose={() => {}} onNavigate={onNavigate} />)
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      fireEvent.click(screen.getByRole('button', { name: 'Next test case' }))
      expect(confirm).not.toHaveBeenCalled()
      expect(onNavigate).toHaveBeenCalledWith(1)
    })
  })

  it('Escape closes; the arrows move to the previous / next row', () => {
    const onClose = vi.fn()
    const onNavigate = vi.fn()
    render(<ReviewPanel row={row()} onClose={onClose} onNavigate={onNavigate} />)
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    expect(onNavigate.mock.calls).toEqual([[1], [-1]])
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('keys typed inside an editor never close the panel or move the row', () => {
    const onClose = vi.fn()
    const onNavigate = vi.fn()
    render(<ReviewPanel row={row()} onClose={onClose} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    const box = screen.getByRole('textbox', { name: 'Test Steps' })
    fireEvent.keyDown(box, { key: 'Escape' })
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    expect(onClose).not.toHaveBeenCalled()
    expect(onNavigate).not.toHaveBeenCalled()
    expect(box).toBeInTheDocument()
  })

  it('links to the markdown file and the story; says nothing about a workbook until it knows', () => {
    const { rerender } = render(<ReviewPanel row={row()} onClose={() => {}} />)
    expect(screen.getByRole('link', { name: 'Markdown file' }))
      .toHaveAttribute('href', '#/explore/testcases/sit/rental-desk/1.1-AC01-01')
    expect(screen.getByRole('link', { name: 'Story US-DEMO-001' })).toHaveAttribute('href', '#/story/US-DEMO-001')
    // not known (the Workbook page, or the inventory is not read yet): no dead control
    expect(screen.queryByText(/workbook/i)).toBeNull()
    // known, and in none: said in words, not as a link that does nothing
    rerender(<ReviewPanel row={row()} onClose={() => {}} workbookHref={null} />)
    expect(screen.queryByRole('link', { name: /workbook/i })).toBeNull()
    expect(screen.getByText('Not in a compiled workbook')).toBeInTheDocument()
    rerender(<ReviewPanel row={row()} onClose={() => {}} workbookHref="#/workbook/demo-sit" />)
    expect(screen.getByRole('link', { name: 'Open in workbook' })).toHaveAttribute('href', '#/workbook/demo-sit')
    expect(screen.queryByText('Not in a compiled workbook')).toBeNull()
  })

  it('without onNavigate there are no previous / next buttons and the arrows do nothing', () => {
    render(<ReviewPanel row={row()} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Next test case' })).toBeNull()
    fireEvent.keyDown(window, { key: 'ArrowDown' })   // must not throw
  })

  describe('keys while an editor is open (focus is not in the control)', () => {
    const setup = () => {
      const onClose = vi.fn()
      const onNavigate = vi.fn()
      render(<ReviewPanel row={row()} onClose={onClose} onNavigate={onNavigate} />)
      return { onClose, onNavigate }
    }
    const press = (key: string, init: object = {}) => fireEvent.keyDown(document.body, { key, ...init })

    it('Edit focuses the textarea', () => {
      setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Test Steps' }))
    })

    it('Edit focuses the priority select', () => {
      setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Priority' }))
      expect(document.activeElement).toBe(screen.getByRole('combobox', { name: 'Priority' }))
    })

    it('an open textarea editor blocks Escape and the arrows even with focus on body', () => {
      const { onClose, onNavigate } = setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      ;(document.activeElement as HTMLElement).blur()
      press('Escape'); press('ArrowDown'); press('ArrowUp')
      expect(onClose).not.toHaveBeenCalled()
      expect(onNavigate).not.toHaveBeenCalled()
    })

    it('an open priority select blocks the keys too', () => {
      const { onClose, onNavigate } = setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Priority' }))
      ;(document.activeElement as HTMLElement).blur()
      press('Escape'); press('ArrowDown')
      expect(onClose).not.toHaveBeenCalled()
      expect(onNavigate).not.toHaveBeenCalled()
    })

    it('keys are blocked while a refusal is showing', async () => {
      vi.mocked(editTestCase).mockResolvedValue({ rc: 1, stdout: 'refused', stderr: '' } as never)
      const { onClose, onNavigate } = setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await screen.findByRole('alert')
      press('Escape'); press('ArrowDown')
      expect(onClose).not.toHaveBeenCalled()
      expect(onNavigate).not.toHaveBeenCalled()
    })

    it('keys work again after Cancel and after a successful save', async () => {
      vi.mocked(editTestCase).mockResolvedValue({ rc: 0, stdout: '', stderr: '' } as never)
      const { onClose, onNavigate } = setup()
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
      press('ArrowDown')
      expect(onNavigate).toHaveBeenCalledTimes(1)
      fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await screen.findByRole('button', { name: 'Edit Test Steps' })
      press('Escape')
      expect(onClose).toHaveBeenCalledOnce()
    })

    it('a modified arrow never navigates, and a handled key is left alone', () => {
      const { onNavigate, onClose } = setup()
      press('ArrowDown', { ctrlKey: true }); press('ArrowUp', { altKey: true })
      press('ArrowDown', { metaKey: true }); press('ArrowDown', { shiftKey: true })
      const e = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true, bubbles: true })
      e.preventDefault()
      document.body.dispatchEvent(e)
      expect(onNavigate).not.toHaveBeenCalled()
      expect(onClose).not.toHaveBeenCalled()
    })

    it('an empty priority is a blank selected option, never a value that matches none', async () => {
      vi.mocked(editTestCase).mockResolvedValue({ rc: 0, stdout: '', stderr: '' } as never)
      render(<ReviewPanel row={row({ priority: null })} onClose={() => {}} />)
      fireEvent.click(screen.getByRole('button', { name: 'Edit Priority' }))
      const sel = screen.getByRole('combobox', { name: 'Priority' }) as HTMLSelectElement
      expect(sel.value).toBe('')
      expect(sel.selectedOptions[0].value).toBe('')
    })

    it('never prints null for a closed part with no level or a missing status', () => {
      const r = row({ status: null as never, editable: [] })
      const closed = { ...r, parts: { ...r.parts, data: { ...r.parts.data, state: 'closed', level: null } } }
      const { container } = render(<ReviewPanel row={closed as never} onClose={() => {}} />)
      expect(container.textContent).not.toContain('null')
    })
  })
})
