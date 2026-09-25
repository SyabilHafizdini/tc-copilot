import { useState, useMemo } from 'react'
import type { ReactNode } from 'react'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { getNodeLabel } from '../../../lib/nodeStyle'
import { useNodeColor } from '../../../lib/TypeColorContext'

export interface ArcDiagramViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeSelect: (node: GraphNode) => void
}

const ROW = 22
const LABEL_COL = 200
const PAD_Y = 20
const AXIS_X = LABEL_COL + 8

function truncate(label: string): string {
  return label.length > 26 ? label.slice(0, 24) + '…' : label
}

/** Every node on one vertical axis (grouped by type, then by degree), every
 * edge as a semicircular arc to the right — the one tree-free view besides
 * force and matrix that draws ALL edges. */
export default function ArcDiagramView({
  nodes,
  edges,
  onNodeSelect,
}: ArcDiagramViewProps): ReactNode {
  const nodeColor = useNodeColor()
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const { ordered, yById } = useMemo(() => {
    const degree = new Map<string, number>()
    for (const e of edges) {
      degree.set(e.fromNodeId, (degree.get(e.fromNodeId) ?? 0) + 1)
      degree.set(e.toNodeId, (degree.get(e.toNodeId) ?? 0) + 1)
    }
    const ordered = [...nodes].sort(
      (a, b) =>
        a.nodeType.localeCompare(b.nodeType) ||
        (degree.get(b.nodeId) ?? 0) - (degree.get(a.nodeId) ?? 0) ||
        getNodeLabel(a).localeCompare(getNodeLabel(b)),
    )
    const yById = new Map(ordered.map((n, i) => [n.nodeId, PAD_Y + i * ROW + ROW / 2]))
    return { ordered, yById }
  }, [nodes, edges])

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-zinc-500">No graph data available.</p>
      </div>
    )
  }

  const height = PAD_Y * 2 + ordered.length * ROW
  const maxSpan = Math.max(ROW, ...edges.map((e) =>
    Math.abs((yById.get(e.fromNodeId) ?? 0) - (yById.get(e.toNodeId) ?? 0)),
  ))
  const width = AXIS_X + maxSpan / 2 + 60

  const isIncident = (e: GraphEdge) =>
    hoveredId !== null && (e.fromNodeId === hoveredId || e.toNodeId === hoveredId)

  const labelById = new Map(nodes.map((n) => [n.nodeId, getNodeLabel(n)]))

  return (
    <div className="h-full w-full overflow-auto" data-testid="arc-diagram">
      <svg width={width} height={height} role="img" aria-label="arc diagram visualization">
        <g className="arcs">
          {edges.map((e) => {
            const y1 = yById.get(e.fromNodeId)!
            const y2 = yById.get(e.toNodeId)!
            const incident = isIncident(e)
            const stroke = incident ? '#4F46E5' : '#d4d4d8'
            const opacity = hoveredId === null ? 0.6 : incident ? 0.9 : 0.15
            const title = `${labelById.get(e.fromNodeId)} —${e.edgeType}→ ${labelById.get(e.toNodeId)}`
            if (y1 === y2) {
              return (
                <circle
                  key={e.edgeId}
                  cx={AXIS_X + 8}
                  cy={y1}
                  r={7}
                  fill="none"
                  stroke={stroke}
                  strokeOpacity={opacity}
                  strokeWidth={incident ? 1.8 : 1.2}
                >
                  <title>{title}</title>
                </circle>
              )
            }
            const r = Math.abs(y2 - y1) / 2
            // sweep chosen so the arc always bulges right of the axis
            const sweep = y2 > y1 ? 1 : 0
            return (
              <path
                key={e.edgeId}
                d={`M ${AXIS_X} ${y1} A ${r} ${r} 0 0 ${sweep} ${AXIS_X} ${y2}`}
                fill="none"
                stroke={stroke}
                strokeOpacity={opacity}
                strokeWidth={incident ? 1.8 : 1.2}
              >
                <title>{title}</title>
              </path>
            )
          })}
        </g>
        <g className="nodes">
          {ordered.map((node) => {
            const y = yById.get(node.nodeId)!
            return (
              <g
                key={node.nodeId}
                role="button"
                tabIndex={0}
                aria-label={`${node.nodeType}: ${getNodeLabel(node)}`}
                style={{ cursor: 'pointer' }}
                onClick={() => onNodeSelect(node)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault()
                    onNodeSelect(node)
                  }
                }}
                onMouseEnter={() => setHoveredId(node.nodeId)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <text
                  x={LABEL_COL}
                  y={y}
                  dy="0.32em"
                  textAnchor="end"
                  fontSize={10}
                  fill={hoveredId === node.nodeId ? '#4F46E5' : '#374151'}
                >
                  {truncate(getNodeLabel(node))}
                </text>
                <circle
                  cx={AXIS_X}
                  cy={y}
                  r={5}
                  fill={nodeColor(node.nodeType)}
                  stroke="#fff"
                  strokeWidth={1.5}
                >
                  <title>{`${getNodeLabel(node)}\nType: ${node.nodeType}`}</title>
                </circle>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
