import { useState } from 'react'
import { MetricCards } from './MetricCards'
import { PhaseKanban } from './PhaseKanban'
import type { MetricFilter } from './kanban'
import type { State } from '../api'

export function Dashboard({ state }: { state: State }) {
  const [filter, setFilter] = useState<MetricFilter | null>(null)
  const toggle = (f: MetricFilter) => setFilter((cur) => (cur === f ? null : f))
  return (
    <div className="page dashboard">
      <MetricCards state={state} active={filter} onFilter={toggle} />
      <PhaseKanban state={state} filter={filter} />
    </div>
  )
}
