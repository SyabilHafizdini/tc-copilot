#!/usr/bin/env node
// Zero-dependency CLI: node scripts/validate.mjs <graph.json>
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { validateGraph } from '../src/lib/validate.mjs'

const file = process.argv[2]
if (!file) {
  console.error('Usage: node scripts/validate.mjs <graph.json>')
  process.exit(1)
}

const path = resolve(process.cwd(), file)
let raw
try {
  raw = readFileSync(path, 'utf8')
} catch (err) {
  console.error(`ERROR: cannot read ${path}: ${err.message}`)
  process.exit(1)
}

let data
try {
  data = JSON.parse(raw)
} catch (err) {
  console.error(`ERROR: invalid JSON: ${err.message}`)
  process.exit(1)
}

const errors = validateGraph(data)
if (errors.length > 0) {
  for (const e of errors) console.error(`ERROR: ${e}`)
  console.error(`ERROR: ${errors.length} error(s) in ${file}`)
  process.exit(1)
}
console.log(`OK: ${data.nodes.length} nodes, ${data.edges.length} edges`)
