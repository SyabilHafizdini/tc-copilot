import type { State, NextRow } from '../api'

export type Phase = 'ingested' | 'alignment' | 'ready' | 'generated'

export interface KanbanCard {
  id: string
  title: string | null
  scope: 'story' | 'flow'
  status: string
  phase: Phase
  openQuestions: number
  tcActive: number
  staleFlag: boolean
}

export interface KanbanColumns {
  ingested: KanbanCard[]
  alignment: KanbanCard[]
  ready: KanbanCard[]
  generated: KanbanCard[]
}

// The runtime shape of a gather() story row. State['stories'][number] is only
// typed as `Record<string, unknown> & { id; status }`, so we narrow here through
// a single documented cast — never `any`.
interface StoryFields {
  id: string
  status: string
  title?: string | null
  acs?: number
  open_questions?: number
  tc?: { active: number; stale: number; retired: number }
  stale_causes?: string[]
}

const n = (v: number | undefined): number => (typeof v === 'number' ? v : 0)
const staleText = (row: NextRow | undefined): boolean => !!row && /stale/i.test(row.state)

function storyCard(raw: State['stories'][number], byId: Map<string, NextRow>): KanbanCard {
  const s = raw as unknown as StoryFields
  const oq = n(s.open_questions)
  const active = n(s.tc?.active)
  let phase: Phase
  if (active > 0) phase = 'generated'
  else if (s.status === 'aligned' && oq === 0) phase = 'ready'
  else if (n(s.acs) === 0 && (s.status === 'draft' || s.status === 'skeleton')) phase = 'ingested'
  else phase = 'alignment'
  const stale = n(s.tc?.stale) > 0 || (s.stale_causes?.length ?? 0) > 0 || staleText(byId.get(s.id))
  return {
    id: s.id, title: s.title ?? null, scope: 'story', status: s.status, phase,
    openQuestions: oq, tcActive: active, staleFlag: phase === 'generated' && stale,
  }
}

function flowCard(f: { id: string; status: string }, byId: Map<string, NextRow>): KanbanCard {
  const row = byId.get(f.id)
  const text = row?.state ?? ''
  const generated = /\d+\s+active\b.*\bTC/i.test(text) || /stale/i.test(text)
  let phase: Phase
  if (generated) phase = 'generated'
  else if (f.status === 'aligned' && /\b0\s+UAT\s+TCs\b/i.test(text)) phase = 'ready'
  else phase = 'alignment'
  return {
    id: f.id, title: null, scope: 'flow', status: f.status, phase,
    openQuestions: 0, tcActive: 0, staleFlag: phase === 'generated' && /stale/i.test(text),
  }
}

export function kanbanColumns(state: State): KanbanColumns {
  const byId = new Map(state.next.rows.map((r) => [r.id, r]))
  const cols: KanbanColumns = { ingested: [], alignment: [], ready: [], generated: [] }
  for (const raw of state.stories) {
    const c = storyCard(raw, byId)
    cols[c.phase].push(c)
  }
  for (const f of state.flows) {
    const c = flowCard(f, byId)
    cols[c.phase].push(c)
  }
  return cols
}

export type MetricFilter = 'open' | 'alignment' | 'ready' | 'tcs' | 'stale'

export interface Metric {
  key: MetricFilter
  label: string
  value: number
  tone: 'critical' | 'attn' | 'neutral'
}

export function allCards(cols: KanbanColumns): KanbanCard[] {
  return [...cols.ingested, ...cols.alignment, ...cols.ready, ...cols.generated]
}

export function dashboardMetrics(state: State): Metric[] {
  const cols = kanbanColumns(state)
  const cards = allCards(cols)
  const open = cards.reduce((sum, c) => sum + c.openQuestions, 0)
  const stale = cards.filter((c) => c.staleFlag).length
  const tcs = state.totals.tcs ?? 0
  const attn = (v: number): Metric['tone'] => (v > 0 ? 'attn' : 'neutral')
  const crit = (v: number): Metric['tone'] => (v > 0 ? 'critical' : 'neutral')
  return [
    { key: 'open', label: 'Open questions', value: open, tone: crit(open) },
    { key: 'alignment', label: 'In alignment', value: cols.alignment.length, tone: attn(cols.alignment.length) },
    { key: 'ready', label: 'Ready to generate', value: cols.ready.length, tone: attn(cols.ready.length) },
    { key: 'tcs', label: 'Test cases', value: tcs, tone: 'neutral' },
    { key: 'stale', label: 'Stale', value: stale, tone: crit(stale) },
  ]
}

export function matchesFilter(c: KanbanCard, f: MetricFilter | null): boolean {
  if (!f) return true
  switch (f) {
    case 'open': return c.openQuestions > 0
    case 'alignment': return c.phase === 'alignment'
    case 'ready': return c.phase === 'ready'
    case 'tcs': return c.phase === 'generated'
    case 'stale': return c.staleFlag
  }
}
