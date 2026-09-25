import type { State } from '../api'
import { storyFromState } from '../story/selectors'
import { hrefFor } from '../shell/routes'
import { Pill, type PillState } from '../ui'

const reportPill = (status: string): PillState =>
  status === 'approved' ? 'ready'
    : status === 'rejected' ? 'blocked'
      : 'attn'

/* Changes & Impact (stitch screen 11): PRD change reports on the left of the
 * story, and the computed downstream impact — stories whose test cases went
 * stale and why — below. Impact is read straight from the staleness cascade
 * (stale_causes / tc.stale), the same verdicts `wiki impact` prints. */
export function ChangesPage({ state }: { state: State }) {
  const impacted = state.stories
    .map((r) => storyFromState(state, r.id))
    .filter((s): s is NonNullable<typeof s> => s !== null)
    .filter((s) => s.stale_causes.length > 0 || s.tc.stale > 0 || s.status === 'needs-review')

  return (
    <div className="page">
      <div className="page-head"><h1>Changes &amp; Impact</h1></div>

      <h3 className="itemized-title">PRD change reports <span className="itemized-count">{state.change_reports.length}</span></h3>
      <div className="card" style={{ marginBottom: 20 }}>
        {state.change_reports.length === 0
          ? <p className="empty">No change reports — upload a new PRD version to stage one.</p>
          : (
            <table>
              <thead><tr><th>Report</th><th>Status</th></tr></thead>
              <tbody>
                {state.change_reports.map((c) => (
                  <tr key={c.id}>
                    <td><span className="id">{c.id}</span></td>
                    <td><Pill state={reportPill(c.status)}>{c.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      <h3 className="itemized-title">Downstream impact <span className="itemized-count">{impacted.length}</span></h3>
      <div className="card">
        {impacted.length === 0
          ? <p className="empty">Nothing stale — every asserted story's test cases are current.</p>
          : (
            <table>
              <thead><tr><th>Story</th><th>Verdict</th><th>Stale TCs</th><th>Causes</th></tr></thead>
              <tbody>
                {impacted.map((s) => (
                  <tr key={s.id} className="gap-row">
                    <td><a className="id row-link" href={hrefFor({ kind: 'story', id: s.id })}>{s.id}</a></td>
                    <td>
                      <Pill state={s.status === 'needs-review' ? 'blocked' : 'attn'}>
                        {s.status === 'needs-review' ? 'needs-review' : 'stale'}
                      </Pill>
                    </td>
                    <td className="num-cell">{s.tc.stale}</td>
                    <td className="muted-cell">{s.stale_causes.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  )
}
