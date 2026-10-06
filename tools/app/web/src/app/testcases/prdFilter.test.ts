import { describe, expect, it } from 'vitest'
import { matchesPrds, prdOptions, togglePrd } from './prdFilter'

const rows = [
  { prds: ['rental-payment'] },
  { prds: ['rental-application', 'rental-payment'] },
  { prds: [] },
]

describe('prdFilter', () => {
  it('lists the PRDs present across the rows, sorted, once each', () => {
    expect(prdOptions(rows)).toEqual(['rental-application', 'rental-payment'])
    expect(prdOptions([{ prds: [] }])).toEqual([])
  })

  it('matches every row when nothing is selected', () => {
    expect(rows.every((r) => matchesPrds(r, []))).toBe(true)
  })

  it('matches a row whose PRDs intersect the selection', () => {
    expect(rows.map((r) => matchesPrds(r, ['rental-application']))).toEqual([false, true, false])
    expect(rows.map((r) => matchesPrds(r, ['rental-application', 'rental-payment']))).toEqual([true, true, false])
  })

  it('toggles an id in and out of the selection', () => {
    expect(togglePrd([], 'rental-payment')).toEqual(['rental-payment'])
    expect(togglePrd(['rental-payment', 'rental-application'], 'rental-payment')).toEqual(['rental-application'])
  })
})
