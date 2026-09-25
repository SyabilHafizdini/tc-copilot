import type { GraphDocument, GraphEdge, GraphNode, GraphStats } from './types'

export function computeStats(g: GraphDocument): GraphStats {
  const nodesByType: Record<string, number> = {}
  for (const n of g.nodes) nodesByType[n.nodeType] = (nodesByType[n.nodeType] ?? 0) + 1
  const edgesByType: Record<string, number> = {}
  for (const e of g.edges) edgesByType[e.edgeType] = (edgesByType[e.edgeType] ?? 0) + 1
  return {
    totalNodes: g.nodes.length,
    totalEdges: g.edges.length,
    nodesByType,
    edgesByType,
  }
}

export interface NodeRelationship {
  edge_type: string
  direction: 'outgoing' | 'incoming'
  target_node_id?: string
  source_node_id?: string
}

export function nodeRelationships(g: GraphDocument, nodeId: string): NodeRelationship[] {
  const rels: NodeRelationship[] = []
  for (const e of g.edges) {
    if (e.fromNodeId === nodeId) {
      rels.push({ edge_type: e.edgeType, direction: 'outgoing', target_node_id: e.toNodeId })
    } else if (e.toNodeId === nodeId) {
      rels.push({ edge_type: e.edgeType, direction: 'incoming', source_node_id: e.fromNodeId })
    }
  }
  return rels
}

/** Undirected adjacency, optionally restricted to a set of edge types. */
function buildAdjacency(
  g: GraphDocument,
  edgeTypes?: ReadonlySet<string>,
): Map<string, string[]> {
  const adj = new Map<string, string[]>()
  for (const e of g.edges) {
    if (edgeTypes && !edgeTypes.has(e.edgeType)) continue
    if (!adj.has(e.fromNodeId)) adj.set(e.fromNodeId, [])
    if (!adj.has(e.toNodeId)) adj.set(e.toNodeId, [])
    adj.get(e.fromNodeId)!.push(e.toNodeId)
    adj.get(e.toNodeId)!.push(e.fromNodeId)
  }
  return adj
}

/** BFS from start up to `depth` hops. Returns visited ids in BFS order. */
function bfs(
  g: GraphDocument,
  startNodeId: string,
  depth: number,
  edgeTypes?: ReadonlySet<string>,
): string[] {
  if (!g.nodes.some((n) => n.nodeId === startNodeId)) return []
  const adj = buildAdjacency(g, edgeTypes)
  const visited = new Set<string>([startNodeId])
  let frontier = [startNodeId]
  for (let d = 0; d < depth && frontier.length > 0; d++) {
    const next: string[] = []
    for (const id of frontier) {
      for (const nb of adj.get(id) ?? []) {
        if (!visited.has(nb)) {
          visited.add(nb)
          next.push(nb)
        }
      }
    }
    frontier = next
  }
  return [...visited]
}

export function subgraph(
  g: GraphDocument,
  centerNodeId: string,
  depth: number,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const ids = new Set(bfs(g, centerNodeId, depth))
  if (ids.size === 0) return { nodes: [], edges: [] }
  return {
    nodes: g.nodes.filter((n) => ids.has(n.nodeId)),
    edges: induceEdges(g.edges, ids),
  }
}

/** Return the edges from `all` that have both endpoints in `nodeIds`. */
export function induceEdges(
  all: ReadonlyArray<GraphEdge>,
  nodeIds: ReadonlySet<string>,
): GraphEdge[] {
  if (nodeIds.size === 0) return []
  return all.filter((e) => nodeIds.has(e.fromNodeId) && nodeIds.has(e.toNodeId))
}
