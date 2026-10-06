import { afterEach, describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, applyFilters, parseFilters, readHashQuery, serializeFilters, writeHashQuery } from './filters'
import { PAYLOAD } from './fixtures'

afterEach(() => { window.location.hash = '' })

describe('parseFilters / serializeFilters', () => {
  it('round-trips every filter', () => {
    const f = { level: 'sit' as const, group: 'run:sit:Main flow', story: 'US-DEMO-001', status: 'active', confidence: ['Medium' as const, 'Low' as const], prds: ['rental-application', 'rental-payment'] }
    expect(parseFilters(serializeFilters(f))).toEqual(f)
  })

  it('reads the prd key as a comma list, dropping empties and repeats', () => {
    expect(parseFilters('prd=rental-payment,,rental-application,rental-payment').prds).toEqual(['rental-payment', 'rental-application'])
    expect(serializeFilters({ ...EMPTY_FILTERS, prds: ['rental-payment'] })).toBe('prd=rental-payment')
  })

  it('an empty query is no filter and serialises to nothing', () => {
    expect(parseFilters('')).toEqual(EMPTY_FILTERS)
    expect(serializeFilters(EMPTY_FILTERS)).toBe('')
  })

  it('drops values it does not know instead of throwing', () => {
    expect(parseFilters('level=osat&confidence=Low,Huge,&zzz=1')).toEqual({ ...EMPTY_FILTERS, confidence: ['Low'] })
  })
})

describe('applyFilters', () => {
  const ids = (f: Partial<typeof EMPTY_FILTERS>) => applyFilters(PAYLOAD.rows, { ...EMPTY_FILTERS, ...f }).map((r) => r.id)

  it('no filter keeps every row in order', () => {
    expect(ids({})).toEqual(PAYLOAD.rows.map((r) => r.id))
  })
  it('filters by level, group, story and status', () => {
    expect(ids({ level: 'uat' })).toEqual(['UAT-1.1-AC01-01'])
    expect(ids({ group: 'run:sit:Variant flow' })).toEqual(['1.1-AC01-02'])
    expect(ids({ story: 'US-DEMO-002' })).toEqual(['1.1-AC01-02'])
    expect(ids({ status: 'stale' })).toEqual(['1.1-AC02-02'])
  })
  it('confidence keeps any of the chosen overall levels', () => {
    expect(ids({ confidence: ['Low', 'Medium'] })).toEqual(['1.1-AC01-01', '1.1-AC02-01'])
  })
  it('prds keeps rows drawing on any selected PRD', () => {
    const rows = [{ ...PAYLOAD.rows[0], prds: ['a-prd'] }, { ...PAYLOAD.rows[1], prds: ['b-prd'] }, PAYLOAD.rows[2]]
    const got = (prds: string[]) => applyFilters(rows, { ...EMPTY_FILTERS, prds }).map((r) => r.id)
    expect(got(['a-prd'])).toEqual(['1.1-AC01-01'])
    expect(got(['a-prd', 'b-prd'])).toEqual(['1.1-AC01-01', '1.1-AC02-01'])
    expect(got([])).toHaveLength(3)
  })
  it('filters combine', () => {
    expect(ids({ level: 'sit', confidence: ['High'], status: 'active' })).toEqual(['1.1-AC01-02'])
  })
})

describe('hash query', () => {
  it('reads the query after the route', () => {
    window.location.hash = '#/testcases?level=sit&confidence=Low'
    expect(readHashQuery()).toBe('level=sit&confidence=Low')
    window.location.hash = '#/testcases'
    expect(readHashQuery()).toBe('')
  })
  it('writes the query without leaving the route', () => {
    window.location.hash = '#/testcases?level=uat'
    writeHashQuery('level=sit')
    expect(window.location.hash).toBe('#/testcases?level=sit')
    writeHashQuery('')
    expect(window.location.hash).toBe('#/testcases')
  })
})
