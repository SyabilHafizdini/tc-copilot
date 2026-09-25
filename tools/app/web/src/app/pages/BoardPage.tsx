import { useState } from 'react'
import type { State } from '../api'
import { MetricCards } from '../dashboard/MetricCards'
import { PhaseKanban } from '../dashboard/PhaseKanban'
import type { MetricFilter } from '../dashboard/kanban'

/* Full-page computed phase board (stitch screen 3): the same read-only
 * four-column Kanban as the Dashboard, page-sized, with the metric row acting
 * as its filter bar. Columns are computed from state — never drag-and-drop. */
export function BoardPage({ state }: { state: State }) {
  const [filter, setFilter] = useState<MetricFilter | null>(null)
  return (
    <div className="page dashboard">
      <div className="page-head"><h1>Board</h1></div>
      <MetricCards state={state} active={filter} onFilter={(f) => setFilter(f === filter ? null : f)} />
      <PhaseKanban state={state} filter={filter} />
    </div>
  )
}
