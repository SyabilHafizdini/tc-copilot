import type { StoryPhase } from './selectors'

const LABELS = ['Ingest', 'Alignment', 'Ready', 'Generated'] as const

export function PhaseStepper({ phase, onSelect }: { phase: StoryPhase; onSelect: (p: StoryPhase) => void }) {
  return (
    <div className="phase-stepper" role="group" aria-label="Phase">
      {LABELS.map((label, i) => {
        const cls = i < phase ? 'step done' : i === phase ? 'step current' : 'step'
        return (
          <button key={label} className={cls} onClick={() => onSelect(i as StoryPhase)}>
            <span className="step-n" aria-hidden="true">{i + 1}</span> {label}
          </button>
        )
      })}
    </div>
  )
}
