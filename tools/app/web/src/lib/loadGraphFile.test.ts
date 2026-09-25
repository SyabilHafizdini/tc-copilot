import { describe, it, expect } from 'vitest'
import { loadGraphFile } from './loadGraphFile'

function make(contents: string, name = 'g.json'): File {
  return new File([contents], name, { type: 'application/json' })
}

describe('loadGraphFile', () => {
  it('loads and normalizes a valid file, title from meta', async () => {
    const res = await loadGraphFile(
      make(
        JSON.stringify({
          meta: { title: 'My Graph' },
          nodes: [{ nodeId: 'n1', nodeType: 'T', displayLabel: 'A' }],
          edges: [],
        }),
      ),
    )
    expect(res.ok).toBe(true)
    if (res.ok) {
      expect(res.title).toBe('My Graph')
      expect(res.graph.nodes[0].properties).toEqual({})
    }
  })

  it('falls back to the file name with .json stripped (case-insensitive)', async () => {
    const res = await loadGraphFile(
      make(JSON.stringify({ nodes: [], edges: [] }), 'checkout-flow.JSON'),
    )
    expect(res.ok).toBe(true)
    if (res.ok) expect(res.title).toBe('checkout-flow')
  })

  it('reports parse errors', async () => {
    const res = await loadGraphFile(make('{nope'))
    expect(res.ok).toBe(false)
    if (!res.ok) expect(res.errors[0]).toMatch(/^Invalid JSON: /)
  })

  it('reports schema errors verbatim', async () => {
    const res = await loadGraphFile(
      make(JSON.stringify({ nodes: [{ nodeId: 'n1' }], edges: [] })),
    )
    expect(res.ok).toBe(false)
    if (!res.ok) {
      expect(res.errors).toContain('nodes[0].nodeType: required non-empty string')
      expect(res.errors).toContain('nodes[0].displayLabel: required non-empty string')
    }
  })
})
