import { useCallback, useEffect, useState } from 'react'
import { getWorkbookInventory, onChange } from '../api'
import type { WbSkipped, WorkbookEntry } from './types'

// The workbook inventory (null while loading). With `live` it re-reads when
// the wiki changes - a changed test case flips an entry to 'changed'. A
// compile writes only under build/, which fires no change event, so callers
// that compile call reload() themselves. Pass live=false when the caller
// already holds a change subscription: each one is an open connection.
//
// A read that FAILS is not an empty inventory: `error` carries what the server
// said and `books` keeps what was last read (null when nothing ever was), so
// no page tells the operator "nothing compiled yet" because a request failed.
// `skipped` lists the files the server could not read.
export function useWorkbooks(live = true): {
  books: WorkbookEntry[] | null
  skipped: WbSkipped[]
  error: string | null
  reload: () => void
} {
  const [read, setRead] = useState<{
    books: WorkbookEntry[] | null; skipped: WbSkipped[]; error: string | null
  }>({ books: null, skipped: [], error: null })
  const reload = useCallback(() => {
    getWorkbookInventory()
      .then((inv) => setRead({ books: inv.workbooks, skipped: inv.skipped, error: null }))
      .catch((e: unknown) => setRead((r) => ({ ...r, error: e instanceof Error ? e.message : String(e) })))
  }, [])
  useEffect(() => {
    reload()
    return live ? onChange(reload) : undefined
  }, [reload, live])
  return { ...read, reload }
}
