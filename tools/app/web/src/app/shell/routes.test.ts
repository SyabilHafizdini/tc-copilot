import { describe, it, expect, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { viewFromHash, hrefFor, useView, type View } from './routes'

afterEach(() => { window.location.hash = '' })

describe('viewFromHash', () => {
  it('defaults to the projects portfolio for an empty hash', () => {
    window.location.hash = ''
    expect(viewFromHash()).toEqual({ kind: 'projects' })
  })
  it('parses a flat view', () => {
    window.location.hash = '#/dashboard'
    expect(viewFromHash()).toEqual({ kind: 'dashboard' })
  })
  it('parses a story id', () => {
    window.location.hash = '#/story/US-VHLD'
    expect(viewFromHash()).toEqual({ kind: 'story', id: 'US-VHLD' })
  })
  it('parses an explore path with slashes', () => {
    window.location.hash = '#/explore/stories/US-VHLD.md'
    expect(viewFromHash()).toEqual({ kind: 'explore', path: 'stories/US-VHLD.md' })
  })
  it('falls back to projects for an unknown head', () => {
    window.location.hash = '#/nonsense'
    expect(viewFromHash()).toEqual({ kind: 'projects' })
  })
  it('parses the inbox view', () => {
    window.location.hash = '#/inbox'
    expect(viewFromHash()).toEqual({ kind: 'inbox' })
  })
})

describe('hrefFor', () => {
  it('round-trips flat, story, explore, inbox and projects views', () => {
    const cases: View[] = [
      { kind: 'dashboard' }, { kind: 'story', id: 'US-VHLD' },
      { kind: 'explore', path: 'glossary/term.md' }, { kind: 'projects' },
      { kind: 'inbox' },
    ]
    for (const v of cases) {
      window.location.hash = hrefFor(v)
      expect(viewFromHash()).toEqual(v)
    }
  })
  it('produces #/inbox for the inbox view', () => {
    expect(hrefFor({ kind: 'inbox' })).toBe('#/inbox')
  })
})

describe('useView', () => {
  it('updates when the hash changes', () => {
    window.location.hash = '#/dashboard'
    const { result } = renderHook(() => useView())
    expect(result.current).toEqual({ kind: 'dashboard' })
    act(() => {
      window.location.hash = '#/stories'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(result.current).toEqual({ kind: 'stories' })
  })
})
