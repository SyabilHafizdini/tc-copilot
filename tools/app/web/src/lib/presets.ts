import type { GraphPreset } from './types'

export interface ResolvedPreset {
  visibleTypes: Set<string>
  visibleEdgeTypes: Set<string>
  search: string
}

/** Turn a preset into concrete filter state. Named types absent from the graph
 * are intersected away; omitted type lists mean "show all". Presets are a filter
 * overlay only — they never change the active view. */
export function resolvePreset(
  preset: GraphPreset,
  allNodeTypes: readonly string[],
  allEdgeTypes: readonly string[],
): ResolvedPreset {
  const nodeSet = new Set(allNodeTypes)
  const edgeSet = new Set(allEdgeTypes)
  return {
    visibleTypes: preset.nodeTypes
      ? new Set(preset.nodeTypes.filter((t) => nodeSet.has(t)))
      : new Set(allNodeTypes),
    visibleEdgeTypes: preset.edgeTypes
      ? new Set(preset.edgeTypes.filter((t) => edgeSet.has(t)))
      : new Set(allEdgeTypes),
    search: preset.search ?? '',
  }
}

export function findDefaultPreset(presets: GraphPreset[]): GraphPreset | null {
  return presets.find((p) => p.default === true) ?? null
}

function sameSet(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  if (a.size !== b.size) return false
  for (const x of a) if (!b.has(x)) return false
  return true
}

/** Name of the first preset whose resolved type-sets + search equal the current
 * filter state, else null. */
export function matchActivePreset(
  presets: GraphPreset[],
  visibleTypes: ReadonlySet<string>,
  visibleEdgeTypes: ReadonlySet<string>,
  search: string,
  allNodeTypes: readonly string[],
  allEdgeTypes: readonly string[],
): string | null {
  const allNodeCount = new Set(allNodeTypes).size
  const allEdgeCount = new Set(allEdgeTypes).size
  for (const p of presets) {
    const r = resolvePreset(p, allNodeTypes, allEdgeTypes)
    // A preset that shows everything (all types, no search) is indistinguishable
    // from the cleared state — don't treat it as an active selection.
    if (
      r.visibleTypes.size === allNodeCount &&
      r.visibleEdgeTypes.size === allEdgeCount &&
      r.search === ''
    ) {
      continue
    }
    if (
      sameSet(r.visibleTypes, visibleTypes) &&
      sameSet(r.visibleEdgeTypes, visibleEdgeTypes) &&
      r.search === search
    ) {
      return p.name
    }
  }
  return null
}
