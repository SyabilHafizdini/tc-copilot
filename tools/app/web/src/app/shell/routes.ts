import { useEffect, useState } from 'react'
import { confirmDiscard } from './unsaved'

export type View =
  | { kind: 'projects' }
  | { kind: 'dashboard' }
  | { kind: 'board' }
  | { kind: 'stories' }
  | { kind: 'story'; id: string }
  | { kind: 'documents' }
  | { kind: 'explore'; path?: string }
  | { kind: 'testcases' } | { kind: 'coverage' } | { kind: 'suites' }
  | { kind: 'changes' } | { kind: 'activity' }
  | { kind: 'rtm' } | { kind: 'settings' } | { kind: 'inbox' }
  | { kind: 'flowbuilder' }
  | { kind: 'workbook'; wbKind: string; file: string; sheet?: string; row?: number }

function decode(part: string): string {
  try { return decodeURIComponent(part) } catch { return part }
}

// #/workbook/<kind>/<file>?sheet=<name>&row=<n>. A bare #/workbook (the nav
// entry) has no file yet: the page picks the newest workbook itself. Parsed
// here, apart from the generic split below, because it is the one route with
// a query string and a sheet name may hold any character but a slash.
function workbookFromHash(raw: string): View {
  const cut = raw.indexOf('?')
  const path = cut < 0 ? raw : raw.slice(0, cut)
  const query = new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1))
  const [, wbKind = '', ...rest] = path.split('/')
  const view: View = { kind: 'workbook', wbKind: decode(wbKind), file: decode(rest.join('/')) }
  const sheet = query.get('sheet')
  if (sheet) view.sheet = sheet
  const row = Number(query.get('row'))
  if (Number.isInteger(row) && row > 0) view.row = row
  return view
}

// Single-segment routes (#/dashboard, #/rtm, ...). 'story' and 'explore' are
// handled explicitly because they carry a trailing segment.
const FLAT = new Set([
  'dashboard', 'board', 'stories', 'documents',
  'testcases', 'coverage', 'suites', 'changes', 'activity', 'rtm', 'settings', 'inbox', 'flowbuilder',
])

export function viewFromHash(): View {
  // A view may carry a query ("#/testcases?level=sit"): it belongs to the
  // page, not to the route.
  const full = window.location.hash.replace(/^#\/?/, '')
  if (/^workbook(?:[/?]|$)/.test(full)) return workbookFromHash(full)
  const raw = full.split('?')[0]
  const [head, ...rest] = raw.split('/')
  if (head === 'story' && rest[0]) return { kind: 'story', id: rest[0] }
  if (head === 'explore') {
    const path = rest.join('/')
    return path ? { kind: 'explore', path } : { kind: 'explore' }
  }
  if (FLAT.has(head)) return { kind: head } as View
  return { kind: 'projects' }
}

export function hrefFor(v: View): string {
  switch (v.kind) {
    case 'story': return `#/story/${v.id}`
    case 'explore': return v.path ? `#/explore/${v.path}` : '#/explore'
    case 'projects': return '#/projects'
    case 'workbook': {
      if (!v.file) return '#/workbook'
      const query = new URLSearchParams()
      if (v.sheet) query.set('sheet', v.sheet)
      if (v.row) query.set('row', String(v.row))
      const tail = query.toString()
      return `#/workbook/${encodeURIComponent(v.wbKind)}/${encodeURIComponent(v.file)}`
        + (tail ? `?${tail}` : '')
    }
    default: return `#/${v.kind}`
  }
}

export function useView(): View {
  const [view, setView] = useState<View>(viewFromHash)
  useEffect(() => {
    // The guard lives here, in the one listener that changes the page: a
    // route change unmounts whatever editor is open, so with unsaved text the
    // operator is asked first, and a "no" puts the address back without the
    // view ever having moved.
    let last = window.location.hash
    let undoing = false
    const onHash = () => {
      const next = window.location.hash
      if (undoing) { undoing = false; last = next; return }
      if (next !== last && !confirmDiscard()) {
        undoing = true
        window.location.replace(last || '#/')
        // The address did not move back (nothing will fire): do not swallow
        // the next real change.
        if (window.location.hash === next) undoing = false
        return
      }
      last = next
      setView(viewFromHash())
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return view
}
