import { matchesPrds } from './prdFilter'
import type { ConfidenceLevel, TcLevel, TcRow } from './types'

export type TcFilters = {
  level: TcLevel | null
  group: string | null        // TcGroup.key: a run, a flow or a module
  story: string | null
  status: string | null
  confidence: ConfidenceLevel[]   // empty = every level
  prds: string[]                  // selected PRD ids; empty = no PRD filter
}

export const EMPTY_FILTERS: TcFilters = {
  level: null, group: null, story: null, status: null, confidence: [], prds: [],
}

const LEVELS: TcLevel[] = ['sit', 'uat']
const CONFIDENCE: ConfidenceLevel[] = ['High', 'Medium', 'Low']

// Unknown or malformed values are dropped, never thrown on: the query comes
// from a URL anyone can type.
export function parseFilters(query: string): TcFilters {
  const q = new URLSearchParams(query)
  const level = q.get('level')
  const conf = (q.get('confidence') ?? '').split(',')
  return {
    level: LEVELS.includes(level as TcLevel) ? (level as TcLevel) : null,
    group: q.get('group') || null,
    story: q.get('story') || null,
    status: q.get('status') || null,
    confidence: CONFIDENCE.filter((c) => conf.includes(c)),
    // Ids are not checked here (the rows are not known); the grid ignores
    // any id no row draws on.
    prds: [...new Set((q.get('prd') ?? '').split(',').filter(Boolean))],
  }
}

export function serializeFilters(f: TcFilters): string {
  const q = new URLSearchParams()
  if (f.level) q.set('level', f.level)
  if (f.group) q.set('group', f.group)
  if (f.story) q.set('story', f.story)
  if (f.status) q.set('status', f.status)
  if (f.confidence.length) q.set('confidence', CONFIDENCE.filter((c) => f.confidence.includes(c)).join(','))
  if (f.prds.length) q.set('prd', [...f.prds].sort().join(','))
  return q.toString()
}

export function applyFilters(rows: TcRow[], f: TcFilters): TcRow[] {
  return rows.filter((r) =>
    (!f.level || r.level === f.level)
    && (!f.group || r.group === f.group)
    && (!f.story || r.story === f.story)
    && (!f.status || r.status === f.status)
    && (!f.confidence.length || f.confidence.includes(r.confidence as ConfidenceLevel))
    && matchesPrds(r, f.prds))
}

// The part of location.hash after '?' ("#/testcases?level=sit" -> "level=sit").
export function readHashQuery(): string {
  const i = window.location.hash.indexOf('?')
  return i < 0 ? '' : window.location.hash.slice(i + 1)
}

// Rewrites only the query of the hash, in place: no history entry and no
// hashchange event, so typing through filters does not fill the back stack.
export function writeHashQuery(query: string): void {
  const path = window.location.hash.split('?')[0] || '#/testcases'
  const next = query ? `${path}?${query}` : path
  if (next !== window.location.hash) window.history.replaceState(null, '', next)
}
