import type { ReactNode } from 'react'
import { useState } from 'react'
import { RotateCcw, Search, Settings2 } from 'lucide-react'
import type { GraphStats } from '../../lib/types'
import type { GraphConfig } from '../../lib/useGraphConfig'
import { useNodeColor } from '../../lib/TypeColorContext'
import { AdvancedConfigDrawer } from './AdvancedConfigDrawer'

export interface GraphControlsProps {
  allNodeTypes: string[]
  visibleTypes: Set<string>
  onSetVisibleTypes: (next: Set<string>) => void
  allEdgeTypes: string[]
  visibleEdgeTypes: Set<string>
  onSetVisibleEdgeTypes: (next: Set<string>) => void
  searchQuery: string
  onSearchChange: (query: string) => void
  subgraphDepth: number
  onDepthChange: (depth: number) => void
  focusedNodeId: string | null
  onResetView: () => void
  // Advanced config (Task 9):
  config: GraphConfig
  onConfigChange: (next: GraphConfig) => void
  onResetConfig: () => void
  onReheat: () => void
  /** Physics config only applies to the force view; hide the toggle elsewhere. */
  showAdvanced?: boolean
}

export function GraphControls({
  allNodeTypes,
  visibleTypes,
  onSetVisibleTypes,
  allEdgeTypes,
  visibleEdgeTypes,
  onSetVisibleEdgeTypes,
  searchQuery,
  onSearchChange,
  subgraphDepth,
  onDepthChange,
  focusedNodeId,
  onResetView,
  config,
  onConfigChange,
  onResetConfig,
  onReheat,
  showAdvanced = true,
}: GraphControlsProps): ReactNode {
  const nodeColor = useNodeColor()
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const makeToggle =
    (visible: Set<string>, onSet: (next: Set<string>) => void) =>
    (type: string) => {
      const next = new Set(visible)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      onSet(next)
    }

  const makeIsolate =
    (all: string[], visible: Set<string>, onSet: (next: Set<string>) => void) =>
    (type: string) => {
      // Already isolated to this one → restore all (double-click is its own undo).
      if (visible.size === 1 && visible.has(type)) onSet(new Set(all))
      else onSet(new Set([type]))
    }

  const toggleNodeType = makeToggle(visibleTypes, onSetVisibleTypes)
  const isolateNodeType = makeIsolate(allNodeTypes, visibleTypes, onSetVisibleTypes)
  const toggleEdgeType = makeToggle(visibleEdgeTypes, onSetVisibleEdgeTypes)
  const isolateEdgeType = makeIsolate(allEdgeTypes, visibleEdgeTypes, onSetVisibleEdgeTypes)

  return (
    <div className="rounded-lg border border-zinc-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search nodes..."
            className="h-8 w-48 rounded border border-zinc-200 bg-zinc-50 pl-7 pr-2 text-xs text-zinc-700 placeholder:text-zinc-400 focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
          />
        </div>

        {/* Node type filters */}
        <div className="flex flex-wrap items-center gap-1.5">
          {allNodeTypes.map((type) => {
            const active = visibleTypes.has(type)
            const color = nodeColor(type)
            return (
              <button
                key={type}
                type="button"
                onClick={() => toggleNodeType(type)}
                onDoubleClick={() => isolateNodeType(type)}
                title="Click to toggle · double-click to isolate"
                className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors ${
                  active
                    ? 'border-zinc-300 bg-white text-zinc-700'
                    : 'border-zinc-200 bg-zinc-100 text-zinc-400 line-through'
                }`}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: active ? color : '#d4d4d8' }}
                />
                {type}
              </button>
            )
          })}
          <button
            type="button"
            onClick={() => onSetVisibleTypes(new Set(allNodeTypes))}
            className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onSetVisibleTypes(new Set())}
            className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
          >
            None
          </button>
        </div>

        {/* Edge type filters */}
        {allEdgeTypes.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-l border-zinc-200 pl-3">
            <span className="text-xs text-zinc-400">Edges:</span>
            {allEdgeTypes.map((type) => {
              const active = visibleEdgeTypes.has(type)
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleEdgeType(type)}
                  onDoubleClick={() => isolateEdgeType(type)}
                  title="Click to toggle · double-click to isolate"
                  className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors ${
                    active
                      ? 'border-zinc-300 bg-white text-zinc-700'
                      : 'border-zinc-200 bg-zinc-100 text-zinc-400 line-through'
                  }`}
                >
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: active ? '#a1a1aa' : '#d4d4d8' }}
                  />
                  {type}
                </button>
              )
            })}
          </div>
        )}

        {/* Depth selector (visible in subgraph/focus mode) */}
        {focusedNodeId && (
          <div className="flex items-center gap-1.5 text-xs text-zinc-600">
            <span>Depth:</span>
            {[1, 2, 3].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => onDepthChange(d)}
                className={`h-6 w-6 rounded text-xs font-medium ${
                  subgraphDepth === d
                    ? 'bg-blue-600 text-white'
                    : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        )}

        {/* Reset view */}
        <button
          type="button"
          onClick={onResetView}
          className="flex items-center gap-1 rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-100"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>

        {/* Advanced config toggle */}
        {showAdvanced && (
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          aria-pressed={advancedOpen}
          aria-label="Toggle advanced layout config"
          className={`flex items-center gap-1 rounded border px-2 py-1 text-xs ${
            advancedOpen
              ? 'border-blue-300 bg-blue-50 text-blue-700'
              : 'border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100'
          }`}
        >
          <Settings2 className="h-3 w-3" />
          Advanced
        </button>
        )}

      </div>
      {showAdvanced && advancedOpen && (
        <AdvancedConfigDrawer
          config={config}
          onConfigChange={onConfigChange}
          onResetConfig={onResetConfig}
          onReheat={onReheat}
        />
      )}
    </div>
  )
}
