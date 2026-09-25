import { useState } from 'react'
import { Pill, Card } from '../ui'
import type { TcRow, TcLevel } from './testcases'

const LEVELS: Array<{ key: TcLevel | 'all'; label: string }> = [
  { key: 'all', label: 'All' }, { key: 'sit', label: 'SIT' }, { key: 'uat', label: 'UAT' }, { key: 'osat', label: 'OSAT' },
]

export function TestCasesTab({ rows }: { rows: TcRow[] }) {
  const [level, setLevel] = useState<TcLevel | 'all'>('all')
  const shown = level === 'all' ? rows : rows.filter((r) => r.level === level)
  return (
    <div className="tc-tab">
      <div className="level-filter">
        {LEVELS.map((l) => (
          <button key={l.key} className={`chip ${level === l.key ? 'on' : ''}`} onClick={() => setLevel(l.key)}>
            {l.label}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="section-label">No test cases at this level.</p>
      ) : shown.map((tc) => (
        <Card key={tc.id}>
          <div className="tc-head">
            <span className="id">{tc.id}</span>{' '}
            <Pill state="neutral">{tc.level.toUpperCase()}</Pill>{' '}
            {tc.ac && <span className="skill">{tc.ac}</span>}
            {tc.title && <span className="state"> {tc.title}</span>}
          </div>
          <table>
            <thead><tr><th>#</th><th>Action</th><th>Test data</th><th>Expected result</th></tr></thead>
            <tbody>
              {tc.steps.map((s) => (
                <tr key={s.n}><td>{s.n}</td><td>{s.action}</td><td>{s.data}</td><td>{s.expected}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  )
}
