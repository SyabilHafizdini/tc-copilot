import { useEffect, useId, useMemo } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import type { GraphMeta, GraphPreset, GraphStats } from '../../lib/types'
import { useNodeColor } from '../../lib/TypeColorContext'

export interface AboutPanelProps {
  meta?: GraphMeta
  presets: GraphPreset[]
  stats: GraphStats
  onClose: () => void
}

const SECTION = 'text-[10px] font-semibold uppercase tracking-wide text-zinc-400'
const CHIP = 'rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-600'

/** A preset key that is absent means "no restriction", which is a different
 * statement from an empty array (show none of that kind). */
function TypeList({
  label,
  values,
  testid,
}: {
  label: string
  values: string[] | undefined
  testid: string
}): ReactNode {
  return (
    <div className="flex gap-2" data-testid={testid}>
      <span className="shrink-0 pt-0.5 text-[11px] text-zinc-400">{label}</span>
      {values === undefined ? (
        <span className="pt-0.5 text-[11px] italic text-zinc-500">all</span>
      ) : values.length === 0 ? (
        <span className="pt-0.5 text-[11px] italic text-zinc-500">none</span>
      ) : (
        <span className="flex flex-wrap gap-1">
          {values.map((v) => (
            <span key={v} className={CHIP}>
              {v}
            </span>
          ))}
        </span>
      )}
    </div>
  )
}

export default function AboutPanel({
  meta,
  presets,
  stats,
  onClose,
}: AboutPanelProps): ReactNode {
  const nodeColor = useNodeColor()
  const headingId = useId()

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const nodeTypes = useMemo(
    () => Object.entries(stats.nodesByType).sort((a, b) => b[1] - a[1]),
    [stats.nodesByType],
  )

  const shape = [
    `${stats.totalNodes.toLocaleString()} nodes`,
    `${stats.totalEdges.toLocaleString()} edges`,
    `${Object.keys(stats.nodesByType).length} node types`,
    `${Object.keys(stats.edgesByType).length} edge types`,
  ].join(' · ')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        data-testid="about-backdrop"
        onClick={onClose}
        className="absolute inset-0 bg-zinc-900/30"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        data-testid="about-panel"
        className="relative flex max-h-[80vh] w-full max-w-lg flex-col rounded-lg border border-zinc-200 bg-white shadow-xl"
      >
        <div className="flex items-start justify-between border-b border-zinc-100 px-4 py-3">
          <div className="min-w-0">
            <h2 id={headingId} className="text-sm font-semibold text-zinc-900">
              {meta?.title ?? 'Knowledge Graph Explorer'}
            </h2>
            <p data-testid="about-shape" className="mt-0.5 text-[11px] text-zinc-400">
              {shape}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close about panel"
            className="ml-3 shrink-0 rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-4 overflow-auto p-4">
          {meta?.description && (
            <p data-testid="about-description" className="text-xs leading-relaxed text-zinc-600">
              {meta.description}
            </p>
          )}

          <div>
            <p className={SECTION}>Node types</p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
              {nodeTypes.map(([type, count]) => (
                <span
                  key={type}
                  data-testid={`about-nodetype-${type}`}
                  className="inline-flex items-center gap-1.5 text-[11px] text-zinc-600"
                >
                  <span
                    className="inline-block size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: nodeColor(type) }}
                  />
                  {type}
                  <span className="tabular-nums text-zinc-400">{count}</span>
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className={SECTION}>Presets</p>
            {presets.length === 0 ? (
              <p className="mt-1.5 text-xs text-zinc-500">This graph defines no presets.</p>
            ) : (
              <div className="mt-1.5 space-y-3">
                {presets.map((p) => (
                  <div
                    key={p.name}
                    data-testid={`about-preset-${p.name}`}
                    className="rounded border border-zinc-200 px-3 py-2"
                  >
                    <p className="flex items-center gap-2 text-xs font-medium text-zinc-800">
                      {p.name}
                      {p.default && (
                        <span className="rounded bg-indigo-50 px-1.5 py-px text-[10px] font-medium text-indigo-700">
                          default
                        </span>
                      )}
                    </p>
                    {p.description && (
                      <p className="mt-0.5 text-[11px] text-zinc-500">{p.description}</p>
                    )}
                    <div className="mt-1.5 space-y-1">
                      <TypeList
                        label="Nodes"
                        values={p.nodeTypes}
                        testid="about-preset-nodetypes"
                      />
                      <TypeList
                        label="Edges"
                        values={p.edgeTypes}
                        testid="about-preset-edgetypes"
                      />
                      {p.search && (
                        <div className="flex gap-2">
                          <span className="shrink-0 text-[11px] text-zinc-400">Search</span>
                          <span className={CHIP}>{p.search}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
