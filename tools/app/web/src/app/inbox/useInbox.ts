import { useCallback, useEffect, useState } from 'react'
import { getInbox, onChange } from '../api'
import type { InboxSnapshot } from './types'

export function useInbox() {
  const [snapshot, setSnapshot] = useState<InboxSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const load = useCallback(() => {
    getInbox().then(setSnapshot).catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    load()
    return onChange(load)
  }, [load])

  const select = useCallback((file: string) => setSelected(file), [])
  return { snapshot, error, selected, select }
}
