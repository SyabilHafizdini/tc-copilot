import { describe, it, expect } from 'vitest'
import { resolvePreset, findDefaultPreset, matchActivePreset } from './presets'
import type { GraphPreset } from './types'

const NODE_TYPES = ['Page', 'Component', 'Field', 'APIEndpoint']
const EDGE_TYPES = ['HAS_COMPONENT', 'HAS_FIELD', 'CALLS']

describe('resolvePreset', () => {
  it('intersects nodeTypes/edgeTypes with what exists', () => {
    const p: GraphPreset = { name: 'x', nodeTypes: ['Page', 'Ghost'], edgeTypes: ['CALLS', 'Nope'] }
    const r = resolvePreset(p, NODE_TYPES, EDGE_TYPES)
    expect([...r.visibleTypes]).toEqual(['Page'])
    expect([...r.visibleEdgeTypes]).toEqual(['CALLS'])
  })

  it('omitted types mean all types', () => {
    const r = resolvePreset({ name: 'x' }, NODE_TYPES, EDGE_TYPES)
    expect(r.visibleTypes.size).toBe(NODE_TYPES.length)
    expect(r.visibleEdgeTypes.size).toBe(EDGE_TYPES.length)
  })

  it('search defaults to empty; explicit search passes through', () => {
    expect(resolvePreset({ name: 'x' }, NODE_TYPES, EDGE_TYPES).search).toBe('')
    expect(resolvePreset({ name: 'x', search: 'log' }, NODE_TYPES, EDGE_TYPES).search).toBe('log')
  })

  it('does not carry a view (presets are filter-only)', () => {
    expect('view' in resolvePreset({ name: 'x' }, NODE_TYPES, EDGE_TYPES)).toBe(false)
  })
})

describe('findDefaultPreset', () => {
  it('returns null when none flagged', () => {
    expect(findDefaultPreset([{ name: 'a' }, { name: 'b' }])).toBeNull()
  })
  it('returns the first default when several flagged', () => {
    const p = findDefaultPreset([{ name: 'a' }, { name: 'b', default: true }, { name: 'c', default: true }])
    expect(p?.name).toBe('b')
  })
})

describe('matchActivePreset', () => {
  const presets: GraphPreset[] = [
    { name: 'Login', nodeTypes: ['Page', 'Component'], search: 'log' },
    { name: 'All fields', nodeTypes: ['Field'] },
  ]
  it('matches on resolved sets + search, order-independent', () => {
    const name = matchActivePreset(
      presets, new Set(['Component', 'Page']), new Set(EDGE_TYPES), 'log', NODE_TYPES, EDGE_TYPES,
    )
    expect(name).toBe('Login')
  })
  it('returns null when search differs', () => {
    const name = matchActivePreset(
      presets, new Set(['Page', 'Component']), new Set(EDGE_TYPES), '', NODE_TYPES, EDGE_TYPES,
    )
    expect(name).toBeNull()
  })
  it('returns null when node set differs', () => {
    const name = matchActivePreset(
      presets, new Set(['Page']), new Set(EDGE_TYPES), 'log', NODE_TYPES, EDGE_TYPES,
    )
    expect(name).toBeNull()
  })
  it('never marks a show-everything preset active (no type lists)', () => {
    const ps: GraphPreset[] = [{ name: 'Overview' }]
    const name = matchActivePreset(
      ps, new Set(NODE_TYPES), new Set(EDGE_TYPES), '', NODE_TYPES, EDGE_TYPES,
    )
    expect(name).toBeNull()
  })
})
