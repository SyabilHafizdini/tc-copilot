import { describe, it, expect } from 'vitest'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - plain JS module shared with the CLI
import { validateGraph, normalizeGraph } from './validate.mjs'

const good = {
  meta: { title: 'T', typeColors: { PAGE: '#3B82F6' } },
  nodes: [
    { nodeId: 'n1', nodeType: 'Page', displayLabel: 'Login', properties: { name: 'login' } },
    { nodeId: 'n2', nodeType: 'Field', displayLabel: 'Email' },
  ],
  edges: [
    { edgeId: 'e1', edgeType: 'HAS_FIELD', fromNodeId: 'n1', toNodeId: 'n2' },
  ],
}

describe('validateGraph', () => {
  it('accepts a valid document (properties optional)', () => {
    expect(validateGraph(good)).toEqual([])
  })

  it('rejects non-object roots', () => {
    expect(validateGraph([])).toEqual(['root: expected an object with "nodes" and "edges" arrays'])
    expect(validateGraph('x')[0]).toMatch(/^root:/)
    expect(validateGraph(null)[0]).toMatch(/^root:/)
  })

  it('requires nodes and edges arrays', () => {
    expect(validateGraph({ nodes: [] })).toContain('edges: required array')
    expect(validateGraph({ edges: [] })).toContain('nodes: required array')
  })

  it('checks required node fields with precise paths', () => {
    const errs = validateGraph({
      nodes: [{ nodeId: '', nodeType: 'Page', displayLabel: 'x' }],
      edges: [],
    })
    expect(errs).toContain('nodes[0].nodeId: required non-empty string')
  })

  it('rejects duplicate node ids', () => {
    const errs = validateGraph({
      nodes: [
        { nodeId: 'n1', nodeType: 'A', displayLabel: 'a' },
        { nodeId: 'n1', nodeType: 'B', displayLabel: 'b' },
      ],
      edges: [],
    })
    expect(errs).toContain('nodes[1].nodeId: duplicate id "n1"')
  })

  it('rejects edges pointing at missing nodes', () => {
    const errs = validateGraph({
      nodes: [{ nodeId: 'n1', nodeType: 'A', displayLabel: 'a' }],
      edges: [{ edgeId: 'e1', edgeType: 'REL', fromNodeId: 'n1', toNodeId: 'x9' }],
    })
    expect(errs).toContain('edges[0].toNodeId: "x9" not found in nodes')
  })

  it('rejects duplicate edge ids and bad properties type', () => {
    const errs = validateGraph({
      nodes: [
        { nodeId: 'n1', nodeType: 'A', displayLabel: 'a' },
        { nodeId: 'n2', nodeType: 'A', displayLabel: 'b', properties: 'nope' },
      ],
      edges: [
        { edgeId: 'e1', edgeType: 'REL', fromNodeId: 'n1', toNodeId: 'n2' },
        { edgeId: 'e1', edgeType: 'REL', fromNodeId: 'n2', toNodeId: 'n1' },
      ],
    })
    expect(errs).toContain('edges[1].edgeId: duplicate id "e1"')
    expect(errs).toContain('nodes[1].properties: expected an object')
  })

  it('validates meta when present', () => {
    const errs = validateGraph({ meta: { title: 5 }, nodes: [], edges: [] })
    expect(errs).toContain('meta.title: expected a string')
  })

  it('accepts a string content on a node', () => {
    expect(validateGraph({
      nodes: [{ nodeId: 'n1', nodeType: 'Page', displayLabel: 'a', content: '# hi' }],
      edges: [],
    })).toEqual([])
  })

  it('rejects a non-string content', () => {
    const errs = validateGraph({
      nodes: [{ nodeId: 'n1', nodeType: 'Page', displayLabel: 'a', content: 5 }],
      edges: [],
    })
    expect(errs).toContain('nodes[0].content: expected a string')
  })
})

describe('normalizeGraph', () => {
  it('fills missing properties with {}', () => {
    const g = normalizeGraph(good)
    expect(g.nodes[1].properties).toEqual({})
    expect(g.edges[0].properties).toEqual({})
    expect(g.meta?.title).toBe('T')
    expect(g.meta?.typeColors).toEqual({ PAGE: '#3B82F6' })
  })
})

describe('validateGraph presets', () => {
  const base = {
    nodes: [{ nodeId: 'n1', nodeType: 'Page', displayLabel: 'a' }],
    edges: [],
  }
  it('accepts a well-formed preset', () => {
    expect(validateGraph({
      ...base,
      presets: [{ name: 'P', description: 'd', default: true, nodeTypes: ['Page'], edgeTypes: [], search: 'x' }],
    })).toEqual([])
  })
  it('tolerates unknown type names (not an error)', () => {
    expect(validateGraph({ ...base, presets: [{ name: 'P', nodeTypes: ['Ghost'] }] })).toEqual([])
  })
  it('ignores an unknown view field (presets are filter-only)', () => {
    expect(validateGraph({ ...base, presets: [{ name: 'P', view: 'sunburst' }] })).toEqual([])
  })
  it('rejects a non-array presets field', () => {
    expect(validateGraph({ ...base, presets: {} })).toContain('presets: expected an array')
  })
  it('requires a non-empty name', () => {
    expect(validateGraph({ ...base, presets: [{ nodeTypes: ['Page'] }] }))
      .toContain('presets[0].name: required non-empty string')
  })
  it('rejects wrong field types', () => {
    const errs = validateGraph({ ...base, presets: [{ name: 'P', search: 5, default: 'yes', nodeTypes: 'Page' }] })
    expect(errs).toContain('presets[0].search: expected a string')
    expect(errs).toContain('presets[0].default: expected a boolean')
    expect(errs).toContain('presets[0].nodeTypes: expected an array of strings')
  })
  it('rejects duplicate preset names', () => {
    const errs = validateGraph({ ...base, presets: [{ name: 'P' }, { name: 'P' }] })
    expect(errs).toContain('presets[1].name: duplicate name "P"')
  })
})

describe('normalizeGraph presets', () => {
  it('preserves the presets array', () => {
    const g = normalizeGraph({ ...good, presets: [{ name: 'P', nodeTypes: ['Page'] }] })
    expect(g.presets).toEqual([{ name: 'P', nodeTypes: ['Page'] }])
  })
})

describe('meta.typeColors', () => {
  const withColors = (typeColors: unknown) =>
    validateGraph({ ...good, meta: { title: 'T', typeColors } })

  it('accepts well-formed hex colors and an empty map', () => {
    expect(withColors({ PAGE: '#3B82F6', VALIDATION_RULE: '#f00' })).toEqual([])
    expect(withColors({})).toEqual([])
  })

  it('still accepts meta without typeColors', () => {
    expect(validateGraph(good)).toEqual([])
  })

  it('rejects a non-object typeColors', () => {
    expect(withColors([])).toContain('meta.typeColors: expected an object')
    expect(withColors('#fff')).toContain('meta.typeColors: expected an object')
  })

  it('rejects malformed colors, naming the offending type in the path', () => {
    const msg = 'meta.typeColors.PAGE: expected a hex color like "#3B82F6"'
    expect(withColors({ PAGE: 'blue' })).toContain(msg)
    expect(withColors({ PAGE: '#12345' })).toContain(msg)
    expect(withColors({ PAGE: 123 })).toContain(msg)
  })
})
