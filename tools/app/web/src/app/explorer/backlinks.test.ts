import { describe, expect, it } from 'vitest'
import { deriveBacklinks } from './backlinks'
import type { GraphModel, DocView } from './types'

const graph: GraphModel = {
  nodes: [
    { id: 'stories/US-VHLD', type: 'Story' },
    { id: 'stories/US-VHLD#AC1', type: 'AC' },
    { id: 'testcases/sit/pm/T-1', type: 'TC' },
  ],
  links: [
    { source: 'testcases/sit/pm/T-1', target: 'stories/US-VHLD#AC1', type: 'covers' },
    { source: 'stories/US-VHLD', target: 'stories/US-VHLD#AC1', type: 'has_ac' },
  ],
}
const docs = {
  'testcases/sit/pm/T-1': { ref: 'testcases/sit/pm/T-1', title: 'Access', status: 'active' },
} as unknown as Record<string, DocView>

describe('deriveBacklinks', () => {
  it('labels an AC\'s incoming covers edge as "covered by" and titles it from docs', () => {
    const groups = deriveBacklinks(graph, 'stories/US-VHLD#AC1', docs)
    const covered = groups.find((g) => g.relation === 'covered by')
    expect(covered?.entries[0]).toEqual({ ref: 'testcases/sit/pm/T-1', title: 'Access', status: 'active' })
  })

  it('labels the TC\'s outgoing covers edge as "covers"', () => {
    const groups = deriveBacklinks(graph, 'testcases/sit/pm/T-1', docs)
    expect(groups.map((g) => g.relation)).toContain('covers')
  })
})
