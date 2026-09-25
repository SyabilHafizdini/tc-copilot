export type ViewMode = 'force' | 'tidy' | 'radial' | 'indented' | 'arc' | 'matrix' | 'table'

export interface GraphNode {
  nodeId: string
  nodeType: string
  displayLabel: string
  properties: Record<string, unknown>
  content?: string
  relationships?: Record<string, unknown>[] | null
}

export interface GraphEdge {
  edgeId: string
  edgeType: string
  fromNodeId: string
  toNodeId: string
  properties: Record<string, unknown>
}

export interface GraphMeta {
  title?: string
  description?: string
  /** Node type → hex color, layered over the built-in palette. */
  typeColors?: Record<string, string>
}

export interface GraphPreset {
  name: string
  description?: string
  default?: boolean
  nodeTypes?: string[]
  edgeTypes?: string[]
  search?: string
}

export interface GraphDocument {
  meta?: GraphMeta
  presets?: GraphPreset[]
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  totalNodes: number
  totalEdges: number
  nodesByType: Record<string, number>
  edgesByType: Record<string, number>
}
