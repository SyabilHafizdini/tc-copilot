import { describe, it, expect, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { viewFromHash, hrefFor, useView, type View } from './routes'
import { DISCARD_PROMPT, confirmDiscard, hasUnsavedDraft, setUnsavedDraft } from './unsaved'

afterEach(() => {
  window.location.hash = ''
  setUnsavedDraft('test-draft', false)
  vi.restoreAllMocks()
})

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
  it('ignores a query after the route', () => {
    window.location.hash = '#/testcases?level=sit&confidence=Low'
    expect(viewFromHash()).toEqual({ kind: 'testcases' })
    window.location.hash = '#/story/US-VHLD?x=1'
    expect(viewFromHash()).toEqual({ kind: 'story', id: 'US-VHLD' })
  })
  it('parses the inbox view', () => {
    window.location.hash = '#/inbox'
    expect(viewFromHash()).toEqual({ kind: 'inbox' })
  })
  it('parses the flow builder beside the workbook and test case routes', () => {
    window.location.hash = '#/flowbuilder'
    expect(viewFromHash()).toEqual({ kind: 'flowbuilder' })
    expect(hrefFor({ kind: 'flowbuilder' })).toBe('#/flowbuilder')
    window.location.hash = '#/workbook/sit/a-latest.xlsx?sheet=S&row=3'
    expect(viewFromHash()).toEqual(
      { kind: 'workbook', wbKind: 'sit', file: 'a-latest.xlsx', sheet: 'S', row: 3 })
    window.location.hash = '#/testcases?level=sit'
    expect(viewFromHash()).toEqual({ kind: 'testcases' })
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

describe('workbook route', () => {
  it('parses kind and file', () => {
    window.location.hash = '#/workbook/sit/demo-sit-latest.xlsx'
    expect(viewFromHash()).toEqual(
      { kind: 'workbook', wbKind: 'sit', file: 'demo-sit-latest.xlsx' })
  })
  it('round-trips a sheet name with spaces and brackets, and a row', () => {
    const v: View = {
      kind: 'workbook', wbKind: 'sit', file: 'demo-sit_20261004-101500.xlsx',
      sheet: 'C-TC-1 (Main flow)', row: 14,
    }
    const href = hrefFor(v)
    expect(href.startsWith('#/workbook/sit/demo-sit_20261004-101500.xlsx?')).toBe(true)
    window.location.hash = href
    expect(viewFromHash()).toEqual(v)
  })
  it('round-trips a file name holding space, %, #, ? and &', () => {
    const v: View = {
      kind: 'workbook', wbKind: 'sit', file: 'a b%c#d?e&f-latest.xlsx', sheet: 'S&1=#2?', row: 3,
    }
    window.location.hash = hrefFor(v)
    expect(viewFromHash()).toEqual(v)
  })
  it('treats a bare #/workbook as the picker (no file yet)', () => {
    expect(hrefFor({ kind: 'workbook', wbKind: '', file: '' })).toBe('#/workbook')
    window.location.hash = '#/workbook'
    expect(viewFromHash()).toEqual({ kind: 'workbook', wbKind: '', file: '' })
  })
  it('drops a row that is not a positive whole number', () => {
    for (const bad of ['0', '-3', '1.5', 'abc', '']) {
      window.location.hash = `#/workbook/sit/a-latest.xlsx?sheet=S&row=${bad}`
      expect(viewFromHash()).toEqual(
        { kind: 'workbook', wbKind: 'sit', file: 'a-latest.xlsx', sheet: 'S' })
    }
  })
  it('does not swallow other routes that merely start with the word', () => {
    window.location.hash = '#/workbooks'
    expect(viewFromHash()).toEqual({ kind: 'projects' })
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

  it('asks before a route change drops unsaved text, and a "no" puts the address back', () => {
    window.location.hash = '#/testcases'
    const { result } = renderHook(() => useView())
    setUnsavedDraft('test-draft', true)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    act(() => {
      window.location.hash = '#/suites'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(confirm).toHaveBeenCalledWith(DISCARD_PROMPT)
    expect(result.current).toEqual({ kind: 'testcases' })     // the page never moved
    expect(window.location.hash).toBe('#/testcases')          // and the address is back
    // the event the undo itself fires asks nothing and moves nothing
    act(() => { window.dispatchEvent(new HashChangeEvent('hashchange')) })
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(result.current).toEqual({ kind: 'testcases' })
    // a "yes" goes through
    confirm.mockReturnValue(true)
    act(() => {
      window.location.hash = '#/suites'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(result.current).toEqual({ kind: 'suites' })
  })

  it('asks nothing when no editor holds unsaved text', () => {
    window.location.hash = '#/testcases'
    const { result } = renderHook(() => useView())
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    act(() => {
      window.location.hash = '#/suites'
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(confirm).not.toHaveBeenCalled()
    expect(result.current).toEqual({ kind: 'suites' })
  })
})

describe('unsaved drafts', () => {
  it('counts editors by key and confirms only while one is registered', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(hasUnsavedDraft()).toBe(false)
    expect(confirmDiscard()).toBe(true)
    expect(confirm).not.toHaveBeenCalled()
    setUnsavedDraft('a', true)
    setUnsavedDraft('b', true)
    setUnsavedDraft('a', false)
    expect(hasUnsavedDraft()).toBe(true)
    expect(confirmDiscard()).toBe(false)
    setUnsavedDraft('b', false)
    expect(hasUnsavedDraft()).toBe(false)
    expect(confirmDiscard()).toBe(true)
    expect(confirm).toHaveBeenCalledTimes(1)
  })
})
