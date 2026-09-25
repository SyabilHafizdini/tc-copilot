import type { ReactNode } from 'react'
import { CollapsibleSection } from './CollapsibleSection'
import type { Metrics } from '../../lib/metrics'

export interface MetricCardsProps {
  metrics: Metrics
}

function Card({
  id,
  label,
  value,
  caption,
}: {
  id: string
  label: string
  value: string
  caption: string
}): ReactNode {
  return (
    <div
      data-testid={`metric-${id}`}
      className="rounded border border-zinc-200 bg-white px-3 py-2"
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        {label}
      </p>
      <p className="truncate text-lg font-semibold tabular-nums text-zinc-800" title={value}>
        {value}
      </p>
      <p className="truncate text-[11px] text-zinc-500" title={caption}>
        {caption}
      </p>
    </div>
  )
}

export default function MetricCards({ metrics }: MetricCardsProps): ReactNode {
  const {
    nodes,
    edges,
    orphans,
    hub,
    avgDegree,
    nodeTypes,
    edgeTypes,
    withContent,
    noProperties,
  } = metrics

  const shownOfTotal = (v: { shown: number; total: number }): string =>
    `${v.shown.toLocaleString()} of ${v.total.toLocaleString()}`

  const summary = `${shownOfTotal(nodes)} nodes · ${shownOfTotal(edges)} edges`

  return (
    <div className="mt-3" data-testid="metric-cards">
      {/* Collapsed by default: nine open cards squeeze the force and matrix
          canvases badly on a short window. The summary line keeps the headline
          counts visible without costing that height. */}
      <CollapsibleSection title="Summary" summary={summary} defaultOpen={false}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <Card id="nodes" label="Nodes" value={shownOfTotal(nodes)} caption="in view" />
          <Card id="edges" label="Edges" value={shownOfTotal(edges)} caption="in view" />
          <Card
            id="orphans"
            label="Orphans"
            value={orphans.toLocaleString()}
            caption="no edges in view"
          />
          <Card
            id="hub"
            label="Most connected"
            value={hub ? hub.label : '—'}
            caption={hub ? `${hub.degree} edge${hub.degree === 1 ? '' : 's'}` : 'no edges in view'}
          />
          <Card
            id="avg-degree"
            label="Avg degree"
            value={avgDegree.toFixed(1)}
            caption="edges per node"
          />
          <Card
            id="node-types"
            label="Node types"
            value={nodeTypes.distinct.toLocaleString()}
            caption={nodeTypes.top ? `top: ${nodeTypes.top}` : '—'}
          />
          <Card
            id="edge-types"
            label="Edge types"
            value={edgeTypes.distinct.toLocaleString()}
            caption={edgeTypes.top ? `top: ${edgeTypes.top}` : '—'}
          />
          <Card
            id="content"
            label="With content"
            value={withContent.count.toLocaleString()}
            caption={`${withContent.percent}% of in view`}
          />
          <Card
            id="no-props"
            label="No properties"
            value={noProperties.toLocaleString()}
            caption="nodes"
          />
        </div>
      </CollapsibleSection>
    </div>
  )
}
