import { describe, it, expect } from 'vitest'
import type { GraphDocument } from '../src/lib/types'
// @ts-ignore - plain JS module
import { fromGraphify as fromGraphifyJs } from './from-graphify.mjs'
// @ts-ignore - plain JS module
import { validateGraph } from '../src/lib/validate.mjs'

const fromGraphify = fromGraphifyJs as (
  raw: unknown,
  opts?: { title?: string },
) => { doc: GraphDocument; droppedHyperedges: number }

const sample = {
  directed: false,
  nodes: [
    { id: 'auth_login', label: 'login()', file_type: 'code', source_file: 'auth.py', community: 0, norm_label: 'login()' },
    { id: 'paper_attention', label: 'Attention Is All You Need', file_type: 'paper', community: 1, author: null },
    { id: 'mystery', label: '', file_type: 'weird_type' },
  ],
  links: [
    { source: 'auth_login', target: 'paper_attention', relation: 'references', confidence: 'INFERRED', confidence_score: 0.85, weight: 1 },
    { source: { id: 'paper_attention' }, target: { id: 'mystery' }, relation: null },
  ],
  hyperedges: [{ id: 'h1', nodes: ['auth_login', 'mystery'], relation: 'participate_in' }],
}

describe('fromGraphify', () => {
  it('produces a graph that passes the viewer validator', () => {
    const { doc } = fromGraphify(sample)
    expect(validateGraph(doc)).toEqual([])
  })

  it('maps file_type to colored viewer types and passes unknown types through', () => {
    const { doc } = fromGraphify(sample)
    expect(doc.nodes.map((n) => n.nodeType)).toEqual(['Component', 'UserStory', 'weird_type'])
  })

  it('falls back to the id when label is empty and uppercases relations', () => {
    const { doc } = fromGraphify(sample)
    expect(doc.nodes[2].displayLabel).toBe('mystery')
    expect(doc.edges.map((e) => e.edgeType)).toEqual(['REFERENCES', 'RELATED_TO'])
  })

  it('accepts object-form endpoints and prunes null properties', () => {
    const { doc } = fromGraphify(sample)
    expect(doc.edges[1].fromNodeId).toBe('paper_attention')
    expect(doc.edges[1].toNodeId).toBe('mystery')
    expect('author' in doc.nodes[1].properties).toBe(false)
    expect(doc.nodes[0].properties.community).toBe(0)
  })

  it('counts dropped hyperedges and sets meta.title when given', () => {
    const { doc, droppedHyperedges } = fromGraphify(sample, { title: 'My Corpus' })
    expect(droppedHyperedges).toBe(1)
    expect(doc.meta?.title).toBe('My Corpus')
  })

  it('passes a presets array through to the converted doc', () => {
    const raw = {
      presets: [{ name: 'P', nodeTypes: ['Component'] }],
      nodes: [{ id: 'x', label: 'X', file_type: 'code' }],
      links: [],
    }
    const { doc } = fromGraphify(raw)
    expect(doc.presets).toEqual([{ name: 'P', nodeTypes: ['Component'] }])
  })
})
