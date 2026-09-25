import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AlignmentCard } from './AlignmentCard'
import type { AlignmentCard as AC } from './types'

const card: AC = {
  file: 'session-US-VHLD-001.json', card_type: 'alignment', story: 'stories/US-VHLD', emitted_at: '',
  zones: {
    what_you_said: ['do X'],
    what_i_understood: 'I understood X: 25 ACs, 9 business rules, 14 components.',
    what_i_changed: ['changed Y'],
    what_this_affects: { staled_tcs: [], dependent_stories: ['stories/US-VDTL'] },
    open_questions: [{ id: 'Q1', about: 'AC1', question: 'q1?', proposed: 'p1' }],
    actions: [],
  },
}

describe('AlignmentCard', () => {
  it('flags the tripwire, shows summary chips, and renders the question', () => {
    render(<AlignmentCard card={card} onAssert={vi.fn()} onRevise={vi.fn()} onDiscard={vi.fn()} />)
    expect(screen.getByText(/I understood X/)).toBeInTheDocument()
    expect(document.querySelector('.tripwire')).toBeTruthy()
    expect(document.querySelector('.summary-chips')).toBeTruthy()
    expect(screen.getByText(/25 ACs/)).toBeInTheDocument()
    expect(screen.getByText(/q1\?/)).toBeInTheDocument()
  })
  it('renders "what this affects" as plain language, never raw JSON', () => {
    render(<AlignmentCard card={card} onAssert={vi.fn()} onRevise={vi.fn()} onDiscard={vi.fn()} />)
    expect(screen.getByText('Staled test cases: none')).toBeInTheDocument()
    expect(screen.getByText('Dependent stories: stories/US-VDTL')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('staled_tcs')
    expect(document.body.textContent).not.toContain('{')
  })
  it('disables Assert while an open question remains and does not fire onAssert', () => {
    const onAssert = vi.fn()
    render(<AlignmentCard card={card} onAssert={onAssert} onRevise={vi.fn()} onDiscard={vi.fn()} />)
    const assertBtn = screen.getByRole('button', { name: /^assert$/i })
    expect(assertBtn).toBeDisabled()
    expect(assertBtn).toHaveAttribute('title', expect.stringMatching(/open question/i))
    fireEvent.click(assertBtn)
    expect(onAssert).not.toHaveBeenCalled()
  })
  it('enables Assert on a card with zero open questions', () => {
    const onAssert = vi.fn()
    const clean: AC = { ...card, zones: { ...card.zones, open_questions: [] } }
    render(<AlignmentCard card={clean} onAssert={onAssert} onRevise={vi.fn()} onDiscard={vi.fn()} />)
    const assertBtn = screen.getByRole('button', { name: /^assert$/i })
    expect(assertBtn).toBeEnabled()
    fireEvent.click(assertBtn)
    expect(onAssert).toHaveBeenCalled()
  })
  it('collapses answered questions and revises with collected answers', () => {
    const onRevise = vi.fn()
    render(<AlignmentCard card={card} onAssert={vi.fn()} onRevise={onRevise} onDiscard={vi.fn()} />)
    // resolve Q1 -> it leaves the open list and progress ticks up
    fireEvent.click(screen.getByRole('button', { name: /^accept$/i }))
    expect(screen.getByText(/1 of 1 resolved/)).toBeInTheDocument()
    expect(screen.getByText(/1 answered/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^revise$/i }))
    expect(onRevise).toHaveBeenCalledWith({ answers: { Q1: 'accept' }, note: '' })
  })
})
