import { useState } from 'react'
import type { OpenQuestion } from './types'

type Mode = 'accept' | 'correct' | 'descope' | 'none'

const modeOf = (value: string): Mode =>
  value === 'accept' ? 'accept' : value === 'descope' ? 'descope' : value === '' ? 'none' : 'correct'

export function QuestionControl({ question, value, onChange }: {
  question: OpenQuestion; value: string; onChange: (next: string) => void
}) {
  const [mode, setMode] = useState<Mode>(modeOf(value))
  const isText = value !== 'accept' && value !== 'descope' && value !== ''
  return (
    <div className="q-control">
      <div className="q-about">{question.id} · {question.about}</div>
      <div className="q-text">{question.question}</div>
      <div className="q-proposed"><b>Proposed:</b> {question.proposed}</div>
      <div className="q-toggle">
        <button className={mode === 'accept' ? 'active' : ''}
          onClick={() => { setMode('accept'); onChange('accept') }}>Accept</button>
        <button className={mode === 'correct' ? 'active' : ''}
          onClick={() => { setMode('correct'); onChange(isText ? value : '') }}>Correct</button>
        <button className={mode === 'descope' ? 'active' : ''}
          onClick={() => { setMode('descope'); onChange('descope') }}>De-scope</button>
      </div>
      {mode === 'correct' && (
        <textarea value={isText ? value : ''} placeholder="Your correction…"
          onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  )
}
