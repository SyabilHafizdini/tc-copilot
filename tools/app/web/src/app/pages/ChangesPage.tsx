import type { State } from '../api'
import { storyFromState } from '../story/selectors'
import { hrefFor } from '../shell/routes'
import { NOT_MIGRATED } from '../prd/PrdList'
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

  const staged = state.prds.filter((p) => p.staged !== null)

  return (
    <div className="page">
      <div className="page-head"><h1>Changes &amp; Impact</h1></div>

      <section aria-label="Staged PRD versions">
        <h3 className="itemized-title">Staged PRD versions <span className="itemized-count">{staged.length}</span></h3>
        {staged.length === 0
          ? <div className="card" style={{ marginBottom: 20 }}><p className="empty">{state.schema1 ? NOT_MIGRATED : 'No PRD has a staged version.'}</p></div>
          : staged.map((p) => {
            const report = state.change_reports.find((c) => c.prd === p.id && c.status === 'pending')
            return (
              <div className="card" key={p.id} style={{ marginBottom: 12 }}>
                <p>
                  <b>{p.title}</b> <span className="id">{p.id}</span>{' '}
                  {p.adopted === null
                    ? <Pill state="neutral">nothing adopted</Pill>
                    : <Pill state="ready">v{p.adopted} adopted</Pill>}{' '}
                  <Pill state="attn">v{p.staged} staged</Pill>
                </p>
                <p>
                  Change report: {report ? <span className="id">{report.id}</span> : <span className="muted">none pending</span>}
                </p>
                <p className="muted">Review the section diff: <code>py tools/wiki.py diff --prd {p.id}</code></p>
              </div>
            )
          })}
      </section>

      <h3 className="itemized-title">PRD change reports <span className="itemized-count">{state.change_reports.length}</span></h3>
      <div className="card" style={{ marginBottom: 20 }}>
        {state.change_reports.length === 0
          ? <p className="empty">No change reports - upload a new PRD version to stage one.</p>
          : (
            <table>
              <thead><tr><th>Report</th><th>PRD</th><th>Versions</th><th>Status</th></tr></thead>
              <tbody>
                {state.change_reports.map((c) => (
                  <tr key={c.id}>
                    <td><span className="id">{c.id}</span></td>
                    <td>{c.prd ?? '-'}</td>
                    <td>{c.from != null && c.to != null ? `v${c.from} \u2192 v${c.to}` : '-'}</td>
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
