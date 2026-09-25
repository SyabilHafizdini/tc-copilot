import { describe, it, expect } from 'vitest'
// @ts-ignore - plain JS module
import { injectGraph } from './bake.mjs'

const TEMPLATE = '<!doctype html><html><head><meta charset="utf-8"></head><body></body></html>'

describe('injectGraph', () => {
  it('injects the payload immediately after <head>', () => {
    const out = injectGraph(TEMPLATE, { nodes: [], edges: [] })
    expect(out).toContain('<head><script>window.__GRAPH_DATA__ = {"nodes":[],"edges":[]};</script>')
  })
  it('does not expand $-replacement patterns from user data', () => {
    const data = { nodes: [{ nodeId: 'n1', nodeType: 'T', displayLabel: "US$$100 and $' and $&", properties: {} }], edges: [] }
    const out = injectGraph(TEMPLATE, data)!
    expect(out).toContain("US$$100 and $' and $&")
    expect(out.endsWith('</html>')).toBe(true)
  })
  it('escapes < so </script> in data cannot break out', () => {
    const out = injectGraph(TEMPLATE, { nodes: [], edges: [], meta: { title: '</script><img>' } })!
    expect(out).not.toContain('</script><img>')
  })
  it('returns null when no <head> exists', () => {
    expect(injectGraph('<html></html>', { nodes: [], edges: [] })).toBeNull()
  })
  it('carries presets into the injected payload', () => {
    const template = '<head></head><body></body>'
    const graph = {
      presets: [{ name: 'P', nodeTypes: ['Page'] }],
      nodes: [{ nodeId: 'n1', nodeType: 'Page', displayLabel: 'a', properties: {} }],
      edges: [],
    }
    const out = injectGraph(template, graph)
    expect(out).toContain('"presets":[{"name":"P","nodeTypes":["Page"]}]')
  })
})
