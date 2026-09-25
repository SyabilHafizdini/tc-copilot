export type Field =
  | { key: string; kind: 'link'; ref: string; label: string }
  | { key: string; kind: 'links'; refs: string[] }
  | { key: string; kind: 'itemized'; items: { id: string; text: string | null; status: string | null }[] }
  | { key: string; kind: 'group'; fields: Field[] }
  | { key: string; kind: 'value'; value: unknown }

export type TreeGroup = {
  kind: string; label: string; count: number
  items: { ref: string; title: string | null; status: string | null }[]
}

export type Facets = {
  kind: string; status: string | null; origin_state: 'asserted' | 'proposed'
  story: string | null; asserted_by: string | null
  stale: boolean; staleness_causes: string[]
}

export type DocView = {
  ref: string; kind: string; title: string | null; status: string | null
  version: unknown; type?: string | null; fields: Field[]; body_md: string; facets: Facets
}

export type GraphNodeRaw = { id: string; type: string; label?: string; state?: string }
export type GraphLinkRaw = { source: string; target: string; type: string }
export type GraphModel = { nodes: GraphNodeRaw[]; links: GraphLinkRaw[] }

export type ExplorerSnapshot = {
  tree: TreeGroup[]
  docs: Record<string, DocView>
  graph: GraphModel
}
