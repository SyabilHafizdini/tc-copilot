import { describe, expect, it } from 'vitest'
import { toGraphDocument } from './graphAdapter'

describe('toGraphDocument', () => {
  it('renames internal fields to the viewer format without flipping edges', () => {
    const doc = toGraphDocument(
      [{ id: 'a', type: 'Story', label: 'A', state: 'aligned' }],
      [{ source: 'a', target: 'b', type: 'covers' }],
    )
    expect(doc.nodes[0]).toMatchObject({ nodeId: 'a', nodeType: 'Story', displayLabel: 'A' })
    expect(doc.nodes[0].properties).toMatchObject({ state: 'aligned' })
    expect(doc.edges[0]).toMatchObject({ edgeType: 'covers', fromNodeId: 'a', toNodeId: 'b' })
  })
})
