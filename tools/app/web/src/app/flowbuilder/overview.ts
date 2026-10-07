/* Pure merge of every flow's journey into one graph, for the flow overview.
 *
 * Two journey entries are the same step when they walk the same criterion to
 * the same end state; flows that share a step share its node, and a flow that
 * leaves the others gets its own node at that point. With `split`, entries
 * that carry different data notes are kept apart too, so each data
 * permutation is its own lane. */
import type { BuilderModel } from '../api'

export type OvVariant = { note: string; flows: string[] }
// one flow's walk of a step: its journey entry, and the data note as written
export type OvEntry = { flow: string; jid: string; note: string }
export type OvNode = {
  id: string
  ref: string           // "<story id>#<criterion id>"
  endState: string
  flows: string[]       // ids of the flows that walk this step, in model order
  variants: OvVariant[] // the distinct data notes among those flows
  entries: OvEntry[]    // every journey entry merged into this step
  col: number
  row: number
  x: number
  y: number
}
export type OvEdge = { id: string; from: string; to: string; flows: string[] }
export type OvFlow = { id: string; label: string; title: string; status: string; steps: number }
export type Overview = { nodes: OvNode[]; edges: OvEdge[]; flows: OvFlow[]; shared: number }

export const COL_W = 330
export const ROW_H = 230

// "FLOW-DEMO-SC04" -> "SC04": how a flow is named on a chip
export const shortLabel = (id: string) => id.split('-').pop() || id

/* A note often names its own flow ("Scenario 4 shows ..."). That number is
 * not a data difference, so it is blanked before notes are compared. */
export function normNote(note: string | null, flowId: string): string {
  const text = (note ?? '').trim()
  const n = flowId.match(/(\d+)$/)
  if (!text || !n) return text
  return text.replace(new RegExp(`\\b0*${Number(n[1])}\\b`, 'g'), '#')
}

export function mergeFlows(model: Pick<BuilderModel, 'flows'>, split: boolean): Overview {
  const byKey = new Map<string, OvNode>()
  const baseOf = new Map<OvNode, string>()   // criterion + end state, whatever the data
  const edgeMap = new Map<string, OvEdge>()
  const flows: OvFlow[] = []

  model.flows.forEach((f) => {
    const entries = f.journey.filter((j) => j.ac_ref)
    flows.push({ id: f.id, label: shortLabel(f.id), title: f.title ?? '', status: f.status, steps: entries.length })
    let prev: OvNode | null = null
    entries.forEach((j) => {
      const note = normNote(j.note, f.id)
      const key = `${j.ac_ref}|${(j.end_state ?? '').trim()}${split ? `|${note}` : ''}`
      let node = byKey.get(key)
      if (!node) {
        node = { id: `s${byKey.size + 1}`, ref: j.ac_ref!, endState: (j.end_state ?? '').trim(),
                 flows: [], variants: [], entries: [], col: 0, row: 0, x: 0, y: 0 }
        byKey.set(key, node)
        baseOf.set(node, `${j.ac_ref}|${(j.end_state ?? '').trim()}`)
      }
      if (!node.flows.includes(f.id)) node.flows.push(f.id)
      node.entries.push({ flow: f.id, jid: j.id, note: (j.note ?? '').trim() })
      const variant = node.variants.find((v) => v.note === note)
      if (variant) { if (!variant.flows.includes(f.id)) variant.flows.push(f.id) }
      else node.variants.push({ note, flows: [f.id] })
      if (prev && prev !== node) {
        const id = `${prev.id}>${node.id}`
        const e = edgeMap.get(id)
        if (e) { if (!e.flows.includes(f.id)) e.flows.push(f.id) }
        else edgeMap.set(id, { id, from: prev.id, to: node.id, flows: [f.id] })
      }
      prev = node
    })
  })

  const nodes = [...byKey.values()]
  const edges = [...edgeMap.values()]
  // Longest-path layering: a step sits one column right of its latest
  // predecessor. Capped, so two flows that order the same steps differently
  // (a cycle in the merged graph) still lay out instead of looping.
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const siblings = new Map<string, OvNode[]>()
  nodes.forEach((n) => siblings.set(baseOf.get(n)!, [...(siblings.get(baseOf.get(n)!) ?? []), n]))
  for (let pass = 0; pass < nodes.length * 2; pass++) {
    let moved = false
    edges.forEach((e) => {
      const a = byId.get(e.from)!, b = byId.get(e.to)!
      if (b.col < a.col + 1 && a.col + 1 <= nodes.length) { b.col = a.col + 1; moved = true }
    })
    // the data variants of one step stand in one column, so they read as lanes
    siblings.forEach((list) => {
      const col = Math.max(...list.map((n) => n.col))
      list.forEach((n) => { if (n.col !== col) { n.col = col; moved = true } })
    })
    if (!moved) break
  }
  // Within a column the step most flows share takes the top row: the common
  // path reads as one straight line and the departures drop below it.
  const cols = new Map<number, OvNode[]>()
  nodes.forEach((n) => cols.set(n.col, [...(cols.get(n.col) ?? []), n]))
  cols.forEach((list) => {
    list.map((n, i) => ({ n, i }))
      .sort((a, b) => b.n.flows.length - a.n.flows.length || a.i - b.i)
      .forEach(({ n }, row) => { n.row = row; n.x = n.col * COL_W; n.y = row * ROW_H })
  })
  return { nodes, edges, flows, shared: nodes.filter((n) => n.flows.length === flows.length).length }
}
