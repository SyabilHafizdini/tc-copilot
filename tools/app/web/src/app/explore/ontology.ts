/** Logical-ontology tree built from the graph model (nodes + links), NOT the
 * filesystem paths. Mirrors the traceability spine the wiki enforces:
 *
 *   Module ──contains──▶ User Story ──has_ac──▶ Acceptance Criterion ──covered_by──▶ Test Case
 *                                   ──has_br──▶ Business Rule        ──verified_by─▶ Test Case
 *                                   ──has────▶ Component
 *
 * Docs that no module owns (PRD sections, glossary terms, flows, resolutions,
 * figma pages) hang off sibling top-level groups. Pure — no React, no I/O —
 * so it unit-tests in isolation. */

import type { GraphModel, DocView } from '../explorer/types'

/** A node is *expandable* when it has children and *selectable* when `ref` is
 * set (a real doc rel or a `story#fragment` id the content pane can open).
 * Synthetic group nodes (Modules, Acceptance Criteria, …) carry `ref: null`. */
export type OntologyNode = {
  id: string
  label: string
  /** graph node type (Module/Story/AC/…) or the sentinel 'group'. Drives the icon. */
  nodeType: string
  ref: string | null
  status: string | null
  count: number | null
  children: OntologyNode[]
}

type Raw = GraphModel['nodes'][number]

const byNumeric = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })

/** Build the ontology forest. `docs` supplies human titles/statuses for the
 * doc-backed nodes; graph `state` fills in for fragment nodes (AC/BR) that
 * have no own doc entry. */
