import { describe, it, expect } from 'vitest'
import {
  resolveTypeColors,
  getNodeColor,
  NODE_TYPE_COLORS,
  DEFAULT_NODE_COLOR,
} from './nodeStyle'

describe('resolveTypeColors', () => {
  it('returns the built-in palette when there are no overrides', () => {
    expect(resolveTypeColors()).toEqual(NODE_TYPE_COLORS)
    expect(resolveTypeColors({})).toEqual(NODE_TYPE_COLORS)
  })

  it('overrides a built-in color and leaves the others alone', () => {
    const r = resolveTypeColors({ Page: '#123456' })
    expect(r.Page).toBe('#123456')
    expect(r.Component).toBe(NODE_TYPE_COLORS.Component)
  })

  it('adds a type the built-in palette does not know', () => {
    const r = resolveTypeColors({ VALIDATION_RULE: '#EF4444' })
    expect(r.VALIDATION_RULE).toBe('#EF4444')
    expect(Object.keys(r)).toHaveLength(Object.keys(NODE_TYPE_COLORS).length + 1)
  })

  it('expands three-digit shorthand to six digits', () => {
    expect(resolveTypeColors({ PAGE: '#F00' }).PAGE).toBe('#FF0000')
    expect(resolveTypeColors({ PAGE: '#abc' }).PAGE).toBe('#aabbcc')
  })

  it('does not mutate the built-in palette', () => {
    resolveTypeColors({ Page: '#000000' })
    expect(NODE_TYPE_COLORS.Page).toBe('#3B82F6')
  })

  it('skips malformed values, keeping the built-in color', () => {
    expect(resolveTypeColors({ Page: 'not-a-color' }).Page).toBe(NODE_TYPE_COLORS.Page)
    expect(resolveTypeColors({ Page: '#12345' }).Page).toBe(NODE_TYPE_COLORS.Page)
    expect(resolveTypeColors({ Page: 123 as unknown as string }).Page).toBe(NODE_TYPE_COLORS.Page)
  })

  it('skips a malformed value without dropping the well-formed ones beside it', () => {
    const r = resolveTypeColors({ Page: 'nope', VALIDATION_RULE: '#EF4444' })
    expect(r.Page).toBe(NODE_TYPE_COLORS.Page)
    expect(r.VALIDATION_RULE).toBe('#EF4444')
  })

  it('returns a copy, never the shared constant', () => {
    expect(resolveTypeColors()).not.toBe(NODE_TYPE_COLORS)
    expect(resolveTypeColors()).toEqual(NODE_TYPE_COLORS)
  })
})

describe('getNodeColor', () => {
  it('reads the built-in palette when given the built-in palette', () => {
    expect(getNodeColor('Page', NODE_TYPE_COLORS)).toBe('#3B82F6')
  })

  it('reads the supplied palette when one is given', () => {
    const palette = resolveTypeColors({ PAGE: '#EF4444' })
    expect(getNodeColor('PAGE', palette)).toBe('#EF4444')
  })

  it('falls back to the default gray for an unknown type', () => {
    expect(getNodeColor('Nope', NODE_TYPE_COLORS)).toBe(DEFAULT_NODE_COLOR)
    expect(getNodeColor('Nope', resolveTypeColors({ PAGE: '#F00' }))).toBe(DEFAULT_NODE_COLOR)
  })
})
