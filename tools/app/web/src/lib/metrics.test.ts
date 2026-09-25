import { describe, it, expect } from 'vitest'
import { computeMetrics } from './metrics'
import type { GraphNode, GraphEdge, GraphStats } from './types'

const node = (
  nodeId: string,
  nodeType: string,
  extra: Partial<GraphNode> = {},
): GraphNode => ({
  nodeId,
  nodeType,
  displayLabel: nodeId.toUpperCase(),
  properties: {},
  ...extra,
})

const edge = (
  edgeId: string,
  edgeType: string,
  fromNodeId: string,
  toNodeId: string,
): GraphEdge => ({ edgeId, edgeType, fromNodeId, toNodeId, properties: {} })

// The whole-graph totals are deliberately larger than any filtered set below,
// so a metric that accidentally reads totals instead of the filtered arrays
// shows up as a wrong number rather than a coincidental match.
const totals: GraphStats = {
  totalNodes: 100,
  totalEdges: 200,
  nodesByType: {},
  edgesByType: {},
}

describe('computeMetrics', () => {
  it('reports filtered counts against whole-graph totals', () => {
    const m = computeMetrics([node('a', 'Page'), node('b', 'Field')], [], totals)

    expect(m.nodes).toEqual({ shown: 2, total: 100 })
    expect(m.edges).toEqual({ shown: 0, total: 200 })
  })

  it('counts nodes with no incident edge as orphans', () => {
    const nodes = [node('a', 'Page'), node('b', 'Field'), node('lonely', 'Page')]
    const edges = [edge('e1', 'HAS', 'a', 'b')]

    expect(computeMetrics(nodes, edges, totals).orphans).toBe(1)
  })

  it('treats a node whose only edge was filtered out as an orphan', () => {
    // 'b' is still in the node set but the edge touching it is not in `edges`.
    const nodes = [node('a', 'Page'), node('b', 'Field')]

    expect(computeMetrics(nodes, [], totals).orphans).toBe(2)
  })

  it('picks the node with the highest combined degree as the hub', () => {
    const nodes = [node('a', 'Page'), node('hub', 'Page'), node('c', 'Field')]
    const edges = [
      edge('e1', 'HAS', 'a', 'hub'),
      edge('e2', 'HAS', 'hub', 'c'),
      edge('e3', 'HAS', 'c', 'hub'),
    ]

    expect(computeMetrics(nodes, edges, totals).hub).toEqual({
      label: 'HUB',
      degree: 3,
    })
  })

  it('breaks hub ties by source order', () => {
    const nodes = [node('first', 'Page'), node('second', 'Page')]
    const edges = [edge('e1', 'HAS', 'first', 'second')]

    expect(computeMetrics(nodes, edges, totals).hub?.label).toBe('FIRST')
  })

  it('has no hub when the filtered set has no edges', () => {
    expect(computeMetrics([node('a', 'Page')], [], totals).hub).toBeNull()
  })

  it('averages degree as twice the edge count over the node count', () => {
    const nodes = [node('a', 'Page'), node('b', 'Field'), node('c', 'Field')]
    const edges = [edge('e1', 'HAS', 'a', 'b'), edge('e2', 'HAS', 'a', 'c')]

    // 2 edges * 2 endpoints / 3 nodes = 1.333...
    expect(computeMetrics(nodes, edges, totals).avgDegree).toBeCloseTo(1.333, 2)
  })

  it('counts distinct types and names the most frequent one', () => {
    const nodes = [
      node('a', 'Field'),
      node('b', 'Field'),
      node('c', 'Page'),
    ]
    const edges = [
      edge('e1', 'HAS', 'a', 'c'),
      edge('e2', 'HAS', 'b', 'c'),
      edge('e3', 'CALLS', 'c', 'a'),
    ]
    const m = computeMetrics(nodes, edges, totals)

    expect(m.nodeTypes).toEqual({ distinct: 2, top: 'Field' })
    expect(m.edgeTypes).toEqual({ distinct: 2, top: 'HAS' })
  })

  it('counts nodes carrying markdown content as a share of those in view', () => {
    const nodes = [
      node('a', 'Page', { content: '# Hi' }),
      node('b', 'Page', { content: '' }),
      node('c', 'Page'),
      node('d', 'Page'),
    ]

    // Only 'a' has non-empty content — an empty string does not count.
    expect(computeMetrics(nodes, [], totals).withContent).toEqual({
      count: 1,
      percent: 25,
    })
  })

  it('counts nodes with an empty properties object', () => {
    const nodes = [
      node('a', 'Page', { properties: { route: '/a' } }),
      node('b', 'Page'),
      node('c', 'Page'),
    ]

    expect(computeMetrics(nodes, [], totals).noProperties).toBe(2)
  })

  it('returns zeroed metrics rather than NaN when every node is filtered out', () => {
    const m = computeMetrics([], [], totals)

    expect(m.nodes).toEqual({ shown: 0, total: 100 })
    expect(m.orphans).toBe(0)
    expect(m.hub).toBeNull()
    expect(m.avgDegree).toBe(0)
    expect(m.nodeTypes).toEqual({ distinct: 0, top: null })
    expect(m.edgeTypes).toEqual({ distinct: 0, top: null })
    expect(m.withContent).toEqual({ count: 0, percent: 0 })
    expect(m.noProperties).toBe(0)
    expect(Number.isFinite(m.avgDegree)).toBe(true)
  })
})