export function buildOntologyTree(graph: GraphModel, docs: Record<string, DocView>): OntologyNode[] {
  const nodes = new Map<string, Raw>(graph.nodes.map((n) => [n.id, n]))
  const of = (type: string) => graph.nodes.filter((n) => n.type === type)

  // Adjacency indexed by the relation direction build_model emits.
  const targets = (relType: string, source: string) =>
    graph.links.filter((l) => l.type === relType && l.source === source).map((l) => l.target)
  const sources = (relType: string, target: string) =>
    graph.links.filter((l) => l.type === relType && l.target === target).map((l) => l.source)

  const titleOf = (ref: string, fallback: string) => docs[ref]?.title ?? fallback
  const statusOf = (ref: string) => docs[ref]?.status ?? nodes.get(ref)?.state ?? null

  const leaf = (ref: string, label: string, nodeType: string, status: string | null): OntologyNode =>
    ({ id: ref, label, nodeType, ref, status, count: null, children: [] })

  const group = (id: string, label: string, children: OntologyNode[]): OntologyNode =>
    ({ id, label, nodeType: 'group', ref: null, status: null, count: children.length, children })

  // Test cases hanging off an AC (covers) or a BR (verifies_rules).
  const tcsUnder = (relType: string, targetId: string): OntologyNode[] =>
    sources(relType, targetId)
      .map((tc) => leaf(tc, tc.split('/').pop() ?? tc, 'TC', statusOf(tc)))
      .sort((a, b) => byNumeric(a.label, b.label))

  // One user story with its AC / BR / Component branches (empty ones omitted).
  const storyNode = (storyId: string): OntologyNode => {
    const acNodes = targets('has_ac', storyId)
      .map((ac) => ({ ...frag(ac), children: tcsUnder('covers', ac) }))
      .sort((a, b) => byNumeric(a.label, b.label))
    const brNodes = targets('has_br', storyId)
      .map((br) => ({ ...frag(br), children: tcsUnder('verifies_rules', br) }))
      .sort((a, b) => byNumeric(a.label, b.label))
    const compNodes = graph.nodes
      .filter((n) => n.type === 'Component' && n.id.startsWith(`${storyId}#`))
      .map((n) => frag(n.id))
      .sort((a, b) => byNumeric(a.label, b.label))

    const branches: OntologyNode[] = []
    if (acNodes.length) branches.push(group(`${storyId}::ac`, 'Acceptance Criteria', acNodes))
    if (brNodes.length) branches.push(group(`${storyId}::br`, 'Business Rules', brNodes))
    if (compNodes.length) branches.push(group(`${storyId}::comp`, 'Components', compNodes))

    const n = nodes.get(storyId)
    return {
      id: storyId, ref: storyId, nodeType: 'Story',
      label: titleOf(storyId, n?.label ?? storyId),
      status: statusOf(storyId), count: branches.length || null, children: branches,
    }
  }

  // AC / BR / Component fragment node (id is `story#fragment`).
  function frag(fragId: string): OntologyNode {
    const n = nodes.get(fragId)
    return {
      id: fragId, ref: fragId, nodeType: n?.type ?? 'AC',
      label: n?.label ?? fragId.split('#').pop() ?? fragId,
      status: n?.state ?? null, count: null, children: [],
    }
  }

  // Modules → their stories. Many doc kinds (TCs, resolutions, …) also carry a
  // `module` frontmatter link, so restrict a module's children to Story nodes.
  const isStory = (id: string) => nodes.get(id)?.type === 'Story'
  const moduleNodes = of('Module')
    .map((m) => {
      const stories = sources('module', m.id)
        .filter(isStory)
        .map(storyNode)
        .sort((a, b) => byNumeric(a.label, b.label))
      return {
        id: m.id, ref: m.id, nodeType: 'Module',
        label: titleOf(m.id, m.label ?? m.id),
        status: statusOf(m.id), count: stories.length, children: stories,
      }
    })
    .sort((a, b) => byNumeric(a.label, b.label))

  // Stories no module claims still deserve a home.
  const claimed = new Set(
    graph.links.filter((l) => l.type === 'module').map((l) => l.source),
  )
  const orphanStories = of('Story')
    .filter((s) => !claimed.has(s.id))
    .map((s) => storyNode(s.id))
    .sort((a, b) => byNumeric(a.label, b.label))

  const flatGroup = (id: string, label: string, type: string): OntologyNode | null => {
    const items = of(type)
      .map((n) => leaf(n.id, titleOf(n.id, n.label ?? n.id), type, statusOf(n.id)))
      .sort((a, b) => byNumeric(a.label, b.label))
    return items.length ? group(id, label, items) : null
  }

  const sources_grp = (() => {
    const prd = of('PRD Section').map((n) => leaf(n.id, titleOf(n.id, n.label ?? n.id), 'PRD Section', statusOf(n.id)))
    const figma = of('Figma Page').map((n) => leaf(n.id, titleOf(n.id, n.label ?? n.id), 'Figma Page', statusOf(n.id)))
    const items = [...prd, ...figma].sort((a, b) => byNumeric(a.label, b.label))
    return items.length ? group('grp::sources', 'Sources (PRD)', items) : null
  })()

  const modulesChildren = [...moduleNodes, ...orphanStories]
  const forest: OntologyNode[] = []
  if (modulesChildren.length) forest.push(group('grp::modules', 'Modules', modulesChildren))
  if (sources_grp) forest.push(sources_grp)
  const glossary = flatGroup('grp::glossary', 'Glossary', 'Term')
  const flows = flatGroup('grp::flows', 'Flows', 'Flow')
  const resolutions = flatGroup('grp::resolutions', 'Resolutions', 'Resolution')
  if (glossary) forest.push(glossary)
  if (flows) forest.push(flows)
  if (resolutions) forest.push(resolutions)

  return forest
}

/** Ancestor node ids of the node whose `ref` equals `target`, shallowest
 * first — used to auto-expand the path to the current selection. Returns []
 * when the ref isn't in the tree. */
export function ancestorIds(forest: OntologyNode[], target: string): string[] {
  const path: string[] = []
  const walk = (node: OntologyNode, trail: string[]): boolean => {
    if (node.ref === target) { path.push(...trail); return true }
    for (const c of node.children) if (walk(c, [...trail, node.id])) return true
    return false
  }
  for (const root of forest) if (walk(root, [])) break
  return path
}
