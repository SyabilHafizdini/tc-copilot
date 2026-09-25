import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { GraphDocument } from './lib/types'
// @ts-ignore - plain JS module shared with the CLI
import { validateGraph, normalizeGraph } from './lib/validate.mjs'
import Viewer from './Viewer'
import { DropZone } from './components/DropZone'
import { TabBar, type GraphTab } from './components/TabBar'
import { GlobalDropOverlay } from './components/GlobalDropOverlay'

declare global {
  interface Window {
    __GRAPH_DATA__?: unknown
  }
}

interface OpenTab extends GraphTab {
  graph: GraphDocument
}

interface TabState {
  tabs: OpenTab[]
  activeTabId: string | null
}

export default function App(): ReactNode {
  const baked = window.__GRAPH_DATA__
  const bakedErrors = useMemo(
    () => (baked !== undefined ? (validateGraph(baked) as string[]) : null),
    [baked],
  )

  const [state, setState] = useState<TabState>(() => {
    if (baked === undefined || (bakedErrors && bakedErrors.length > 0)) {
      return { tabs: [], activeTabId: null }
    }
    const graph = normalizeGraph(baked) as GraphDocument
    return {
      tabs: [{ id: 'tab-1', title: graph.meta?.title ?? 'Graph 1', graph }],
      activeTabId: 'tab-1',
    }
  })
  // ids/titles count up monotonically; never reused after closes
  const nextIdRef = useRef(2)
  const [adding, setAdding] = useState(false)

  const addTab = useCallback((graph: GraphDocument, title: string) => {
    const n = nextIdRef.current
    nextIdRef.current += 1
    const id = `tab-${n}`
    setState((s) => ({
      tabs: [...s.tabs, { id, title: title || `Graph ${n}`, graph }],
      activeTabId: id,
    }))
    setAdding(false)
  }, [])

  const closeTab = useCallback((id: string) => {
    setState((s) => {
      const idx = s.tabs.findIndex((t) => t.id === id)
      const tabs = s.tabs.filter((t) => t.id !== id)
      let activeTabId = s.activeTabId
      if (activeTabId === id) {
        activeTabId = tabs.length > 0 ? tabs[Math.max(0, idx - 1)].id : null
      }
      return { tabs, activeTabId }
    })
  }, [])

  const selectTab = useCallback((id: string) => {
    setAdding(false)
    setState((s) => ({ ...s, activeTabId: id }))
  }, [])

  // Never let a stray drag navigate the page away - that would silently
  // destroy every open tab. Drop handling itself lives in DropZone /
  // GlobalDropOverlay; this only cancels the browser default.
  useEffect(() => {
    const prevent = (e: DragEvent) => e.preventDefault()
    window.addEventListener('dragover', prevent)
    window.addEventListener('drop', prevent)
    return () => {
      window.removeEventListener('dragover', prevent)
      window.removeEventListener('drop', prevent)
    }
  }, [])

  if (bakedErrors && bakedErrors.length > 0) {
    return <BakedErrorScreen errors={bakedErrors} />
  }

  const { tabs, activeTabId } = state
  const showDropScreen = tabs.length === 0 || adding

  return (
    <div className="flex h-screen flex-col">
      {tabs.length > 0 && (
        <TabBar
          tabs={tabs}
          activeTabId={activeTabId}
          onSelect={selectTab}
          onClose={closeTab}
          onAdd={() => setAdding(true)}
        />
      )}
      <div className="relative min-h-0 flex-1">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className="h-full"
            style={{ display: tab.id === activeTabId && !adding ? undefined : 'none' }}
          >
            <Viewer graph={tab.graph} />
          </div>
        ))}
        {showDropScreen && (
          <div className="absolute inset-0 z-20 bg-white">
            <DropZone
              onGraphLoaded={addTab}
              onCancel={tabs.length > 0 ? () => setAdding(false) : undefined}
            />
          </div>
        )}
        {tabs.length > 0 && !adding && <GlobalDropOverlay onGraphLoaded={addTab} />}
      </div>
    </div>
  )
}

function BakedErrorScreen({ errors }: { errors: string[] }): ReactNode {
  return (
    <div className="flex h-screen items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-lg border border-red-200 bg-red-50 p-6">
        <h1 className="text-sm font-semibold text-red-900">Baked graph data is invalid</h1>
        <ul className="mt-3 space-y-1">
          {errors.map((e, i) => (
            <li key={i} className="font-mono text-xs text-red-700">
              {e}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
