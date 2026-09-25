import { useEffect, useState } from 'react'
import { getExplorer, onChange } from '../api'
import type { ExplorerSnapshot } from '../explorer/types'
import { GlobalGraph } from '../explore/GlobalGraph'
import { hrefFor } from '../shell/routes'
import { PageSkeleton } from '../ui'

/* Traceability (stitch screen 13): the whole-project RTM graph — the
 * PRD Section → Module → Story → AC/BR → Test Case spine — reusing Explore's
 * full-screen graph (force / indented switches and the type legend live
 * inside GlobalGraph). Clicking a node opens it in Explore. */
export function RtmPage() {
  const [snap, setSnap] = useState<ExplorerSnapshot | null>(null)
  useEffect(() => {
    const load = () => getExplorer().then(setSnap).catch(() => setSnap(null))
    load()
    return onChange(load)
  }, [])

  if (!snap) return <PageSkeleton />

  return (
    <div className="page rtm-page">
      <div className="page-head"><h1>Traceability</h1></div>
      <GlobalGraph
        graph={snap.graph}
        onNavigate={(nodeId) => { window.location.hash = hrefFor({ kind: 'explore', path: nodeId }) }}
      />
    </div>
  )
}
