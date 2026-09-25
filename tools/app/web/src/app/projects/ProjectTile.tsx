import type { ProjectCard } from '../api'
import type { View } from '../shell/routes'

const PHASES = ['Ingested', 'In alignment', 'Ready', 'Generated']

export function ProjectTile({ card, onOpen, onNext }: {
  card: ProjectCard
  onOpen: (id: string) => void
  onNext: (v: View) => void
}) {
  const next = card.next
  return (
    <div className="proj-card">
      <button className="proj-open" onClick={() => onOpen(card.id)}>
        <div className="proj-head">
          <b>{card.product}</b>
          <span className="proj-branch">{card.branch}</span>
        </div>
        <ol className="phase-mini" aria-label="phase tracker">
          {PHASES.map((label, i) => (
            <li key={label} className={i < card.phase ? 'done' : i === card.phase ? 'current' : ''}>
              <span className="vh">{label}</span>
            </li>
          ))}
        </ol>
        <div className="proj-counts">
          <span>{card.counts.stories} stories</span>
          <span>{card.counts.tcs} test cases</span>
        </div>
      </button>
      {next && (
        <button className="proj-next" onClick={() => onNext(next.view)}>▶ {next.label}</button>
      )}
    </div>
  )
}
