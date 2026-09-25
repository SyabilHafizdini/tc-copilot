#!/usr/bin/env node
// Zero-dependency bake: node scripts/bake.mjs <graph.json> [-o out.html]
// Injects the graph JSON into dist/viewer.html as window.__GRAPH_DATA__,
// producing a single shareable HTML file.
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve, basename } from 'node:path'
import { validateGraph } from '../src/lib/validate.mjs'

// Injects `data` into `template` right after the opening <head> tag as
// window.__GRAPH_DATA__. Returns the injected HTML string, or null if the
// template has no <head> tag to anchor on.
//
// Uses a function replacer (not a plain string) because String.replace
// treats "$&", "$'", "$`", "$$" as special patterns when the replacement is
// a string — untrusted graph data containing e.g. "US$$100" or "$'" would
// otherwise corrupt the output. A function replacer's return value is used
// verbatim.
export function injectGraph(template, data) {
  const payload = JSON.stringify(data).replace(/</g, '\\u003c')
  const injected = template.replace(
    /<head>/i,
    () => `<head><script>window.__GRAPH_DATA__ = ${payload};</script>`,
  )
  return injected === template ? null : injected
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const args = process.argv.slice(2)
  const oIdx = args.indexOf('-o')
  let outPath = null
  if (oIdx !== -1) {
    outPath = args[oIdx + 1]
    if (outPath === undefined) {
      console.error('ERROR: -o requires a value')
      process.exit(1)
    }
    args.splice(oIdx, 2)
  }
  const file = args[0]
  if (!file) {
    console.error('Usage: node scripts/bake.mjs <graph.json> [-o out.html]')
    process.exit(1)
  }

  const jsonPath = resolve(process.cwd(), file)
  const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const templatePath = resolve(projectRoot, 'dist', 'viewer.html')

  if (!existsSync(templatePath)) {
    console.error(`ERROR: ${templatePath} not found. Run "npm run build" first.`)
    process.exit(1)
  }

  let data
  try {
    data = JSON.parse(readFileSync(jsonPath, 'utf8'))
  } catch (err) {
    console.error(`ERROR: cannot read/parse ${jsonPath}: ${err.message}`)
    process.exit(1)
  }

  const errors = validateGraph(data)
  if (errors.length > 0) {
    for (const e of errors) console.error(`ERROR: ${e}`)
    console.error(`ERROR: refusing to bake: ${errors.length} error(s) in ${file}`)
    process.exit(1)
  }

  const template = readFileSync(templatePath, 'utf8')
  const injected = injectGraph(template, data)
  if (injected === null) {
    console.error('ERROR: could not find <head> in dist/viewer.html')
    process.exit(1)
  }

  const out = outPath
    ? resolve(process.cwd(), outPath)
    : resolve(dirname(jsonPath), basename(file).replace(/\.json$/i, '') + '.html')
  writeFileSync(out, injected)
  console.log(`Baked ${data.nodes.length} nodes, ${data.edges.length} edges -> ${out}`)
}
