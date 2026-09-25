import type { ReactNode } from 'react'
import { useState, useEffect } from 'react'
import { X, Focus, Maximize2, Minimize2 } from 'lucide-react'
import type { GraphNode } from '../../lib/types'
import { NodeContent } from './NodeContent'
import { CollapsibleSection } from './CollapsibleSection'
import { useResizableWidth } from '../../lib/useResizableWidth'
import { useNodeColor } from '../../lib/TypeColorContext'

export interface NodeDetailPanelProps {
  node: GraphNode | null
  onClose: () => void
  onFocusSubgraph: (nodeId: string) => void
}

function Badge({ label, color }: { label: string; color: string }): ReactNode {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}1A`, color }}
    >
      {label}
    </span>
  )
}

export function NodeDetailPanel({ node, onClose, onFocusSubgraph }: NodeDetailPanelProps): ReactNode {
  const [expanded, setExpanded] = useState(false)
  const { width, startResize } = useResizableWidth()
  const nodeColor = useNodeColor()

  // Reset the expand state when the panel closes (node cleared).
  useEffect(() => {
    if (!node) setExpanded(false)
  }, [node])

  // While expanded, Escape collapses back to the compact panel.
  useEffect(() => {
    if (!expanded) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  if (!node) return null

  const badgeColor = nodeColor(node.nodeType)

  // Extract display properties (skip empty values)
  const displayProps = Object.entries(node.properties).filter(
    ([, v]) => v != null && v !== '' && v !== false,
  )

  // Group relationships by type
  const relationships = node.relationships ?? []
  const relByType: Record<string, Record<string, unknown>[]> = {}
  for (const rel of relationships) {
    const edgeType = (rel.edge_type as string) ?? 'related'
    if (!relByType[edgeType]) relByType[edgeType] = []
    relByType[edgeType].push(rel)
  }

  return (
    <>
      {expanded && (
        <div
          className="absolute inset-0 z-20 bg-black/30"
          data-testid="detail-backdrop"
          aria-hidden="true"
          onClick={() => setExpanded(false)}
        />
      )}
      <div
        className={
          expanded
            ? 'absolute inset-4 z-30 mx-auto max-w-[900px] overflow-y-auto rounded-lg border border-zinc-200 bg-white shadow-xl'
            : 'absolute right-3 top-3 bottom-3 z-10 overflow-y-auto rounded-lg border border-zinc-200 bg-white shadow-lg'
        }
        data-testid="graph-detail-panel"
        data-expanded={expanded}
        style={expanded ? undefined : { width }}
      >
        {!expanded && (
          <div
            data-testid="detail-resize-handle"
            onMouseDown={startResize}
            aria-hidden="true"
            className="absolute left-0 top-0 bottom-0 z-20 w-1.5 cursor-col-resize hover:bg-blue-200"
          />
        )}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-100 bg-white px-4 py-3">
          <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">Node Details</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setExpanded((e) => !e)}
              aria-pressed={expanded}
              aria-label={expanded ? 'Collapse details' : 'Expand details'}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
            >
              {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
            <button
              onClick={onClose}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
              aria-label="Close detail panel"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="space-y-4 p-4">
          {/* Node type badge and name */}
          <div>
            <Badge label={node.nodeType} color={badgeColor} />
            <h3 className="mt-2 text-sm font-semibold text-zinc-900">
              {node.displayLabel || (node.properties.name as string) || node.nodeId}
            </h3>
            <p className="mt-0.5 font-mono text-xs text-zinc-400">{node.nodeId}</p>
          </div>

          {/* Focus subgraph button */}
          <button
            type="button"
            onClick={() => onFocusSubgraph(node.nodeId)}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
          >
            <Focus className="h-3.5 w-3.5" />
            Focus Subgraph
          </button>

          {/* Content (markdown) */}
          {typeof node.content === 'string' && node.content.trim() !== '' && (
            <CollapsibleSection title="Content">
              <NodeContent markdown={node.content} />
            </CollapsibleSection>
          )}

          {/* Properties */}
          {displayProps.length > 0 && (
            <CollapsibleSection title="Properties">
              <div className="space-y-1.5">
                {displayProps.map(([key, value]) => (
                  <div key={key} className="text-sm">
                    <span className="text-zinc-500">{key.replace(/_/g, ' ')}</span>
                    <p className="break-words text-zinc-800">
                      {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                    </p>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Relationships */}
          {Object.keys(relByType).length > 0 && (
            <CollapsibleSection title={`Relationships (${relationships.length})`}>
              {Object.entries(relByType).map(([edgeType, rels]) => (
                <div key={edgeType} className="mb-2">
                  <p className="text-xs font-medium text-zinc-600">{edgeType}</p>
                  <ul className="mt-1 space-y-0.5">
                    {rels.map((rel, i) => {
                      const targetId =
                        (rel.target_node_id as string) ?? (rel.source_node_id as string) ?? ''
                      const direction = rel.direction as string | undefined
                      return (
                        <li key={i} className="flex items-center gap-1 text-xs text-zinc-600">
                          <span className="text-zinc-400">{direction === 'outgoing' ? '→' : '←'}</span>
                          <span className="truncate font-mono">{targetId}</span>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </CollapsibleSection>
          )}
        </div>
      </div>
    </>
  )
}
