import type { ReactNode } from 'react'
import { Flame, RotateCcw } from 'lucide-react'

import {
  type GraphConfig,
  DEFAULT_GRAPH_CONFIG,
} from '../../lib/useGraphConfig'

export interface AdvancedConfigDrawerProps {
  config: GraphConfig
  onConfigChange: (next: GraphConfig) => void
  onResetConfig: () => void
  onReheat: () => void
}

interface KnobSpec {
  key: keyof GraphConfig
  label: string
  min: number
  max: number
  step: number
}

const KNOBS: KnobSpec[] = [
  { key: 'linkDistance', label: 'Link distance', min: 50, max: 300, step: 5 },
  { key: 'chargeStrength', label: 'Charge strength', min: -1000, max: -100, step: 10 },
  { key: 'collideRadius', label: 'Collide radius', min: 10, max: 40, step: 1 },
  { key: 'clusterStrength', label: 'Cluster strength', min: 0, max: 0.3, step: 0.01 },
  { key: 'labelShowZoom', label: 'Show labels at zoom', min: 0.3, max: 1.5, step: 0.05 },
]

export function AdvancedConfigDrawer({
  config,
  onConfigChange,
  onResetConfig,
  onReheat,
}: AdvancedConfigDrawerProps): ReactNode {
  function update<K extends keyof GraphConfig>(key: K, value: GraphConfig[K]) {
    onConfigChange({ ...config, [key]: value })
  }

  function resetKnob(key: keyof GraphConfig) {
    onConfigChange({ ...config, [key]: DEFAULT_GRAPH_CONFIG[key] })
  }

  return (
    <div
      className="mt-2 grid gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3"
      data-testid="advanced-config-drawer"
    >
      {KNOBS.map((knob) => {
        const value = config[knob.key]
        const isDefault = value === DEFAULT_GRAPH_CONFIG[knob.key]
        return (
          <div key={knob.key} className="flex items-center gap-3">
            <label
              htmlFor={`knob-${knob.key}`}
              className="w-44 shrink-0 text-xs font-medium text-zinc-600"
            >
              {knob.label}
            </label>
            <input
              id={`knob-${knob.key}`}
              type="range"
              min={knob.min}
              max={knob.max}
              step={knob.step}
              value={value}
              onChange={(e) => update(knob.key, Number(e.target.value) as GraphConfig[typeof knob.key])}
              className="flex-1"
            />
            <span className="w-16 shrink-0 text-right font-mono text-xs text-zinc-700">
              {typeof value === 'number' ? value.toFixed(knob.step < 1 ? 2 : 0) : value}
            </span>
            <button
              type="button"
              onClick={() => resetKnob(knob.key)}
              disabled={isDefault}
              aria-label={`Reset ${knob.label}`}
              className="rounded p-1 text-zinc-400 hover:text-zinc-700 disabled:opacity-30"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          </div>
        )
      })}

      <div className="mt-1 flex justify-end gap-2 border-t border-zinc-200 pt-2">
        <button
          type="button"
          onClick={onReheat}
          className="flex items-center gap-1 rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100"
        >
          <Flame className="h-3 w-3" />
          Re-heat
        </button>
        <button
          type="button"
          onClick={onResetConfig}
          className="flex items-center gap-1 rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100"
        >
          <RotateCcw className="h-3 w-3" />
          Reset to defaults
        </button>
      </div>
    </div>
  )
}
