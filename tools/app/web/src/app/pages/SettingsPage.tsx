import type { State, ProjectCard } from '../api'

/* Settings (stitch screen 15): the same labeled-field layout as the metadata
 * panels. Everything here is read from live state; theme is the one control. */
export function SettingsPage({ state, projects, theme, onToggleTheme }: {
  state: State; projects: ProjectCard[]; theme: 'light' | 'dark'; onToggleTheme: () => void
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
        </dl>
      </div>

      <div className="pane" style={{ maxWidth: 640 }}>
        <h4>Project</h4>
        <dl className="fm-fields">
          <div className="fm-field"><dt>project</dt><dd>{state.project}</dd></div>
          {project && <div className="fm-field"><dt>product</dt><dd>{project.product}</dd></div>}
          {project && <div className="fm-field"><dt>branch</dt><dd><span className="id">{project.branch}</span></dd></div>}
          <div className="fm-field"><dt>prd adopted</dt><dd>{state.prd.adopted ?? '—'}</dd></div>
          <div className="fm-field"><dt>prd staged</dt><dd>{state.prd.staged ?? '—'}</dd></div>
          <div className="fm-field"><dt>stories</dt><dd>{state.stories.length}</dd></div>
          <div className="fm-field"><dt>test cases</dt><dd>{state.totals.tcs ?? 0}</dd></div>
          <div className="fm-field"><dt>suites</dt><dd>{state.suites.join(', ') || '—'}</dd></div>
        </dl>
      </div>
    </div>
  )
}
