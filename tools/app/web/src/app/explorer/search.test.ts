import { describe, expect, it } from 'vitest'
import { searchDocs, facetOptions } from './search'
import type { DocView } from './types'

const mk = (ref: string, title: string, body: string, f: Partial<DocView['facets']>): DocView => ({
  ref, kind: f.kind ?? 'stories', title, status: f.status ?? 'active', version: 1,
  fields: [], body_md: body,
  facets: { kind: f.kind ?? 'stories', status: f.status ?? 'active', origin_state: f.origin_state ?? 'asserted',
            story: f.story ?? null, asserted_by: f.asserted_by ?? null, stale: !!f.stale, staleness_causes: f.staleness_causes ?? [] },
})
const docs = {
  'stories/US-VHLD': mk('stories/US-VHLD', 'Vehicle Holding', 'dashboard filters', { kind: 'stories' }),
  'testcases/T-1': mk('testcases/T-1', 'Access dashboard', 'login side menu', { kind: 'testcases', status: 'stale', staleness_causes: ['prd_changed'] }),
}

describe('searchDocs', () => {
  it('matches title and body, title hits first', () => {
    expect(searchDocs(docs, 'dashboard', {})).toEqual(['testcases/T-1', 'stories/US-VHLD'])
  })
  it('filters by facet', () => {
    expect(searchDocs(docs, '', { kind: new Set(['stories']) })).toEqual(['stories/US-VHLD'])
  })
  it('empty query + no facets returns everything', () => {
    expect(new Set(searchDocs(docs, '', {}))).toEqual(new Set(['stories/US-VHLD', 'testcases/T-1']))
  })
})

describe('facetOptions', () => {
  it('lists distinct staleness causes', () => {
    expect(facetOptions(docs).staleness_cause).toEqual(['prd_changed'])
  })
})
