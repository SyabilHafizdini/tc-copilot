import { Pill, Skeleton } from '../ui'
import { FrontmatterFields } from '../explorer/FrontmatterFields'
import type { Field } from '../explorer/types'
import { allowedTransitions, type Story } from './selectors'

export function PropertiesRail({ story, fields, onRun, onNavigate, loading = false }: {
  story: Story
  fields: Field[]
  onRun: (name: string, params?: Record<string, unknown>) => void
  onNavigate: (nodeId: string) => void
  loading?: boolean
}) {
  const transitions = allowedTransitions(story)
  const onPick = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const t = transitions[Number(e.target.value)]
    if (t) onRun(t.action, t.params)
    e.target.selectedIndex = 0 // reset so the same transition can be re-fired
  }
  const c = story.components
  return (
    <aside className="props-rail">
      <div className="prop">
        <label htmlFor="story-status">Status</label>
        <div className="status-line">
          <Pill state={story.status === 'aligned' ? 'ready' : 'draft'}>{story.status}</Pill>
        </div>
        <select id="story-status" aria-label="Status" defaultValue="" onChange={onPick}>
          <option value="" disabled>Change status…</option>
          {transitions.map((t, i) => (
            <option key={t.label} value={i}>{t.gated ? `${t.label} (gated)` : t.label}</option>
          ))}
        </select>
      </div>

      <div className="prop">
        <span className="section-label">Coverage</span>
        <p className="state">{c.covered}/{c.total} covered · {c.out_of_scope} out-of-scope · {c.gaps} gap(s)</p>
      </div>

      <div className="prop">
        <span className="section-label">Metadata</span>
        {loading
          ? <Skeleton lines={5} />
          : <FrontmatterFields fields={fields} onNavigate={onNavigate} onFocusItem={() => {}} />}
      </div>
    </aside>
  )
}
