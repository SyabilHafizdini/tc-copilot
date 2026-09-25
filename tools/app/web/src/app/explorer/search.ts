import type { DocView } from './types'

export type FacetKey = 'kind' | 'status' | 'story' | 'origin_state' | 'asserted_by' | 'staleness_cause'
export type FacetSelection = Partial<Record<FacetKey, Set<string>>>

function facetValues(d: DocView, key: FacetKey): string[] {
  const f = d.facets
  if (key === 'staleness_cause') return f.staleness_causes
  const v = (f as Record<string, unknown>)[key]
  return v == null ? [] : [String(v)]
}

function passesFacets(d: DocView, active: FacetSelection): boolean {
  return (Object.entries(active) as [FacetKey, Set<string>][]).every(
    ([key, sel]) => !sel || sel.size === 0 || facetValues(d, key).some((v) => sel.has(v)),
  )
}

export function searchDocs(
  docs: Record<string, DocView>, query: string, active: FacetSelection,
): string[] {
  const q = query.trim().toLowerCase()
  const scored: { ref: string; score: number }[] = []
  for (const d of Object.values(docs)) {
    if (!passesFacets(d, active)) continue
    if (!q) { scored.push({ ref: d.ref, score: 0 }); continue }
    const title = (d.title ?? '').toLowerCase()
    const inTitle = title.includes(q) || d.ref.toLowerCase().includes(q)
    const inBody = d.body_md.toLowerCase().includes(q)
    if (inTitle) scored.push({ ref: d.ref, score: 2 })
    else if (inBody) scored.push({ ref: d.ref, score: 1 })
  }
  return scored.sort((a, b) => b.score - a.score || a.ref.localeCompare(b.ref)).map((s) => s.ref)
}

export function facetOptions(docs: Record<string, DocView>): Record<FacetKey, string[]> {
  const keys: FacetKey[] = ['kind', 'status', 'story', 'origin_state', 'asserted_by', 'staleness_cause']
  const out = Object.fromEntries(keys.map((k) => [k, new Set<string>()])) as Record<FacetKey, Set<string>>
  for (const d of Object.values(docs)) for (const k of keys) for (const v of facetValues(d, k)) out[k].add(v)
  return Object.fromEntries(keys.map((k) => [k, [...out[k]].sort()])) as Record<FacetKey, string[]>
}
