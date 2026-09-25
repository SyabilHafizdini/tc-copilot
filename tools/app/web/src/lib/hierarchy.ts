import type { GraphNode, GraphEdge } from './types'

/** One node of the derived spanning tree. `node` is null only for the
 * synthetic root that parents multiple real roots. `edge` is the graph edge
 * used to reach this node from its tree parent (null for roots). */
export interface TreeDatum {
  node: GraphNode | null
  edge: GraphEdge | null
  children: TreeDatum[]
}

export interface HierarchyResult {
  root: TreeDatum
  /** Edges the spanning tree cannot draw (cycles, extra in-edges). */
  crossEdgeCount: number
}

/** Derive a deterministic spanning forest from a general directed graph:
 * in-degree-0 nodes become roots (highest out-degree first), directed BFS
 * claims children in edge input order, and any nodes left unreached
 * (cycles, disconnected pieces) are promoted to extra roots until every
 * node appears exactly once. */
export function buildHierarchy(
  nodes: GraphNode[],
  edges: GraphEdge[],
): HierarchyResult {
  const inDegree = new Map<string, number>()
  const outEdges = new Map<string, GraphEdge[]>()
  for (const node of nodes) {
    inDegree.set(node.nodeId, 0)
    outEdges.set(node.nodeId, [])
  }
  for (const edge of edges) {
    inDegree.set(edge.toNodeId, (inDegree.get(edge.toNodeId) ?? 0) + 1)
    outEdges.get(edge.fromNodeId)?.push(edge)
  }

  const outDegree = (id: string) => outEdges.get(id)?.length ?? 0
  const datumById = new Map<string, TreeDatum>()
  const claimed = new Set<string>()
  let treeEdgeCount = 0

  const bfsFrom = (rootNode: GraphNode): TreeDatum => {
    const rootDatum: TreeDatum = { node: rootNode, edge: null, children: [] }
    datumById.set(rootNode.nodeId, rootDatum)
    claimed.add(rootNode.nodeId)
    let frontier = [rootNode.nodeId]
    while (frontier.length > 0) {
      const next: string[] = []
      for (const id of frontier) {
        for (const edge of outEdges.get(id) ?? []) {
          if (claimed.has(edge.toNodeId)) continue
          const childNode = nodeById.get(edge.toNodeId)
          if (!childNode) continue
          const childDatum: TreeDatum = { node: childNode, edge, children: [] }
          datumById.get(id)!.children.push(childDatum)
          datumById.set(edge.toNodeId, childDatum)
          claimed.add(edge.toNodeId)
          treeEdgeCount++
          next.push(edge.toNodeId)
        }
      }
      frontier = next
    }
    return rootDatum
  }

  const nodeById = new Map(nodes.map((n) => [n.nodeId, n]))

  const naturalRoots = nodes
    .filter((n) => (inDegree.get(n.nodeId) ?? 0) === 0)
    .sort((a, b) => outDegree(b.nodeId) - outDegree(a.nodeId))

  const topLevel: TreeDatum[] = []
  for (const rootNode of naturalRoots) {
    if (!claimed.has(rootNode.nodeId)) topLevel.push(bfsFrom(rootNode))
  }

  // Leftovers: nodes only reachable through cycles or not at all.
  while (claimed.size < nodes.length) {
    let best: GraphNode | null = null
    for (const node of nodes) {
      if (claimed.has(node.nodeId)) continue
      if (!best || outDegree(node.nodeId) > outDegree(best.nodeId)) best = node
    }
    topLevel.push(bfsFrom(best!))
  }

  const root: TreeDatum =
    topLevel.length === 1
      ? topLevel[0]
      : { node: null, edge: null, children: topLevel }

  return { root, crossEdgeCount: edges.length - treeEdgeCount }
}
