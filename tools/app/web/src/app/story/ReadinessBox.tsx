import { Pill, Button, Banner, Card } from '../ui'
import { readiness, type Story } from './selectors'

export function ReadinessBox({ story, onRun, onExport }: {
  story: Story
  onRun: (name: string, params?: Record<string, unknown>) => void
  onExport: (name: string, params: Record<string, unknown>) => void
}) {
  const r = readiness(story)
  const gate = (ok: boolean, label: string) => (
    <Pill state={ok ? 'ready' : 'blocked'}>{label}</Pill>
  )
  if (r.ready && r.nextAction) {
    const a = r.nextAction
    return (
      <Card>
        <div className="readiness ready">
          <p className="verdict">Sealed &amp; ready to export{story.asserted_by ? ` — asserted by ${story.asserted_by}` : ''}</p>
          <div className="gate-rollup">
            {gate(r.gates.aligned, 'aligned')}{' '}
            {gate(r.gates.coverage, 'coverage')}{' '}
            {gate(r.gates.lint, 'lint')}{' '}
            {gate(r.gates.asserted, 'asserted')}
          </div>
          <Button variant="primary" onClick={() => onExport(a.action, a.params)}>{a.label}</Button>
        </div>
      </Card>
    )
  }
  return (
    <Card>
      <div className="readiness blocked">
        <Banner tone="blocked">{r.blocker}</Banner>
        <div className="gate-rollup">
          {gate(r.gates.aligned, 'aligned')}{' '}
          {gate(r.gates.coverage, 'coverage')}{' '}
          {gate(r.gates.lint, 'lint')}{' '}
          {gate(r.gates.asserted, 'asserted')}
        </div>
        {r.nextAction && (
          <Button variant="primary" onClick={() => onRun(r.nextAction!.action, r.nextAction!.params)}>
            {r.nextAction.label}
          </Button>
        )}
      </div>
    </Card>
  )
}
