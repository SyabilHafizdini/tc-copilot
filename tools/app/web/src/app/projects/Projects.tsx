import { Plus } from 'lucide-react'
import { useProject } from '../shell/useProject'
import { hrefFor, type View } from '../shell/routes'
import { Skeleton } from '../ui'
import { ProjectTile } from './ProjectTile'

export function Projects() {
  const { all, switch: switchTo, loading } = useProject()
  const go = (v: View) => { window.location.hash = hrefFor(v) }
  return (
    <div className="page">
      <div className="page-head">
        <h1>Projects</h1>
        <button className="create"><Plus size={14} /> New project</button>
      </div>
      {loading ? (
        <div className="proj-grid"><div className="proj-card skeleton-tile"><Skeleton lines={3} header /></div></div>
      ) : all.length === 0 ? (
        <p className="section-label">No projects yet.</p>
      ) : (
        <div className="proj-grid">
          {all.map((c) => (
            <ProjectTile key={c.id} card={c} onOpen={switchTo} onNext={go} />
          ))}
        </div>
      )}
    </div>
  )
}
