import type { State } from '../api'

export type Story = {
  id: string
  title: string | null
  status: string
  module: string | null
  acs: number
  open_questions: number
  asserted_by: string | null
  tc: { active: number; stale: number; retired: number }
  stale_causes: string[]
  components: { total: number; covered: number; acs_without_tcs: number; out_of_scope: number; gaps: number }
}

export type Gates = { aligned: boolean; coverage: boolean; lint: boolean; asserted: boolean }
export type TransitionAction = { label: string; action: string; params: Record<string, unknown> }
export type Transition = { label: string; action: string; params: Record<string, unknown>; gated: boolean }
export type Readiness = { ready: boolean; gates: Gates; blocker?: string; nextAction?: TransitionAction }

// Narrow a loosely-typed dashboard row (Record<string, unknown>) into Story.
// The fields all exist on the read-model row; we coerce with safe defaults.
export function storyFromState(state: State, id: string): Story | null {
  const row = state.stories.find((r) => r.id === id)
  if (!row) return null
  const r = row as Record<string, unknown>
  const tc = (r.tc ?? {}) as Record<string, unknown>
  const c = (r.components ?? {}) as Record<string, unknown>
  const num = (v: unknown): number => (typeof v === 'number' ? v : 0)
  return {
    id: String(r.id),
    title: (r.title as string) ?? null,
    status: String(r.status ?? '?'),
    module: (r.module as string) ?? null,
    acs: num(r.acs),
    open_questions: num(r.open_questions),
    asserted_by: (r.asserted_by as string) ?? null,
    tc: { active: num(tc.active), stale: num(tc.stale), retired: num(tc.retired) },
    stale_causes: Array.isArray(r.stale_causes) ? (r.stale_causes as string[]) : [],
    components: {
      total: num(c.total), covered: num(c.covered), acs_without_tcs: num(c.acs_without_tcs),
      out_of_scope: num(c.out_of_scope), gaps: num(c.gaps),
    },
  }
}

// Merge-box rollup. Gate order mirrors wiki_next.story_next: aligned →
// coverage → lint → asserted; the first unmet gate is the single blocker.
export function readiness(s: Story): Readiness {
  const gates: Gates = {
    aligned: s.status === 'aligned' && s.open_questions === 0,
    coverage: s.components.gaps === 0 && s.components.acs_without_tcs === 0 && s.components.covered > 0,
    lint: s.tc.stale === 0,
    asserted: !!s.asserted_by,
  }
  const ready = gates.aligned && gates.coverage && gates.lint && gates.asserted && s.tc.active > 0
  if (ready) {
    return { ready, gates, nextAction: { label: 'Export ↓', action: 'export', params: { story: s.id, name: `${s.id}-sit` } } }
  }
  let blocker: string
  if (!gates.aligned) {
    blocker = s.status !== 'aligned'
      ? `Not aligned — status '${s.status}'`
      : `Aligned but ${s.open_questions} open question(s) remain`
  } else if (!gates.coverage) {
    blocker = s.components.gaps > 0
      ? `Coverage incomplete — ${s.components.gaps} component gap(s)`
      : `${s.components.acs_without_tcs} component(s) not yet covered by an active test case — generate`
  } else if (!gates.lint) {
    blocker = `${s.tc.stale} stale test case(s) — regenerate`
  } else if (!gates.asserted) {
    blocker = 'Not asserted by a human yet'
  } else {
    blocker = 'No active test cases yet — generate first'
  }
  return { ready, gates, blocker, nextAction: { label: 'Run gate check', action: 'gate', params: { story: s.id } } }
}

// Allowed transitions for a story. Status-advancing transitions are gated: true.
// Two universal read-only checks (gate, lint) are always appended, gated: false.
export function allowedTransitions(s: Story): Transition[] {
  const t: Transition[] = []
  const gate = (label: string): Transition => ({ label, action: 'gate', params: { story: s.id }, gated: true })
  switch (s.status) {
    case 'draft':
    case 'in-alignment':
      t.push(gate('Assert alignment'))
      break
    case 'needs-review':
      t.push(gate('Re-align'))
      break
    case 'aligned': {
      const covered = s.components.gaps === 0 && s.components.acs_without_tcs === 0 && s.components.covered > 0
      if (s.open_questions > 0) t.push(gate('Assert alignment'))
      else if (!covered) t.push(gate('Confirm coverage'))
      else if (s.tc.stale > 0) t.push(gate('Regenerate stale test cases'))
      // fully ready: no status-advancing transition — export lives in the readiness box
      break
    }
  }
  // Universal read-only checks — never gated, always available.
  t.push({ label: 'Run gate check', action: 'gate', params: { story: s.id }, gated: false })
  t.push({ label: 'Run lint', action: 'lint', params: {}, gated: false })
  return t
}

// Story phase for the PhaseStepper dashboard component.
// 0: Ingest (draft) · 1: Alignment (in-alignment/needs-review or aligned-with-open-questions)
// 2: Ready (aligned, 0 open questions, no active TCs) · 3: Generated (aligned with active TCs)
export type StoryPhase = 0 | 1 | 2 | 3

export function storyPhase(s: Story): StoryPhase {
  if (s.status === 'draft') return 0
  if (s.status !== 'aligned' || s.open_questions > 0) return 1
  if (s.tc.active > 0) return 3
  return 2
}
