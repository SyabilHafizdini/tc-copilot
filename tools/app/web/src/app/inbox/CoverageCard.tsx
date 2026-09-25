import { useState } from 'react'
import type { CoverageCard as CC } from './types'
import { Button } from '../ui'

export function CoverageCard({ card, onAssert, onDiscard }: {
  card: CC; onAssert: () => void; onDiscard: (d: { note: string }) => void
}) {
  const [note, setNote] = useState('')
  return (
    <div className="coverage-card">
      <div className="cov-status">Coverage: <b>{card.coverage_status}</b></div>
      <table className="cov-grid">
        <thead><tr><th>AC</th><th>Added</th><th>Removed</th><th>Reason</th></tr></thead>
        <tbody>
          {card.map_corrections.map((m) => (
            <tr key={m.ac}>
              <td>{m.ac}</td><td>{m.added.join(', ')}</td><td>{m.removed.join(', ')}</td><td>{m.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {card.note && <p className="cov-note">{card.note}</p>}
      <textarea className="card-note" placeholder="Note (optional)…" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="card-actions">
        <Button onClick={onAssert}>Assert</Button>
        <Button onClick={() => onDiscard({ note })}>Discard</Button>
      </div>
    </div>
  )
}
