import type { GraphNode, GraphEdge } from './types'

/** Node visibility + search filter, plus the induced edge set restricted to
 * visible edge types. Mirrors what the force canvas has always done, shared
 * so tree views apply identical filtering. */
export function filterGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  visibleTypes: ReadonlySet<string>,
  visibleEdgeTypes: ReadonlySet<string>,
  searchQuery: string,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const filteredNodes = nodes.filter((n) => {
    if (!visibleTypes.has(n.nodeType)) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const name = (n.properties.name as string | undefined) ?? ''
      return (
        n.displayLabel.toLowerCase().includes(q) ||
        name.toLowerCase().includes(q) ||
        n.nodeId.toLowerCase().includes(q) ||
        n.nodeType.toLowerCase().includes(q)
      )
    }
    return true
  })
  const ids = new Set(filteredNodes.map((n) => n.nodeId))
  const filteredEdges = edges.filter(
    (e) =>
      visibleEdgeTypes.has(e.edgeType) &&
      ids.has(e.fromNodeId) &&
      ids.has(e.toNodeId),
  )
  return { nodes: filteredNodes, edges: filteredEdges }
}
