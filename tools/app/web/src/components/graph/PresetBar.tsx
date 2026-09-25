import type { ReactNode } from 'react'
import type { GraphPreset } from '../../lib/types'

export interface PresetBarProps {
  presets: GraphPreset[]
  activeName: string | null
  onApply: (preset: GraphPreset) => void
  onClear: () => void
}

/** A row of named chips that apply an author-supplied filter preset. Clicking
 * the already-active chip clears back to show-all. */
export function PresetBar({ presets, activeName, onApply, onClear }: PresetBarProps): ReactNode {
  if (presets.length === 0) return null
  return (
    <div
      className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2"
      data-testid="preset-bar"
    >
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">Presets</span>
      {presets.map((p) => {
        const active = p.name === activeName
        return (
          <button
            key={p.name}
            type="button"
            title={p.description}
            aria-pressed={active}
            onClick={() => (active ? onClear() : onApply(p))}
            className={`rounded-full border px-3 py-0.5 text-xs font-medium transition-colors ${
              active
                ? 'border-indigo-600 bg-indigo-600 text-white'
                : 'border-zinc-300 bg-white text-zinc-700 hover:bg-indigo-50 hover:text-indigo-700'
            }`}
          >
            {p.name}
          </button>
        )
      })}
    </div>
  )
}
