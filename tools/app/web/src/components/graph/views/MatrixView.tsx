import { useMemo } from 'react'
import type { ReactNode } from 'react'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { getNodeLabel } from '../../../lib/nodeStyle'
import { useNodeColor } from '../../../lib/TypeColorContext'

export interface MatrixViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeSelect: (node: GraphNode) => void
}

const CELL = 16
const MARGIN_LEFT = 190
const MARGIN_TOP = 130

function truncate(label: string): string {
  return label.length > 26 ? label.slice(0, 24) + '…' : label
}

/** Adjacency matrix: rows are edge sources, columns are targets, one cell
 * per edge colored by edge type. Shows every edge; scales to dense graphs
 * where drawn links would be hairballs. */
export default function MatrixView({
  nodes,
  edges,
  onNodeSelect,
}: MatrixViewProps): ReactNode {
  const nodeColor = useNodeColor()
  const { ordered, indexById, cells, edgeTypes, edgeColor } = useMemo(() => {
    const ordered = [...nodes].sort(
      (a, b) =>
        a.nodeType.localeCompare(b.nodeType) ||
        getNodeLabel(a).localeCompare(getNodeLabel(b)),
    )
    const indexById = new Map(ordered.map((n, i) => [n.nodeId, i]))
    // Group parallel edges into one cell.
    const byCell = new Map<string, GraphEdge[]>()
    for (const e of edges) {
      const key = `${e.fromNodeId}\u0000${e.toNodeId}`
      const list = byCell.get(key)
      if (list) list.push(e)
      else byCell.set(key, [e])
    }
    const cells = [...byCell.values()]
    const edgeTypes = [...new Set(edges.map((e) => e.edgeType))].sort()
    const edgeColor = d3.scaleOrdinal<string, string>(d3.schemeTableau10).domain(edgeTypes)
    return { ordered, indexById, cells, edgeTypes, edgeColor }
  }, [nodes, edges])

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-zinc-500">No graph data available.</p>
      </div>
    )
  }

  const n = ordered.length
  const width = MARGIN_LEFT + n * CELL + 40
  const height = MARGIN_TOP + n * CELL + 20
  const labelById = new Map(nodes.map((node) => [node.nodeId, getNodeLabel(node)]))

  const nodeLabelProps = (node: GraphNode) => ({
    role: 'button' as const,
    tabIndex: 0,
    style: { cursor: 'pointer' },
    onClick: () => onNodeSelect(node),
    onKeyDown: (ev: React.KeyboardEvent) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault()
        onNodeSelect(node)
      }
    },
  })

  return (
    <div className="flex h-full flex-col" data-testid="matrix-view">
      {edgeTypes.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 border-b border-zinc-100 px-3 py-2 text-xs text-zinc-600">
          <span className="text-zinc-400">Rows → columns:</span>
          {edgeTypes.map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block size-2.5 rounded-sm"
                style={{ backgroundColor: edgeColor(t) }}
              />
              {t}
            </span>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <svg width={width} height={height} role="img" aria-label="adjacency matrix visualization">
          {/* grid */}
          <g className="grid" stroke="#f4f4f5">
            {ordered.map((_, i) => (
              <line
                key={`h${i}`}
                x1={MARGIN_LEFT}
                x2={MARGIN_LEFT + n * CELL}
                y1={MARGIN_TOP + i * CELL}
                y2={MARGIN_TOP + i * CELL}
              />
            ))}
            {ordered.map((_, j) => (
              <line
                key={`v${j}`}
                y1={MARGIN_TOP}
                y2={MARGIN_TOP + n * CELL}
                x1={MARGIN_LEFT + j * CELL}
                x2={MARGIN_LEFT + j * CELL}
              />
            ))}
          </g>
          {/* row labels (sources) */}
          <g className="row-labels">
            {ordered.map((node, i) => (
              <g key={node.nodeId} {...nodeLabelProps(node)} aria-label={`${node.nodeType}: ${getNodeLabel(node)}`}>
                <circle
                  cx={MARGIN_LEFT - 10}
                  cy={MARGIN_TOP + i * CELL + CELL / 2}
                  r={4}
                  fill={nodeColor(node.nodeType)}
                />
                <text
                  x={MARGIN_LEFT - 18}
                  y={MARGIN_TOP + i * CELL + CELL / 2}
                  dy="0.32em"
                  textAnchor="end"
                  fontSize={10}
                  fill="#374151"
                >
                  {truncate(getNodeLabel(node))}
                </text>
              </g>
            ))}
          </g>
          {/* column labels (targets), tilted */}
          <g className="col-labels">
            {ordered.map((node, j) => (
              <g key={node.nodeId} {...nodeLabelProps(node)}>
                <text
                  transform={`translate(${MARGIN_LEFT + j * CELL + CELL / 2}, ${MARGIN_TOP - 8}) rotate(-55)`}
                  fontSize={10}
                  fill="#374151"
                >
                  {truncate(getNodeLabel(node))}
                </text>
              </g>
            ))}
          </g>
          {/* one cell per source→target pair */}
          <g className="cells">
            {cells.map((group) => {
              const first = group[0]
              const i = indexById.get(first.fromNodeId)!
              const j = indexById.get(first.toNodeId)!
              const types = [...new Set(group.map((e) => e.edgeType))]
              return (
                <rect
                  key={`${first.fromNodeId}-${first.toNodeId}`}
                  x={MARGIN_LEFT + j * CELL + 1.5}
                  y={MARGIN_TOP + i * CELL + 1.5}
                  width={CELL - 3}
                  height={CELL - 3}
                  rx={2}
                  fill={edgeColor(types[0])}
                  fillOpacity={0.85}
                >
                  <title>
                    {`${labelById.get(first.fromNodeId)} → ${labelById.get(first.toNodeId)}\n${types.join(', ')}`}
                  </title>
                </rect>
              )
            })}
          </g>
        </svg>
      </div>
    </div>
  )
}
