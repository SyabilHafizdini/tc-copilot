import { describe, expect, it } from 'vitest'
import { cardSummary } from './cardSummary'
import type { AlignmentCard as AC } from './types'

const card: AC = {
  file: 'session-US-VHLD-001.json', card_type: 'alignment', story: 'stories/US-VHLD', emitted_at: '',
  zones: {
    what_you_said: [],
    what_i_understood:
      'Vehicle Holding dashboard. 25 ACs (1.1.3.1.1-AC1..AC25), 9 business rules, 14 components, 10 glossary terms proposed.',
    what_i_changed: [],
    what_this_affects: {},
    open_questions: [
      { id: 'Q1', about: 'AC17', question: 'What renders after clicking AWS?', proposed: 'drills in' },
      { id: 'Q4', about: 'BR-VHLD-04', question: 'PRD contradiction: #20 says X, #12 says Y.', proposed: 'X is a typo' },
    ],
    actions: [],
  },
}

describe('cardSummary', () => {
  it('parses AC / rule / component counts from the understood prose', () => {
    const s = cardSummary(card)
    expect(s.acs).toBe(25)
    expect(s.rules).toBe(9)
    expect(s.components).toBe(14)
  })
  it('counts contradiction questions and open questions', () => {
    const s = cardSummary(card)
    expect(s.contradictions).toBe(1)
    expect(s.openQuestions).toBe(2)
  })
  it('returns zeros when the prose carries no counts', () => {
    const bare: AC = { ...card, zones: { ...card.zones, what_i_understood: 'nothing quantified', open_questions: [] } }
    expect(cardSummary(bare)).toEqual({ acs: 0, rules: 0, components: 0, contradictions: 0, openQuestions: 0 })
  })
})
