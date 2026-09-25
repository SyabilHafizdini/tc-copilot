#!/usr/bin/env node
// Zero-dependency converter: node scripts/from-graphify.mjs <graphify graph.json> [-o out.json] [--title "Title"]
// Converts a graphify (networkx node-link) graph.json into graph-viewer
// format and validates the result. Hyperedges are dropped (pairwise only).
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { dirname, resolve, basename } from 'node:path'
import { validateGraph } from '../src/lib/validate.mjs'

// graphify file_type -> a colored viewer nodeType (see NODE_TYPE_COLORS).
// Unknown types pass through and render gray.
const TYPE_MAP = {
  code: 'Component',
  document: 'Page',
  paper: 'UserStory',
  image: 'State',
  rationale: 'BusinessRule',
}

function prune(obj) {
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v !== null && v !== undefined && v !== '') out[k] = v
  }
  return out
}

// node-link `links` reference nodes by id (or by whole-object after a
// round-trip through some tools) — normalize either to the id string.
function endpointId(ref) {
  return String(typeof ref === 'object' && ref !== null ? ref.id : ref)
}

export function fromGraphify(raw, { title } = {}) {
  const rawNodes = raw.nodes ?? []
  const rawLinks = raw.links ?? raw.edges ?? []
  const nodes = rawNodes.map((n) => ({
    nodeId: String(n.id),
    nodeType: TYPE_MAP[n.file_type] ?? n.file_type ?? 'Component',
    displayLabel: n.label || String(n.id),
    properties: prune({
      file_type: n.file_type,
      community: n.community,
      source_file: n.source_file,
      source_url: n.source_url,
      author: n.author,
      contributor: n.contributor,
      rationale: n.rationale,
    }),
  }))
  const edges = rawLinks.map((l, i) => ({
    edgeId: `e${i + 1}`,
    edgeType: String(l.relation ?? 'related_to').toUpperCase(),
    fromNodeId: endpointId(l.source),
    toNodeId: endpointId(l.target),
    properties: prune({
      confidence: l.confidence,
      confidence_score: l.confidence_score,
      weight: l.weight,
      source_file: l.source_file,
    }),
  }))
  const doc = { nodes, edges }
  if (title) doc.meta = { title }
  if (raw.presets !== undefined) doc.presets = raw.presets
  return { doc, droppedHyperedges: (raw.hyperedges ?? []).length }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const args = process.argv.slice(2)
  const takeValue = (flag) => {
    const idx = args.indexOf(flag)
    if (idx === -1) return null
    const value = args[idx + 1]
    if (value === undefined) {
      console.error(`ERROR: ${flag} requires a value`)
      process.exit(1)
    }
    args.splice(idx, 2)
    return value
  }
  const outPath = takeValue('-o')
  const title = takeValue('--title')
  const file = args[0]
  if (!file) {
    console.error(
      'Usage: node scripts/from-graphify.mjs <graph.json> [-o out.json] [--title "Title"]',
    )
    process.exit(1)
  }

  const jsonPath = resolve(process.cwd(), file)
  let raw
  try {
    raw = JSON.parse(readFileSync(jsonPath, 'utf8'))
  } catch (err) {
    console.error(`ERROR: cannot read/parse ${jsonPath}: ${err.message}`)
    process.exit(1)
  }

  const { doc, droppedHyperedges } = fromGraphify(raw, { title })
  const errors = validateGraph(doc)
  if (errors.length > 0) {
    for (const e of errors) console.error(`ERROR: ${e}`)
    console.error(`ERROR: converted graph is invalid: ${errors.length} error(s)`)
    process.exit(1)
  }

  const out = outPath
    ? resolve(process.cwd(), outPath)
    : resolve(dirname(jsonPath), basename(file).replace(/\.json$/i, '') + '-viewer.json')
  writeFileSync(out, JSON.stringify(doc, null, 2))
  const dropped = droppedHyperedges > 0 ? ` (${droppedHyperedges} hyperedge(s) dropped)` : ''
  console.log(`Converted ${doc.nodes.length} nodes, ${doc.edges.length} edges -> ${out}${dropped}`)
}
