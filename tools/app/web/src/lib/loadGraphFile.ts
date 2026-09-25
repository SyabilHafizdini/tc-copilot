import type { GraphDocument } from './types'
// @ts-ignore - plain JS module shared with the CLI
import { validateGraph, normalizeGraph } from './validate.mjs'

export type LoadResult =
  | { ok: true; graph: GraphDocument; title: string }
  | { ok: false; errors: string[] }

/** Read, parse, validate, and normalize a dropped/picked graph JSON file. */
export async function loadGraphFile(file: File): Promise<LoadResult> {
  let data: unknown
  try {
    data = JSON.parse(await file.text())
  } catch (err) {
    return {
      ok: false,
      errors: [`Invalid JSON: ${err instanceof Error ? err.message : String(err)}`],
    }
  }
  const errors = validateGraph(data) as string[]
  if (errors.length > 0) return { ok: false, errors }
  const graph = normalizeGraph(data) as GraphDocument
  const title = graph.meta?.title ?? file.name.replace(/\.json$/i, '')
  return { ok: true, graph, title }
}
