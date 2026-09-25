import { describe, expect, it } from 'vitest'
import { canAssert } from './cardSummary'
import type { AlignmentCard as AC } from './types'

const base: AC = {
  file: 'c.json', card_type: 'alignment', story: 'stories/US-VHLD', emitted_at: '',
  zones: {
    what_you_said: [], what_i_understood: '', what_i_changed: [],
    what_this_affects: {}, open_questions: [], actions: [],
  },
}

describe('canAssert', () => {
  it('blocks assert while open questions remain', () => {
    const withQ: AC = { ...base, zones: { ...base.zones, open_questions: [
      { id: 'Q1', about: 'AC1', question: 'q?', proposed: 'p' },
    ] } }
    expect(canAssert(withQ)).toBe(false)
  })
  it('allows assert when there are no open questions', () => {
    expect(canAssert(base)).toBe(true)
  })
})
