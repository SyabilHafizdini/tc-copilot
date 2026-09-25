import type { GraphDocument } from '../../lib/types'
import type { GraphLinkRaw, GraphNodeRaw } from './types'

export function toGraphDocument(nodes: GraphNodeRaw[], links: GraphLinkRaw[]): GraphDocument {
  return {
    nodes: nodes.map(({ id, type, label, ...rest }) => ({
      nodeId: id, nodeType: type, displayLabel: label ?? id, properties: rest,
    })),
    edges: links.map((l, i) => ({
      edgeId: `e${i + 1}`, edgeType: l.type,
      fromNodeId: l.source, toNodeId: l.target, properties: {},
    })),
  }
}
