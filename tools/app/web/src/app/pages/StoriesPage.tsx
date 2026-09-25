import type { State } from '../api'
import { storyFromState, storyPhase } from '../story/selectors'
import { hrefFor } from '../shell/routes'
import { Pill, type PillState } from '../ui'

const PHASE_LABEL = ['① Ingest', '② Alignment', '③ Ready', '④ Generated'] as const

const statusPill = (status: string): PillState =>
  status === 'aligned' ? 'ready'
    : status === 'draft' || status === 'skeleton' ? 'neutral'
      : status === 'needs-review' ? 'blocked'
        : 'attn'

/* Dense Jira-style backlog table (stitch screen 4): Key · Title · Status ·
 * Phase · ACs · TCs · Open questions. Rows link into the Story issue view. */
export function StoriesPage({ state }: { state: State }) {
  const stories = state.stories
    .map((r) => storyFromState(state, r.id))
    .filter((s): s is NonNullable<typeof s> => s !== null)
  return (
    <div className="page">
      <div className="page-head"><h1>Stories</h1></div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Key</th><th>Title</th><th>Status</th><th>Phase</th>
              <th>ACs</th><th>Test cases</th><th>Open questions</th>
            </tr>
          </thead>
          <tbody>
            {stories.map((s) => (
              <tr key={s.id}>
                <td><a className="id row-link" href={hrefFor({ kind: 'story', id: s.id })}>{s.id}</a></td>
                <td>{s.title ?? '—'}</td>
                <td><Pill state={statusPill(s.status)}>{s.status}</Pill></td>
                <td className="muted-cell">{PHASE_LABEL[storyPhase(s)]}</td>
                <td className="num-cell">{s.acs}</td>
                <td className="num-cell">
                  {s.tc.active}
                  {s.tc.stale > 0 && <> <Pill state="attn">{s.tc.stale} stale</Pill></>}
                </td>
                <td className="num-cell">
                  {s.open_questions > 0
                    ? <Pill state="blocked">{s.open_questions}</Pill>
                    : '0'}
                </td>
              </tr>
            ))}
            {stories.length === 0 && (
              <tr><td colSpan={7}><p className="empty">No stories yet — ingest a PRD to begin.</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
