import { Sun, Moon, Search, Plus, Bell } from 'lucide-react'
import type { ProjectCard } from '../api'

export function TopBar({
  project, projects, onSwitchProject, onSearch, onCreate, theme, onToggleTheme,
}: {
  project: string | null
  projects: ProjectCard[]
  onSwitchProject: (id: string) => void
  onSearch: () => void
  onCreate: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}) {
  return (
    <div className="topbar">
      <div className="brand-mark"><b>tc</b><span>tc-copilot</span></div>
      <label className="proj-switch">
        <span className="vh">Project</span>
        <select value={project ?? ''} onChange={(e) => onSwitchProject(e.target.value)}>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.product}</option>)}
        </select>
      </label>
      <div className="search-slot">
        <button className="search" onClick={onSearch}>
          <Search size={14} /> Search <kbd>Ctrl K</kbd>
        </button>
      </div>
      <button className="create" onClick={onCreate}><Plus size={14} /> Create</button>
      <button className="icon-btn" aria-label="Notifications"><Bell size={16} /></button>
      <button
        className="icon-btn" onClick={onToggleTheme}
        aria-label="Toggle theme" title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      >
        {theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
      </button>
      <button className="icon-btn" aria-label="Profile"><span className="av-mini">SY</span></button>
    </div>
  )
}
