import { Card, Pill } from '../ui'
import { hrefFor } from '../shell/routes'
import { kanbanColumns, matchesFilter } from './kanban'
import type { KanbanCard, MetricFilter, Phase } from './kanban'
import type { State } from '../api'

const COLUMNS: Array<{ phase: Phase; title: string }> = [
  { phase: 'ingested', title: '① Ingested' },
  { phase: 'alignment', title: '② In alignment' },
  { phase: 'ready', title: '③ Ready for generation' },
  { phase: 'generated', title: '④ Generated' },
]

function CardBody({ card }: { card: KanbanCard }) {
  return (
    <Card>
      <div className="kban-card-body">
        <span className="id">{card.id}</span>
        {card.title && <span className="title">{card.title}</span>}
        <span className="tags">
          {card.staleFlag && <Pill state="attn">⚠ stale</Pill>}
          {card.openQuestions > 0 && <Pill state="blocked">{card.openQuestions} open</Pill>}
        </span>
      </div>
    </Card>
  )
}

function CardView({ card }: { card: KanbanCard }) {
  if (card.scope === 'story') {
    return (
      <a className="kban-card" href={hrefFor({ kind: 'story', id: card.id })}>
        <CardBody card={card} />
      </a>
    )
  }
  return <div className="kban-card"><CardBody card={card} /></div>
}

export function PhaseKanban({ state, filter }: { state: State; filter: MetricFilter | null }) {
  const cols = kanbanColumns(state)
  return (
    <div className="kanban">
      {COLUMNS.map(({ phase, title }) => {
        const cards = cols[phase].filter((c) => matchesFilter(c, filter))
        return (
          <section key={phase} className="kban-col" role="region" aria-label={title}>
            <header className="kban-head">
              <span>{title}</span>
              <span className="count">{cards.length}</span>
            </header>
            {cards.map((c) => <CardView key={`${c.scope}:${c.id}`} card={c} />)}
          </section>
        )
      })}
    </div>
  )
}
