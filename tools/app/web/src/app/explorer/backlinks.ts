import type { DocView, GraphModel } from './types'

export type BacklinkEntry = { ref: string; title: string | null; status: string | null }
export type BacklinkGroup = { relation: string; entries: BacklinkEntry[] }

// Edge-kind -> human relation, by direction. `out` = current node is the edge
// source; `in` = current node is the target. Display-only: the EDGES are
// authoritative from build_model; this map never invents an edge.
const LABELS: Record<string, { out: string; in: string }> = {
  covers: { out: 'covers', in: 'covered by' },
  maps_to: { out: 'maps to', in: 'mapped from' },
  settles: { out: 'settles', in: 'settled by' },
  derived_from: { out: 'derived from', in: 'source of' },
  has_ac: { out: 'contains', in: 'part of' },
  has_br: { out: 'contains', in: 'part of' },
  exercises: { out: 'exercises', in: 'exercised by' },
  verifies_rules: { out: 'verifies', in: 'verified by' },
  uses_terms: { out: 'uses', in: 'used by' },
}

const fileRefOf = (nodeId: string) => nodeId.split('#')[0]

function entry(nodeId: string, docs: Record<string, DocView>): BacklinkEntry {
  const d = docs[fileRefOf(nodeId)]
  return { ref: nodeId, title: d?.title ?? null, status: d?.status ?? null }
}

export function deriveBacklinks(
  graph: GraphModel, nodeId: string, docs: Record<string, DocView>,
): BacklinkGroup[] {
  const byRelation = new Map<string, BacklinkEntry[]>()
  const push = (rel: string, other: string) => {
    if (!byRelation.has(rel)) byRelation.set(rel, [])
    byRelation.get(rel)!.push(entry(other, docs))
  }
  for (const l of graph.links) {
    const label = LABELS[l.type] ?? { out: l.type, in: l.type }
    if (l.source === nodeId) push(label.out, l.target)
    else if (l.target === nodeId) push(label.in, l.source)
  }
  return [...byRelation.entries()].map(([relation, entries]) => ({ relation, entries }))
}
