import { useEffect, useState } from 'react'

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

// Single-segment routes (#/dashboard, #/rtm, ...). 'story' and 'explore' are
// handled explicitly because they carry a trailing segment.
const FLAT = new Set([
  'dashboard', 'board', 'stories', 'documents',
  'testcases', 'coverage', 'suites', 'changes', 'activity', 'rtm', 'settings', 'inbox',
])

export function viewFromHash(): View {
  const raw = window.location.hash.replace(/^#\/?/, '')
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
    default: return `#/${v.kind}`
  }
}

export function useView(): View {
  const [view, setView] = useState<View>(viewFromHash)
  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return view
}
