import { useState, useMemo, useCallback } from 'react'
import type { ReactNode } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { buildHierarchy, type TreeDatum } from '../../../lib/hierarchy'
import { getNodeLabel } from '../../../lib/nodeStyle'
import { useNodeColor } from '../../../lib/TypeColorContext'

export interface IndentedTreeViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeSelect: (node: GraphNode) => void
}

function Row({
  datum,
  depth,
  collapsed,
  onToggle,
  onNodeSelect,
}: {
  datum: TreeDatum
  depth: number
  collapsed: ReadonlySet<string>
  onToggle: (id: string) => void
  onNodeSelect: (node: GraphNode) => void
}): ReactNode {
  const nodeColor = useNodeColor()
  const node = datum.node!
  const hasChildren = datum.children.length > 0
  const isCollapsed = collapsed.has(node.nodeId)

  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        onClick={() => onNodeSelect(node)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onNodeSelect(node)
          }
        }}
        className="flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 text-xs hover:bg-zinc-50"
        style={{ paddingLeft: `${depth * 20 + 6}px` }}
        data-testid={`indented-row-${node.nodeId}`}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={`${isCollapsed ? 'Expand' : 'Collapse'} ${getNodeLabel(node)}`}
            aria-expanded={!isCollapsed}
            onClick={(e) => {
              e.stopPropagation()
              onToggle(node.nodeId)
            }}
            className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700"
          >
            {isCollapsed ? (
              <ChevronRight className="size-3.5" aria-hidden="true" />
            ) : (
              <ChevronDown className="size-3.5" aria-hidden="true" />
            )}
          </button>
        ) : (
          <span className="inline-block w-[18px]" />
        )}
        <span
          className="inline-block size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: nodeColor(node.nodeType) }}
        />
        <span className="truncate font-medium text-zinc-800">{getNodeLabel(node)}</span>
        <span className="shrink-0 rounded bg-zinc-100 px-1.5 py-px text-[10px] text-zinc-500">
          {node.nodeType}
        </span>
        {datum.edge && (
          <span className="shrink-0 text-[10px] text-zinc-400">
            via {datum.edge.edgeType}
          </span>
        )}
      </div>
      {hasChildren && !isCollapsed && (
        <ul>
          {datum.children.map((child) => (
            <Row
              key={child.node!.nodeId}
              datum={child}
              depth={depth + 1}
              collapsed={collapsed}
              onToggle={onToggle}
              onNodeSelect={onNodeSelect}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function IndentedTreeView({
  nodes,
  edges,
  onNodeSelect,
}: IndentedTreeViewProps): ReactNode {
  const { root, crossEdgeCount } = useMemo(
    () => buildHierarchy(nodes, edges),
    [nodes, edges],
  )

  // A synthetic root isn't a real node — its children become top-level rows.
  const topLevel = root.node === null ? root.children : [root]

  const allParentIds = useMemo(() => {
    const ids: string[] = []
    const walk = (d: TreeDatum) => {
      if (d.node && d.children.length > 0) ids.push(d.node.nodeId)
      d.children.forEach(walk)
    }
    walk(root)
    return ids
  }, [root])

  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const handleToggle = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-zinc-500">No graph data available.</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-zinc-100 px-3 py-2">
        <button
          type="button"
          onClick={() => setCollapsed(new Set())}
          className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100"
        >
          Expand all
        </button>
        <button
          type="button"
          onClick={() => setCollapsed(new Set(allParentIds))}
          className="rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100"
        >
          Collapse all
        </button>
        {crossEdgeCount > 0 && (
          <span data-testid="cross-edge-caption" className="ml-auto text-xs text-zinc-400">
            {crossEdgeCount} cross-link{crossEdgeCount === 1 ? '' : 's'} not shown
          </span>
        )}
      </div>
      <ul className="flex-1 overflow-auto p-2" data-testid="indented-tree">
        {topLevel.map((datum) => (
          <Row
            key={datum.node!.nodeId}
            datum={datum}
            depth={0}
            collapsed={collapsed}
            onToggle={handleToggle}
            onNodeSelect={onNodeSelect}
          />
        ))}
      </ul>
    </div>
  )
}
