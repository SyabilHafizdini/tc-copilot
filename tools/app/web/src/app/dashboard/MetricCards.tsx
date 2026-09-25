import { StatTile } from '../ui'
import { dashboardMetrics } from './kanban'
import type { MetricFilter } from './kanban'
import type { State } from '../api'

export function MetricCards({
  state, active, onFilter,
}: {
  state: State
  active: MetricFilter | null
  onFilter: (f: MetricFilter) => void
}) {
  return (
    <div className="metric-row">
      {dashboardMetrics(state).map((m) => (
        <button
          key={m.key}
          type="button"
          className={`metric ${m.tone}${active === m.key ? ' active' : ''}`}
          aria-pressed={active === m.key}
          onClick={() => onFilter(m.key)}
        >
          <StatTile n={m.value} label={m.label} />
        </button>
      ))}
    </div>
  )
}
