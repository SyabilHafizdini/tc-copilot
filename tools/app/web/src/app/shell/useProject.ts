import { useCallback, useEffect, useState } from 'react'
import { getProjects, type ProjectCard } from '../api'
import { hrefFor } from './routes'

// `switch` is a reserved word, so the local is named switchTo and exposed under
// the `switch` property (a legal object member name) per the registry signature.
export function useProject(): { id: string; switch(id: string): void; all: ProjectCard[]; loading: boolean } {
  const [all, setAll] = useState<ProjectCard[]>([])
  const [id, setId] = useState('')
  // Distinguishes "portfolio still fetching" from "genuinely no projects" so
  // the Projects page can show a skeleton instead of a false empty state.
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProjects()
      .then((ps) => {
        setAll(ps)
        setId((cur) => cur || (ps[0]?.id ?? ''))
      })
      .catch(() => { /* portfolio degrades to empty; App shows its error banner */ })
      .finally(() => setLoading(false))
  }, [])

  const switchTo = useCallback((next: string) => {
    setId(next)
    // Land in Explore (the file-directory) — the approved primary surface —
    // not the Dashboard, whenever a project is selected/opened.
    window.location.hash = hrefFor({ kind: 'explore' })
  }, [])

  return { id, switch: switchTo, all, loading }
}
