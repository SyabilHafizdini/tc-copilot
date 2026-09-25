import type { ReactNode } from 'react'
import { Plus, X } from 'lucide-react'

export interface GraphTab {
  id: string
  title: string
}

export interface TabBarProps {
  tabs: GraphTab[]
  activeTabId: string | null
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onAdd: () => void
}

export function TabBar({ tabs, activeTabId, onSelect, onClose, onAdd }: TabBarProps): ReactNode {
  return (
    <div
      role="tablist"
      data-testid="graph-tab-bar"
      className="flex items-center gap-1 border-b border-zinc-200 bg-white px-2 pt-1"
    >
      {tabs.map((tab) => {
        const active = tab.id === activeTabId
        return (
          <div
            key={tab.id}
            className={`flex items-center gap-1 rounded-t-md border border-b-0 px-3 py-1.5 text-xs font-medium ${
              active
                ? 'border-zinc-200 bg-white text-indigo-600'
                : 'border-transparent bg-zinc-50 text-zinc-500 hover:bg-zinc-100'
            }`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onSelect(tab.id)}
              className="max-w-64 truncate"
            >
              {tab.title}
            </button>
            <button
              type="button"
              aria-label={`Close ${tab.title}`}
              onClick={() => onClose(tab.id)}
              className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700"
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </div>
        )
      })}
      <button
        type="button"
        aria-label="Open another graph"
        onClick={onAdd}
        className="ml-1 rounded p-1 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
      >
        <Plus className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}
