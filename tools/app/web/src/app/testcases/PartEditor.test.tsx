import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { PartEditor } from './PartEditor'
import { hasUnsavedDraft } from '../shell/unsaved'
import { row } from './fixtures'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, editTestCase: vi.fn() }
})
import * as api from '../api'

const ok = { argv: ['tc', 'edit'], rc: 0, stdout: 'tc edit: saved', stderr: '' }

describe('PartEditor', () => {
  beforeEach(() => { vi.mocked(api.editTestCase).mockReset() })

  it('shows the text with bold markers rendered and an Edit button', () => {
    const { container } = render(<PartEditor row={row()} field="steps" label="Test Steps" text={'1. Click **Login**.'} />)
    expect(container.querySelector('strong')?.textContent).toBe('Login')
    expect(screen.getByRole('button', { name: 'Edit Test Steps' })).toBeInTheDocument()
  })

  it('a field the row does not list as editable exposes no editor', () => {
    render(<PartEditor row={row({ editable: ['title'] })} field="steps" label="Test Steps" text="1. Do." />)
    expect(screen.queryByRole('button', { name: /Edit/ })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('Edit opens a textarea holding the raw text, markers included', () => {
    render(<PartEditor row={row()} field="steps" label="Test Steps" text={'1. Click **Login**.'} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    expect(screen.getByRole('textbox', { name: 'Test Steps' })).toHaveValue('1. Click **Login**.')
  })

  it('Save sends id, field and text, then closes the editor and shows the saved text', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Test Steps' }), { target: { value: '1. New.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    expect(api.editTestCase).toHaveBeenCalledWith('1.1-AC01-01', 'steps', '1. New.')
    expect(screen.getByText('1. New.')).toBeInTheDocument()
  })

  it('a refusal is shown verbatim and the operator text stays in the editor', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue({
      argv: ['tc', 'edit'], rc: 1, stdout: '',
      stderr: 'tc edit refused: `render_sit.py --story US-DEMO-001 --force` refused:\n  ERROR pre_extra must be ONE line\n  Nothing was changed.',
    })
    render(<PartEditor row={row()} field="pre_extra" label="Extra precondition" text="" />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Extra precondition' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'one\ntwo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('pre_extra must be ONE line')
    expect(alert.textContent).toContain('Nothing was changed.')
    expect(screen.getByRole('textbox')).toHaveValue('one\ntwo')
  })

  it('a failed request is shown like a refusal, never swallowed', async () => {
    vi.mocked(api.editTestCase).mockRejectedValue(new Error('invalid field'))
    render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect((await screen.findByRole('alert')).textContent).toBe('invalid field')
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('Cancel discards the draft and calls nothing', () => {
    render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'junk' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByText('1. Old.')).toBeInTheDocument()
    expect(api.editTestCase).not.toHaveBeenCalled()
  })

  it('a closed set is edited with a select', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    render(<PartEditor row={row()} field="priority" label="Priority" text="P1" options={['P1', 'P2', 'P3']} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Priority' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Priority' }), { target: { value: 'P3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.editTestCase).toHaveBeenCalledWith('1.1-AC01-01', 'priority', 'P3'))
  })

  it('states the note before the save, only while editing', () => {
    render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." note="Confirmed part: Test Steps (Medium)." />)
    expect(screen.queryByRole('note')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    expect(screen.getByRole('note').textContent).toContain('Confirmed part')
  })

  it('moving to another test case drops a half-made edit', () => {
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    rerender(<PartEditor row={row({ id: '1.1-AC02-01' })} field="steps" label="Test Steps" text="1. Other." />)
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByText('1. Other.')).toBeInTheDocument()
  })

  it('a save that resolves after the row changed does not leak into the new row', async () => {
    let resolve: (v: typeof ok) => void = () => {}
    vi.mocked(api.editTestCase).mockReturnValue(new Promise((r) => { resolve = r }))
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. A old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '1. A draft.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    rerender(<PartEditor row={row({ id: '1.1-AC02-01' })} field="steps" label="Test Steps" text="1. B own." />)
    await act(async () => { resolve(ok) })
    expect(screen.getByText('1. B own.')).toBeInTheDocument()
    expect(screen.queryByText('1. A draft.')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('warns when the text changed under an open editor and keeps the draft', () => {
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'my draft' } })
    expect(screen.queryByRole('status')).toBeNull()
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Newer." />)
    expect(screen.getByRole('status').textContent).toBe('This text changed while you were editing. Saving will replace the newer text.')
    expect(screen.getByRole('textbox')).toHaveValue('my draft')
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
  })

  it('no false notice when Edit is pressed again before the reload of a save lands', async () => {
    // Save, then Edit at once: the prop still holds the old text and the
    // editor opens on the saved text. The reload then brings the prop to
    // what the editor already shows - that is not a change underneath.
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '1. New.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    expect(screen.getByRole('textbox')).toHaveValue('1. New.')
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. New." />)
    expect(screen.queryByRole('status')).toBeNull()
    // a third text is still a change underneath
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Someone else." />)
    expect(screen.getByRole('status').textContent).toContain('changed while you were editing')
  })

  it('reports unsaved text for exactly as long as the draft differs from what it opened with', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    const { unmount } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    expect(hasUnsavedDraft()).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    expect(hasUnsavedDraft()).toBe(false)          // open, nothing typed
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'typed' } })
    expect(hasUnsavedDraft()).toBe(true)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '1. Old.' } })
    expect(hasUnsavedDraft()).toBe(false)          // typed back
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'typed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(hasUnsavedDraft()).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'saved' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    expect(hasUnsavedDraft()).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'left behind' } })
    expect(hasUnsavedDraft()).toBe(true)
    unmount()
    expect(hasUnsavedDraft()).toBe(false)          // an editor that is gone holds nothing
  })

  it('a refused save keeps the draft reported as unsaved', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue({ argv: [], rc: 1, stdout: '', stderr: 'tc edit refused: nope' })
    const { unmount } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'typed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByRole('alert')
    expect(hasUnsavedDraft()).toBe(true)
    unmount()
  })

  it('returns focus to the Edit button after Cancel and after Save', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '1. New.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Edit Test Steps' }))
  })

  it('no notice while the text is unchanged', () => {
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('after a save the closed view keeps the saved text until the prop changes', async () => {
    vi.mocked(api.editTestCase).mockResolvedValue(ok)
    const { rerender } = render(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '1. New.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Old." />)
    expect(screen.getByText('1. New.')).toBeInTheDocument()
    rerender(<PartEditor row={row()} field="steps" label="Test Steps" text="1. Reloaded." />)
    expect(screen.getByText('1. Reloaded.')).toBeInTheDocument()
  })
})
