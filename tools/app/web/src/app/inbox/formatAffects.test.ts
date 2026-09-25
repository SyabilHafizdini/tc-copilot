import { describe, expect, it } from 'vitest'
import { formatAffects } from './cardSummary'

describe('formatAffects', () => {
  it('humanizes keys and renders plain language, never raw JSON', () => {
    const affects = {
      staled_tcs: [],
      dependent_stories: ['stories/US-VDTL (shares base data set and alert definitions)'],
      coverage_impact: '25 active ACs currently uncovered; generation unlocked on assertion',
    }
    expect(formatAffects(affects)).toEqual([
      'Staled test cases: none',
      'Dependent stories: stories/US-VDTL (shares base data set and alert definitions)',
      'Coverage impact: 25 active ACs currently uncovered; generation unlocked on assertion',
    ])
  })
  it('never leaks JSON braces or raw snake_case keys', () => {
    const out = formatAffects({ staled_tcs: ['sit/TC-1', 'sit/TC-2'] }).join('\n')
    expect(out).toBe('Staled test cases: sit/TC-1; sit/TC-2')
    expect(out).not.toContain('{')
    expect(out).not.toContain('staled_tcs')
  })
  it('returns an empty list for an empty affects object', () => {
    expect(formatAffects({})).toEqual([])
  })
})
