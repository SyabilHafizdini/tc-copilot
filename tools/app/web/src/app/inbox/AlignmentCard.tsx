import { useState } from 'react'
import type { AlignmentCard as AC } from './types'
import { QuestionControl } from './QuestionControl'
import { cardSummary, canAssert, formatAffects } from './cardSummary'
import { Button, Pill } from '../ui'

export function AlignmentCard({ card, onAssert, onRevise, onDiscard }: {
  card: AC
  onAssert: () => void
  onRevise: (d: { answers: Record<string, string>; note: string }) => void
  onDiscard: (d: { note: string }) => void
}) {
  const qs = card.zones.open_questions
  const [answers, setAnswers] = useState<Record<string, string>>(
    () => Object.fromEntries(qs.map((q) => [q.id, ''])))
  const [note, setNote] = useState('')
  const set = (id: string, v: string) => setAnswers((a) => ({ ...a, [id]: v }))

  const summary = cardSummary(card)
  const ready = canAssert(card)
  const affects = formatAffects(card.zones.what_this_affects)
  const open = qs.filter((q) => answers[q.id] === '')
  const done = qs.filter((q) => answers[q.id] !== '')
  const answered = done.length

  return (
    <div className="align-card">
      <div className={`verdict ${ready ? 'ready' : 'blocked'}`}>
        <Pill state={ready ? 'ready' : 'blocked'}>{ready ? 'Ready to assert' : 'Blocked'}</Pill>
        <span className="verdict-progress">{answered} of {qs.length} resolved</span>
      </div>

      <div className="summary-chips">
        <span className="chip"><b>{summary.acs}</b> ACs</span>
        <span className="chip"><b>{summary.rules}</b> rules</span>
        <span className="chip"><b>{summary.components}</b> components</span>
        <span className={`chip${summary.contradictions ? ' attn' : ''}`}><b>{summary.contradictions}</b> contradictions</span>
        <span className="chip"><b>{summary.openQuestions}</b> open questions</span>
      </div>

      <details className="zone">
        <summary>What you said ({card.zones.what_you_said.length})</summary>
        <ul>{card.zones.what_you_said.map((s, i) => <li key={i}>{s}</li>)}</ul>
      </details>
      <details className="zone tripwire" open>
        <summary>What I understood <span className="tripwire-tag">tripwire — if this is wrong, the edits are wrong</span></summary>
        <p>{card.zones.what_i_understood}</p>
      </details>
      <details className="zone">
        <summary>What I changed ({card.zones.what_i_changed.length})</summary>
        <ul>{card.zones.what_i_changed.map((s, i) => <li key={i}>{s}</li>)}</ul>
      </details>
      <details className="zone">
        <summary>What this affects ({affects.length})</summary>
        <ul>{affects.map((s, i) => <li key={i}>{s}</li>)}</ul>
      </details>

      <section className="questions"><h4>Open questions</h4>
        {open.map((q) => <QuestionControl key={q.id} question={q} value={answers[q.id]} onChange={(v) => set(q.id, v)} />)}
        {open.length === 0 && qs.length > 0 && <p className="all-answered">All questions answered.</p>}
        {done.length > 0 && (
          <details className="answered-questions">
            <summary>{done.length} answered</summary>
            {done.map((q) => <QuestionControl key={q.id} question={q} value={answers[q.id]} onChange={(v) => set(q.id, v)} />)}
          </details>
        )}
      </section>

      <div className="card-actionbar">
        <textarea className="card-note" placeholder="Overall note (optional)…" value={note} onChange={(e) => setNote(e.target.value)} />
        <div className="card-actions">
          <Button onClick={() => onDiscard({ note })}>Discard</Button>
          <Button onClick={() => onRevise({ answers, note })}>Revise</Button>
          <button className="btn primary" disabled={!ready}
            title={ready ? undefined : 'Resolve every open question first — the server refuses assert while questions are open.'}
            onClick={() => { if (ready) onAssert() }}>Assert</button>
        </div>
      </div>
    </div>
  )
}
