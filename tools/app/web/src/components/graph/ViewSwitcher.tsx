import type { ReactNode } from 'react'
import { Waypoints, Network, Orbit, ListTree, Spline, Table, Rows3 } from 'lucide-react'

import type { ViewMode } from '../../lib/types'
export type { ViewMode }

const VIEWS: {
  mode: ViewMode
  label: string
  Icon: typeof Waypoints
  description: string
}[] = [
  {
    mode: 'force',
    label: 'Force',
    Icon: Waypoints,
    description: 'Force-directed layout — every edge drawn, drag & physics',
  },
  {
    mode: 'tidy',
    label: 'Tidy tree',
    Icon: Network,
    description: 'Left-to-right hierarchy derived from the graph',
  },
  {
    mode: 'radial',
    label: 'Radial',
    Icon: Orbit,
    description: 'The same hierarchy bent around a circle',
  },
  {
    mode: 'indented',
    label: 'Indented',
    Icon: ListTree,
    description: 'Collapsible outline — best for scanning many labels',
  },
  {
    mode: 'arc',
    label: 'Arc',
    Icon: Spline,
    description: 'All nodes on one axis, every edge as an arc',
  },
  {
    mode: 'matrix',
    label: 'Matrix',
    Icon: Table,
    description: 'Adjacency matrix — one colored cell per relation',
  },
  {
    mode: 'table',
    label: 'Table',
    Icon: Rows3,
    description: 'Every node as a row — sortable, expandable',
  },
]

export function ViewSwitcher({
  mode,
  onModeChange,
}: {
  mode: ViewMode
  onModeChange: (mode: ViewMode) => void
}): ReactNode {
  const active = VIEWS.find((v) => v.mode === mode) ?? VIEWS[0]
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
          View
        </span>
        <div
          role="group"
          aria-label="Graph view"
          className="inline-flex overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm"
        >
          {VIEWS.map(({ mode: m, label, Icon, description }) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              title={description}
              onClick={() => onModeChange(m)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                mode === m
                  ? 'bg-indigo-600 text-white'
                  : 'text-zinc-600 hover:bg-indigo-50 hover:text-indigo-700'
              }`}
            >
              <Icon className="size-3.5" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-zinc-400" data-testid="view-description">
        {active.description}
      </p>
    </div>
  )
}
