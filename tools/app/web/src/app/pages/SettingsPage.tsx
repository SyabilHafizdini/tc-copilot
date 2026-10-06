import type { State, ProjectCard } from '../api'
import { PrdList } from '../prd/PrdList'

/* Settings (stitch screen 15): the same labeled-field layout as the metadata
 * panels. Everything here is read from live state; theme and chat are the two
 * controls, both per-browser view preferences owned by App. */
export function SettingsPage({ state, projects, theme, onToggleTheme, chatEnabled = false, onSetChatEnabled }: {
  state: State; projects: ProjectCard[]; theme: 'light' | 'dark'; onToggleTheme: () => void
  chatEnabled?: boolean; onSetChatEnabled?: (enabled: boolean) => void
}) {
  const project = projects[0] ?? null
  return (
    <div className="page">
      <div className="page-head"><h1>Settings</h1></div>

      <div className="pane" style={{ maxWidth: 640, marginBottom: 16 }}>
        <h4>Appearance</h4>
        <dl className="fm-fields">
          <div className="fm-field">
            <dt>theme</dt>
            <dd>
              <div className="explore-mode">
                <button className={theme === 'light' ? 'active' : ''} onClick={() => theme !== 'light' && onToggleTheme()}>Light</button>
                <button className={theme === 'dark' ? 'active' : ''} onClick={() => theme !== 'dark' && onToggleTheme()}>Slate</button>
              </div>
            </dd>
          </div>
          <div className="fm-field">
            <dt>chat</dt>
            <dd>
              <div className="explore-mode">
                <button className={chatEnabled ? '' : 'active'} onClick={() => chatEnabled && onSetChatEnabled?.(false)}>Off</button>
                <button className={chatEnabled ? 'active' : ''} onClick={() => !chatEnabled && onSetChatEnabled?.(true)}>On</button>
              </div>
            </dd>
          </div>
        </dl>
      </div>

      <div className="pane" style={{ maxWidth: 640 }}>
        <h4>Project</h4>
        <dl className="fm-fields">
          <div className="fm-field"><dt>project</dt><dd>{state.project}</dd></div>
          {project && <div className="fm-field"><dt>product</dt><dd>{project.product}</dd></div>}
          {project && <div className="fm-field"><dt>branch</dt><dd><span className="id">{project.branch}</span></dd></div>}
          <div className="fm-field"><dt>stories</dt><dd>{state.stories.length}</dd></div>
          <div className="fm-field"><dt>test cases</dt><dd>{state.totals.tcs ?? 0}</dd></div>
          <div className="fm-field"><dt>suites</dt><dd>{state.suites.join(', ') || '—'}</dd></div>
        </dl>
      </div>

      <div className="pane" style={{ maxWidth: 640, marginTop: 16 }}>
        <h4>PRDs</h4>
        <PrdList prds={state.prds} schema1={state.schema1} />
      </div>
    </div>
  )
}
