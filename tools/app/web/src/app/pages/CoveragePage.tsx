import type { State } from '../api'
import { storyFromState } from '../story/selectors'
import { hrefFor } from '../shell/routes'
import { Pill, StatTile } from '../ui'

/* Coverage rollup (stitch screen 9): aggregate stat tiles over every story's
 * component coverage, then a per-story table with gap rows highlighted. */
export function CoveragePage({ state }: { state: State }) {
  const stories = state.stories
    .map((r) => storyFromState(state, r.id))
    .filter((s): s is NonNullable<typeof s> => s !== null)

  const sum = (f: (s: (typeof stories)[number]) => number) => stories.reduce((t, s) => t + f(s), 0)
  const total = sum((s) => s.components.total)
  const covered = sum((s) => s.components.covered)
  const gaps = sum((s) => s.components.gaps)
  const uncovered = sum((s) => s.components.acs_without_tcs)

  return (
    <div className="page">
      <div className="page-head"><h1>Coverage</h1></div>
      <div className="strip">
        <StatTile n={`${covered}/${total}`} label="Components covered" />
        <StatTile n={sum((s) => s.components.out_of_scope)} label="Out of scope" />
        <StatTile n={gaps} label="Gaps" sub={gaps > 0 ? 'needs disposition' : undefined} />
        <StatTile n={uncovered} label="Without active TCs" sub={uncovered > 0 ? 'generate to cover' : undefined} />
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Story</th><th>Covered</th><th>Out of scope</th>
              <th>Gaps</th><th>Without active TCs</th><th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {stories.map((s) => {
              const bad = s.components.gaps > 0 || s.components.acs_without_tcs > 0
              const none = s.components.total === 0
              return (
                <tr key={s.id} className={bad ? 'gap-row' : ''}>
                  <td><a className="id row-link" href={hrefFor({ kind: 'story', id: s.id })}>{s.id}</a></td>
                  <td className="num-cell">{none ? '—' : `${s.components.covered}/${s.components.total}`}</td>
                  <td className="num-cell">{none ? '—' : s.components.out_of_scope}</td>
                  <td className="num-cell">
                    {s.components.gaps > 0 ? <Pill state="blocked">{s.components.gaps}</Pill> : none ? '—' : '0'}
                  </td>
                  <td className="num-cell">
                    {s.components.acs_without_tcs > 0
                      ? <Pill state="attn">{s.components.acs_without_tcs}</Pill> : none ? '—' : '0'}
                  </td>
                  <td>
                    {none
                      ? <Pill state="neutral">no coverage map</Pill>
                      : bad ? <Pill state="blocked">incomplete</Pill> : <Pill state="ready">covered</Pill>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
