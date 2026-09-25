export function ClipboardHandoff({ reason }: { reason: string }) {
  const sample = 'opencode   # then: align US-XXXX against its PRD section'
  return (
    <div className="handoff">
      <p className="handoff-why">Chat unavailable — {reason}</p>
      <p>Run the agent in your own terminal:</p>
      <pre onClick={(e) => navigator.clipboard?.writeText(e.currentTarget.textContent ?? '')}>{sample}</pre>
      <p className="handoff-hint">Click to copy. The app stays fully usable for reading and decisions.</p>
    </div>
  )
}
