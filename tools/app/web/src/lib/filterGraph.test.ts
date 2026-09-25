import { describe, it, expect } from 'vitest'
import { filterGraph } from './filterGraph'
import type { GraphNode, GraphEdge } from './types'

const nodes: GraphNode[] = [
  { nodeId: 'p1', nodeType: 'Page', displayLabel: 'Login Page', properties: {} },
  { nodeId: 'c1', nodeType: 'Component', displayLabel: 'Form', properties: { name: 'LoginForm' } },
  { nodeId: 'f1', nodeType: 'Field', displayLabel: 'Email', properties: {} },
]

const edges: GraphEdge[] = [
  { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'p1', toNodeId: 'c1', properties: {} },
  { edgeId: 'e2', edgeType: 'HAS_FIELD', fromNodeId: 'c1', toNodeId: 'f1', properties: {} },
]

const allTypes = new Set(['Page', 'Component', 'Field'])
const allEdgeTypes = new Set(['CONTAINS', 'HAS_FIELD'])

describe('filterGraph', () => {
  it('passes everything through with no filters', () => {
    const r = filterGraph(nodes, edges, allTypes, allEdgeTypes, '')
    expect(r.nodes).toHaveLength(3)
    expect(r.edges).toHaveLength(2)
  })

  it('drops hidden node types and their edges', () => {
    const r = filterGraph(nodes, edges, new Set(['Page', 'Component']), allEdgeTypes, '')
    expect(r.nodes.map((n) => n.nodeId)).toEqual(['p1', 'c1'])
    expect(r.edges.map((e) => e.edgeId)).toEqual(['e1'])
  })

  it('drops hidden edge types', () => {
    const r = filterGraph(nodes, edges, allTypes, new Set(['CONTAINS']), '')
    expect(r.nodes).toHaveLength(3)
    expect(r.edges.map((e) => e.edgeId)).toEqual(['e1'])
  })

  it('matches search against label, name, id, and type', () => {
    expect(filterGraph(nodes, edges, allTypes, allEdgeTypes, 'loginform').nodes.map((n) => n.nodeId)).toEqual(['c1'])
    expect(filterGraph(nodes, edges, allTypes, allEdgeTypes, 'field').nodes.map((n) => n.nodeId)).toEqual(['f1'])
    expect(filterGraph(nodes, edges, allTypes, allEdgeTypes, 'p1').nodes.map((n) => n.nodeId)).toEqual(['p1'])
  })
})
