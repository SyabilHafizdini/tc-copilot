import { describe, it, expect } from 'vitest'
import { buildHierarchy, type TreeDatum } from './hierarchy'
import type { GraphNode, GraphEdge } from './types'

function n(id: string, type = 'Page'): GraphNode {
  return { nodeId: id, nodeType: type, displayLabel: id, properties: {} }
}

function e(from: string, to: string, type = 'REL'): GraphEdge {
  return {
    edgeId: `${from}->${to}`,
    edgeType: type,
    fromNodeId: from,
    toNodeId: to,
    properties: {},
  }
}

function collectIds(root: TreeDatum): string[] {
  const ids: string[] = []
  const walk = (d: TreeDatum) => {
    if (d.node) ids.push(d.node.nodeId)
    d.children.forEach(walk)
  }
  walk(root)
  return ids
}

describe('buildHierarchy', () => {
  it('uses the single in-degree-0 node as the real root', () => {
    const { root, crossEdgeCount } = buildHierarchy(
      [n('a'), n('b'), n('c')],
      [e('a', 'b'), e('b', 'c')],
    )
    expect(root.node?.nodeId).toBe('a')
    expect(root.children.map((c) => c.node?.nodeId)).toEqual(['b'])
    expect(root.children[0].children.map((c) => c.node?.nodeId)).toEqual(['c'])
    expect(crossEdgeCount).toBe(0)
  })

  it('records the edge used to reach each child', () => {
    const { root } = buildHierarchy([n('a'), n('b')], [e('a', 'b', 'CONTAINS')])
    expect(root.children[0].edge?.edgeType).toBe('CONTAINS')
  })

  it('creates a synthetic root over multiple roots', () => {
    const { root } = buildHierarchy(
      [n('a'), n('b'), n('x'), n('y')],
      [e('a', 'b'), e('x', 'y')],
    )
    expect(root.node).toBeNull()
    expect(root.children.map((c) => c.node?.nodeId).sort()).toEqual(['a', 'x'])
  })

  it('orders multiple roots by out-degree descending', () => {
    const { root } = buildHierarchy(
      [n('small'), n('big'), n('s1'), n('b1'), n('b2')],
      [e('small', 's1'), e('big', 'b1'), e('big', 'b2')],
    )
    expect(root.children.map((c) => c.node?.nodeId)).toEqual(['small', 'big'].reverse())
  })

  it('includes every node once even with cycles, counting cross edges', () => {
    const { root, crossEdgeCount } = buildHierarchy(
      [n('a'), n('b'), n('c')],
      [e('a', 'b'), e('b', 'c'), e('c', 'a')],
    )
    const ids = collectIds(root)
    expect([...ids].sort()).toEqual(['a', 'b', 'c'])
    expect(new Set(ids).size).toBe(3)
    // 3 edges, 2 usable as tree edges
    expect(crossEdgeCount).toBe(1)
  })

  it('handles a pure cycle (no in-degree-0 node) via max out-degree entry', () => {
    const { root } = buildHierarchy(
      [n('a'), n('b')],
      [e('a', 'b'), e('b', 'a')],
    )
    expect(collectIds(root).sort()).toEqual(['a', 'b'])
  })

  it('keeps isolated nodes as extra roots', () => {
    const { root } = buildHierarchy([n('a'), n('lone')], [])
    expect(root.node).toBeNull()
    expect(collectIds(root).sort()).toEqual(['a', 'lone'])
  })

  it('counts duplicate edges to an already-claimed child as cross edges', () => {
    const { root, crossEdgeCount } = buildHierarchy(
      [n('a'), n('b'), n('c')],
      [e('a', 'b'), e('a', 'c'), e('b', 'c')],
    )
    const cUnderA = root.children.find((x) => x.node?.nodeId === 'c')
    expect(cUnderA).toBeDefined()
    expect(crossEdgeCount).toBe(1)
  })

  it('returns an empty synthetic root for an empty graph', () => {
    const { root, crossEdgeCount } = buildHierarchy([], [])
    expect(root.node).toBeNull()
    expect(root.children).toEqual([])
    expect(crossEdgeCount).toBe(0)
  })

  it('preserves edge input order for children of the same parent', () => {
    const { root } = buildHierarchy(
      [n('a'), n('z'), n('m'), n('b')],
      [e('a', 'z'), e('a', 'm'), e('a', 'b')],
    )
    expect(root.children.map((c) => c.node?.nodeId)).toEqual(['z', 'm', 'b'])
  })
})
