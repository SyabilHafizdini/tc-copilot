import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor as rtlWait } from '@testing-library/react'

const snap = {
  cards: [{
    file: 'session-US-VHLD-001.json', card_type: 'alignment', story: 'stories/US-VHLD',
    session: 'US-VHLD-001', emitted_at: '',
    zones: { what_you_said: [], what_i_understood: 'X', what_i_changed: [], what_this_affects: {}, open_questions: [], actions: [] },
  }],
}
const { runAction } = vi.hoisted(() => ({
  runAction: vi.fn(async () => ({ argv: ['assert'], rc: 0, stdout: 'asserted', stderr: '' })),
}))
vi.mock('../api', () => ({ getInbox: vi.fn(async () => snap), onChange: vi.fn(() => () => {}), runAction }))
import { InboxPage, cardTitle } from './InboxPage'

describe('cardTitle', () => {
  it('humanizes card_type and story into a readable title', () => {
    expect(cardTitle({ card_type: 'alignment', story: 'stories/US-VDTL' })).toBe('Alignment · US-VDTL')
    expect(cardTitle({ card_type: 'coverage', story: 'US-VHLD' })).toBe('Coverage · US-VHLD')
  })

  it('falls back to a label built from card_type when there is no story', () => {
    expect(cardTitle({ card_type: 'change_report', story: null })).toBe('Change report')
  })
})

describe('InboxPage', () => {
  it('titles the list card with a human-readable label, not the raw filename', async () => {
    render(<InboxPage />)
    await rtlWait(() => expect(screen.getByText(/Alignment.*US-VHLD/i)).toBeInTheDocument())
    expect(screen.getByText(/Alignment.*US-VHLD/i, { selector: 'b' })).toBeInTheDocument()
    expect(screen.queryByText('session-US-VHLD-001.json', { selector: 'b' })).not.toBeInTheDocument()
  })

  it('lists a card, selects it, and asserts with the story basename', async () => {
    render(<InboxPage />)
    await rtlWait(() => expect(screen.getByText(/session-US-VHLD-001/)).toBeInTheDocument())
    fireEvent.click(screen.getByText(/session-US-VHLD-001/))
    await rtlWait(() => expect(screen.getByText('X')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^assert$/i }))
    expect(runAction).toHaveBeenCalledWith('assert', { id: 'US-VHLD', card: 'session-US-VHLD-001.json' })
  })

  it('offers a revert after a discard reports commits, calling session_revert', async () => {
    render(<InboxPage />)
    await rtlWait(() => expect(screen.getByText(/session-US-VHLD-001/)).toBeInTheDocument())
    fireEvent.click(screen.getByText(/session-US-VHLD-001/))
    await rtlWait(() => expect(screen.getByText('X')).toBeInTheDocument())

    vi.mocked(runAction).mockResolvedValueOnce({
      argv: ['card', 'discard'], rc: 0,
      stdout: 'card discard: session-US-VHLD-001.json by syabz\n' +
              '  session US-VHLD-001 produced these commits...\n    abc1234 feat',
      stderr: '',
    })
    fireEvent.click(screen.getByRole('button', { name: /discard/i }))
    const revert = await screen.findByRole('button', { name: /revert/i })

    vi.mocked(runAction).mockResolvedValueOnce({ argv: [], rc: 0, stdout: 'undid 1', stderr: '' })
    fireEvent.click(revert)
    expect(runAction).toHaveBeenLastCalledWith('session_revert', { session: 'US-VHLD-001' })
  })
})
