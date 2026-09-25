import { describe, it, expect } from 'vitest'
import type { GraphDocument } from './types'
import {
  computeStats, nodeRelationships, subgraph, induceEdges,
} from './graph'

// a --KNOWS--> b --KNOWS--> c --LIKES--> d ;  e is disconnected
const g: GraphDocument = {
  nodes: [
    { nodeId: 'a', nodeType: 'Person', displayLabel: 'A', properties: {} },
    { nodeId: 'b', nodeType: 'Person', displayLabel: 'B', properties: {} },
    { nodeId: 'c', nodeType: 'Person', displayLabel: 'C', properties: {} },
    { nodeId: 'd', nodeType: 'Thing', displayLabel: 'D', properties: {} },
    { nodeId: 'e', nodeType: 'Thing', displayLabel: 'E', properties: {} },
  ],
  edges: [
    { edgeId: 'e1', edgeType: 'KNOWS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
    { edgeId: 'e2', edgeType: 'KNOWS', fromNodeId: 'b', toNodeId: 'c', properties: {} },
    { edgeId: 'e3', edgeType: 'LIKES', fromNodeId: 'c', toNodeId: 'd', properties: {} },
  ],
}

describe('computeStats', () => {
  it('counts totals and per-type', () => {
    expect(computeStats(g)).toEqual({
      totalNodes: 5,
      totalEdges: 3,
      nodesByType: { Person: 3, Thing: 2 },
      edgesByType: { KNOWS: 2, LIKES: 1 },
    })
  })
})

describe('nodeRelationships', () => {
  it('reports outgoing and incoming with snake_case keys', () => {
    expect(nodeRelationships(g, 'b')).toEqual([
      { edge_type: 'KNOWS', direction: 'incoming', source_node_id: 'a' },
      { edge_type: 'KNOWS', direction: 'outgoing', target_node_id: 'c' },
    ])
  })
  it('returns [] for isolated or unknown nodes', () => {
    expect(nodeRelationships(g, 'e')).toEqual([])
    expect(nodeRelationships(g, 'zz')).toEqual([])
  })
})

describe('subgraph', () => {
  it('BFS to depth, undirected, with induced edges', () => {
    const s = subgraph(g, 'b', 1)
    expect(s.nodes.map((n) => n.nodeId).sort()).toEqual(['a', 'b', 'c'])
    expect(s.edges.map((e) => e.edgeId).sort()).toEqual(['e1', 'e2'])
  })
  it('depth 0 is just the center node', () => {
    const s = subgraph(g, 'b', 0)
    expect(s.nodes.map((n) => n.nodeId)).toEqual(['b'])
    expect(s.edges).toEqual([])
  })
  it('unknown center returns empty', () => {
    expect(subgraph(g, 'zz', 2)).toEqual({ nodes: [], edges: [] })
  })
})

describe('induceEdges', () => {
  it('keeps only edges with both endpoints in the set', () => {
    expect(induceEdges(g.edges, new Set(['a', 'b'])).map((e) => e.edgeId)).toEqual(['e1'])
    expect(induceEdges(g.edges, new Set())).toEqual([])
  })
})
