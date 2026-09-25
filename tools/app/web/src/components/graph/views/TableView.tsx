import { useMemo, useState, useCallback, Fragment } from 'react'
import type { ReactNode } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { getNodeLabel } from '../../../lib/nodeStyle'
import { useNodeColor } from '../../../lib/TypeColorContext'

export interface TableViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeSelect: (node: GraphNode) => void
}

interface Degree {
  in: number
  out: number
}

// Shared read-only fallback for nodes with no incident edges. Never stored
// into a map or mutated — buildIncidentMap always allocates a fresh
// `{ out: [], in: [] }` per node it touches, so this constant is never
// aliased into that structure.
const ZERO: Degree = { in: 0, out: 0 }

interface Incident {
  out: GraphEdge[]
  in: GraphEdge[]
}

function buildIncidentMap(edges: GraphEdge[]): Map<string, Incident> {
  const map = new Map<string, Incident>()
  const slot = (id: string): Incident => {
    let s = map.get(id)
    if (!s) {
      s = { out: [], in: [] }
      map.set(id, s)
    }
    return s
  }
  for (const e of edges) {
    slot(e.fromNodeId).out.push(e)
    slot(e.toNodeId).in.push(e)
  }
  return map
}

/** Derives a node's degree from the incident index rather than a second
 * full pass over `edges` — `incident` already holds every in/out edge per
 * node, so in/out-degree is just the length of those arrays. */
function degreeOf(incident: Map<string, Incident>, nodeId: string): Degree {
  const inc = incident.get(nodeId)
  return inc ? { in: inc.in.length, out: inc.out.length } : ZERO
}

function formatValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

const TH =
  'sticky top-0 z-10 border-b border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500'
const TD = 'border-b border-zinc-100 px-3 py-1.5 text-xs text-zinc-700'
const TOOLBAR_BUTTON =
  'rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100'

type SortKey = 'id' | 'type' | 'label' | 'in' | 'out' | 'props'

interface SortState {
  key: SortKey
  dir: 'asc' | 'desc'
}

interface Column {
  key: SortKey
  label: string
  numeric: boolean
}

const COLUMNS: Column[] = [
  { key: 'id', label: 'ID', numeric: false },
  { key: 'type', label: 'Type', numeric: false },
  { key: 'label', label: 'Label', numeric: false },
  { key: 'in', label: 'In', numeric: true },
  { key: 'out', label: 'Out', numeric: true },
  { key: 'props', label: 'Props', numeric: true },
]

function SortHeader({
  column,
  sort,
  onSort,
}: {
  column: Column
  sort: SortState | null
  onSort: (key: SortKey) => void
}): ReactNode {
  // Narrow to a plain value first — `sort?.key === column.key` does not narrow
  // `sort` to non-null for TypeScript, so reading `sort.dir` off it fails tsc.
  const dir: 'asc' | 'desc' | null =
    sort !== null && sort.key === column.key ? sort.dir : null

  return (
    <th
      scope="col"
      aria-sort={dir === null ? 'none' : dir === 'asc' ? 'ascending' : 'descending'}
      className={`${TH} ${column.numeric ? 'text-right' : 'text-left'}`}
    >
      <button
        type="button"
        onClick={() => onSort(column.key)}
        className={`inline-flex items-center gap-1 uppercase tracking-wide hover:text-indigo-700 ${
          dir === null ? '' : 'text-indigo-700'
        }`}
      >
        {column.label}
        <span aria-hidden="true" className="text-[9px]">
          {dir === null ? '' : dir === 'asc' ? '▲' : '▼'}
        </span>
      </button>
    </th>
  )
}

function NeighbourLine({
  direction,
  edgeType,
  neighbour,
  onNodeSelect,
}: {
  direction: 'out' | 'in'
  edgeType: string
  neighbour: GraphNode
  onNodeSelect: (node: GraphNode) => void
}): ReactNode {
  const arrow = direction === 'out' ? '→' : '←'
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onNodeSelect(neighbour)
      }}
      className="block text-left font-mono text-[11px] text-zinc-600 hover:text-indigo-700 hover:underline"
    >
      {`${arrow} ${edgeType} ${arrow} ${getNodeLabel(neighbour)} (${neighbour.nodeId})`}
    </button>
  )
}

