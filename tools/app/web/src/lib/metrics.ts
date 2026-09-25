import type { GraphEdge, GraphNode, GraphStats } from './types'
import { getNodeLabel } from './nodeStyle'

export interface ShownOfTotal {
  shown: number
  total: number
}

export interface TypeSpread {
  distinct: number
  /** The most frequent type, or null when the filtered set is empty. */
  top: string | null
}

export interface Hub {
  label: string
  degree: number
}

export interface Metrics {
  nodes: ShownOfTotal
  edges: ShownOfTotal
  orphans: number
  /** Null when nothing in view carries an edge. */
  hub: Hub | null
  avgDegree: number
  nodeTypes: TypeSpread
  edgeTypes: TypeSpread
  withContent: { count: number; percent: number }
  noProperties: number
}

/** Distinct count plus the most frequent value. Ties resolve to whichever key
 * reached the winning count first, which follows source order because the
 * counts are accumulated in a single forward pass. */
function spread(values: string[]): TypeSpread {
  const counts = new Map<string, number>()
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1)

  let top: string | null = null
  let best = 0
  for (const [value, count] of counts) {
    if (count > best) {
      best = count
      top = value
    }
  }
  return { distinct: counts.size, top }
}

/**
 * Aggregate the filtered graph for the summary bar.
 *
 * `nodes` / `edges` are the filtered set — every value describes what the
 * reader can currently see. `totals` is the whole-graph stats, used only as
 * the denominator in the node and edge cards, so "of N" stays fixed while
 * filtering.
 */
export function computeMetrics(
  nodes: GraphNode[],
  edges: GraphEdge[],
  totals: GraphStats,
): Metrics {
  const degree = new Map<string, number>()
  for (const e of edges) {
    degree.set(e.fromNodeId, (degree.get(e.fromNodeId) ?? 0) + 1)
    degree.set(e.toNodeId, (degree.get(e.toNodeId) ?? 0) + 1)
  }

  let orphans = 0
  let hub: Hub | null = null
  let withContent = 0
  let noProperties = 0

  for (const n of nodes) {
    // Absent from the degree map means no edge in the *filtered* set touches
    // this node, even if the source graph connects it.
    const deg = degree.get(n.nodeId) ?? 0
    if (deg === 0) orphans++
    // Strict `>` keeps the first node at the winning degree, so ties break by
    // source order.
    if (deg > 0 && (hub === null || deg > hub.degree)) {
      hub = { label: getNodeLabel(n), degree: deg }
    }
    if (n.content) withContent++
    if (Object.keys(n.properties).length === 0) noProperties++
  }

  return {
    nodes: { shown: nodes.length, total: totals.totalNodes },
    edges: { shown: edges.length, total: totals.totalEdges },
    orphans,
    hub,
    // Each edge contributes two endpoints. Guarded so an empty view reads 0.
    avgDegree: nodes.length === 0 ? 0 : (edges.length * 2) / nodes.length,
    nodeTypes: spread(nodes.map((n) => n.nodeType)),
    edgeTypes: spread(edges.map((e) => e.edgeType)),
    withContent: {
      count: withContent,
      percent: nodes.length === 0 ? 0 : Math.round((withContent / nodes.length) * 100),
    },
    noProperties,
  }
}
