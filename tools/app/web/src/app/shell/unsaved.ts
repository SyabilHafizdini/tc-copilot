import { useSyncExternalStore } from 'react'

/* Editors that hold text the operator has not saved.
 *
 * An editor registers itself while its draft differs from the text it opened
 * with (PartEditor). Everything that would unmount an editor - another row,
 * Prev / Next / Close, a sheet tab, a route change - asks confirmDiscard()
 * first, and the views keep the open row mounted while a draft exists, so a
 * filter or a reload cannot drop it.
 *
 * A module store, not a React context: the hash guard in useView and the
 * beforeunload handler in App need it outside the component tree. */
const drafts = new Set<string>()
const listeners = new Set<() => void>()

export const DISCARD_PROMPT = 'You have unsaved text in an editor. Discard it?'

export function setUnsavedDraft(key: string, unsaved: boolean): void {
  if (unsaved === drafts.has(key)) return
  if (unsaved) drafts.add(key)
  else drafts.delete(key)
  listeners.forEach((l) => l())
}

export function hasUnsavedDraft(): boolean {
  return drafts.size > 0
}

/* True when nothing is unsaved, or the operator agrees to lose it. */
export function confirmDiscard(): boolean {
  return drafts.size === 0 || window.confirm(DISCARD_PROMPT)
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/* Re-renders the caller when the first draft appears or the last one goes. */
export function useUnsavedDraft(): boolean {
  return useSyncExternalStore(subscribe, hasUnsavedDraft, hasUnsavedDraft)
}