function ExpandedRow({
  node,
  incident,
  nodesById,
  columnCount,
  onNodeSelect,
}: {
  node: GraphNode
  incident: Incident | undefined
  nodesById: Map<string, GraphNode>
  columnCount: number
  onNodeSelect: (node: GraphNode) => void
}): ReactNode {
  const entries = Object.entries(node.properties)
  const outEdges = incident?.out ?? []
  const inEdges = incident?.in ?? []

  return (
    <tr
      id={`table-detail-${node.nodeId}`}
      data-testid={`table-detail-${node.nodeId}`}
      className="bg-zinc-50/60"
    >
      <td colSpan={columnCount} className="border-b border-zinc-100 px-10 py-3">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
              Properties
            </p>
            {entries.length === 0 ? (
              <p className="text-xs text-zinc-500">No properties</p>
            ) : (
              <dl className="space-y-0.5">
                {entries.map(([key, value]) => {
                  const formatted = formatValue(value)
                  return (
                    <div key={key} className="flex gap-2 text-[11px]">
                      <dt className="shrink-0 font-medium text-zinc-500">{key}</dt>
                      <dd className="truncate font-mono text-zinc-700" title={formatted}>
                        {formatted}
                      </dd>
                    </div>
                  )
                })}
              </dl>
            )}
            {node.content && (
              <p className="mt-2 text-[11px] text-zinc-400">
                {`content · ${node.content.length.toLocaleString()} chars`}
              </p>
            )}
          </div>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
              Edges
            </p>
            {outEdges.length === 0 && inEdges.length === 0 ? (
              <p className="text-xs text-zinc-500">No connected edges</p>
            ) : (
              <div className="space-y-0.5">
                {outEdges.map((e) => {
                  // Invariant: filterGraph.ts only keeps edges whose endpoints
                  // are both in the filtered node set, so this lookup should
                  // always hit. If it ever misses, the miss is silent — the
                  // row's In/Out count above would overcount versus the
                  // neighbour lines actually rendered here.
                  const neighbour = nodesById.get(e.toNodeId)
                  if (!neighbour) return null
                  return (
                    <NeighbourLine
                      key={e.edgeId}
                      direction="out"
                      edgeType={e.edgeType}
                      neighbour={neighbour}
                      onNodeSelect={onNodeSelect}
                    />
                  )
                })}
                {inEdges.map((e) => {
                  // Same invariant as the out-edge loop above.
                  const neighbour = nodesById.get(e.fromNodeId)
                  if (!neighbour) return null
                  return (
                    <NeighbourLine
                      key={e.edgeId}
                      direction="in"
                      edgeType={e.edgeType}
                      neighbour={neighbour}
                      onNodeSelect={onNodeSelect}
                    />
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </td>
    </tr>
  )
}

export default function TableView({
  nodes,
  edges,
  onNodeSelect,
}: TableViewProps): ReactNode {
  const nodeColor = useNodeColor()
  const incident = useMemo(() => buildIncidentMap(edges), [edges])
  const nodesById = useMemo(
    () => new Map(nodes.map((n) => [n.nodeId, n])),
    [nodes],
  )

  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggleExpanded = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  // Seeded from `nodes` rather than `sortedNodes` — same membership, and it
  // keeps the handler independent of the current sort. Filtered-out nodes are
  // absent from `nodes`, so expand all can never open a hidden row.
  const expandAll = useCallback(() => {
    setExpanded(new Set(nodes.map((n) => n.nodeId)))
  }, [nodes])

  const collapseAll = useCallback(() => {
    setExpanded(new Set())
  }, [])

  const [sort, setSort] = useState<SortState | null>(null)

  const handleSort = useCallback((key: SortKey) => {
    setSort((prev) =>
      prev && prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    )
  }, [])

  const sortedNodes = useMemo(() => {
    if (!sort) return nodes
    // Destructure after the guard so the closure below captures plain values
    // rather than relying on narrowing to survive into a nested function.
    const { key, dir } = sort
    const valueOf = (n: GraphNode): string | number => {
      const deg = degreeOf(incident, n.nodeId)
      switch (key) {
        case 'id':
          return n.nodeId
        case 'type':
          return n.nodeType
        case 'label':
          return getNodeLabel(n)
        case 'in':
          return deg.in
        case 'out':
          return deg.out
        case 'props':
          return Object.keys(n.properties).length
      }
    }
    const sign = dir === 'asc' ? 1 : -1
    // Array.prototype.sort is stable, so ties keep source order.
    return [...nodes].sort((x, y) => {
      const a = valueOf(x)
      const b = valueOf(y)
      const cmp =
        typeof a === 'number' && typeof b === 'number'
          ? a - b
          : String(a).localeCompare(String(b))
      return cmp * sign
    })
  }, [nodes, incident, sort])

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-zinc-500">No nodes match the current filters.</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col" data-testid="table-view">
      <div className="flex items-center gap-2 border-b border-zinc-100 px-3 py-2">
        <button type="button" onClick={expandAll} className={TOOLBAR_BUTTON}>
          Expand all
        </button>
        <button type="button" onClick={collapseAll} className={TOOLBAR_BUTTON}>
          Collapse all
        </button>
      </div>
      {/* The scrollport is this inner div, not the root — `sticky top-0` on the
          header resolves against it, so the header pins below the toolbar. */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-separate border-spacing-0">
          <thead>
            <tr>
              <th scope="col" className={TH}>
                <span className="sr-only">Expand</span>
              </th>
              {COLUMNS.map((column) => (
                <SortHeader
                  key={column.key}
                  column={column}
                  sort={sort}
                  onSort={handleSort}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedNodes.map((node) => {
              const deg = degreeOf(incident, node.nodeId)
              const label = getNodeLabel(node)
              const isExpanded = expanded.has(node.nodeId)
              return (
                <Fragment key={node.nodeId}>
                  <tr
                    data-testid={`table-row-${node.nodeId}`}
                    onClick={() => onNodeSelect(node)}
                    className="cursor-pointer hover:bg-zinc-50"
                  >
                    <td className={`${TD} w-8`}>
                      <button
                        type="button"
                        aria-expanded={isExpanded}
                        aria-controls={isExpanded ? `table-detail-${node.nodeId}` : undefined}
                        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${label}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleExpanded(node.nodeId)
                        }}
                        className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700"
                      >
                        {isExpanded ? (
                          <ChevronDown className="size-3.5" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="size-3.5" aria-hidden="true" />
                        )}
                      </button>
                    </td>
                    <td className={`${TD} font-mono text-zinc-500`} data-testid="cell-id">
                      <span className="block max-w-[16rem] truncate" title={node.nodeId}>
                        {node.nodeId}
                      </span>
                    </td>
                    <td className={TD} data-testid="cell-type">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="inline-block size-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: nodeColor(node.nodeType) }}
                        />
                        {node.nodeType}
                      </span>
                    </td>
                    <td className={TD} data-testid="cell-label">
                      <button
                        type="button"
                        aria-label={`${node.nodeType}: ${label}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          onNodeSelect(node)
                        }}
                        className="max-w-[24rem] truncate text-left font-medium text-zinc-800 hover:text-indigo-700 hover:underline"
                      >
                        {label}
                      </button>
                    </td>
                    <td className={`${TD} text-right tabular-nums`} data-testid="cell-in">
                      {deg.in}
                    </td>
                    <td className={`${TD} text-right tabular-nums`} data-testid="cell-out">
                      {deg.out}
                    </td>
                    <td className={`${TD} text-right tabular-nums`} data-testid="cell-props">
                      {Object.keys(node.properties).length}
                    </td>
                  </tr>
                  {isExpanded && (
                    <ExpandedRow
                      node={node}
                      incident={incident.get(node.nodeId)}
                      nodesById={nodesById}
                      columnCount={COLUMNS.length + 1}
                      onNodeSelect={onNodeSelect}
                    />
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
