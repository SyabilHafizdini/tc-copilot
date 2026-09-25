import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import type { GraphDocument } from '../lib/types'
import { loadGraphFile } from '../lib/loadGraphFile'

interface DropError {
  fileName: string
  errors: string[]
}

/** Window-level drop target: any file dropped on the page opens as a new
 * tab (valid) or surfaces a dismissible error panel (invalid). Must be
 * rendered inside a position:relative container. */
export function GlobalDropOverlay({
  onGraphLoaded,
}: {
  onGraphLoaded: (graph: GraphDocument, title: string) => void
}): ReactNode {
  const [dragActive, setDragActive] = useState(false)
  const [dropError, setDropError] = useState<DropError | null>(null)

  const handleFile = useCallback(
    async (file: File) => {
      const result = await loadGraphFile(file)
      if (result.ok) {
        setDropError(null)
        onGraphLoaded(result.graph, result.title)
      } else {
        setDropError({ fileName: file.name, errors: result.errors })
      }
    },
    [onGraphLoaded],
  )

  useEffect(() => {
    const isFileDrag = (e: DragEvent) => e.dataTransfer?.types.includes('Files') ?? false
    const onDragOver = (e: DragEvent) => {
      if (!isFileDrag(e)) return
      e.preventDefault()
      setDragActive(true)
    }
    const onDragLeave = (e: DragEvent) => {
      // relatedTarget is null when the drag leaves the window entirely
      if (e.relatedTarget == null) setDragActive(false)
    }
    const onDrop = (e: DragEvent) => {
      if (!isFileDrag(e)) return
      e.preventDefault()
      setDragActive(false)
      const file = e.dataTransfer?.files?.[0]
      if (file) void handleFile(file)
    }
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
  }, [handleFile])

  return (
    <>
      {dragActive && (
        <div
          data-testid="global-drop-highlight"
          className="pointer-events-none absolute inset-0 z-30 border-4 border-dashed border-blue-400 bg-blue-50/60"
        >
          <div className="flex h-full items-center justify-center">
            <p className="rounded bg-white/90 px-4 py-2 text-sm font-medium text-blue-700 shadow">
              Drop to open in a new tab
            </p>
          </div>
        </div>
      )}
      {dropError && (
        <div
          data-testid="global-drop-errors"
          className="absolute left-1/2 top-6 z-30 w-full max-w-xl -translate-x-1/2 rounded-lg border border-red-200 bg-red-50 p-4 shadow-lg"
        >
          <div className="flex items-start justify-between">
            <p className="text-xs font-semibold text-red-900">
              {dropError.fileName}: {dropError.errors.length} problem
              {dropError.errors.length !== 1 ? 's' : ''} found
            </p>
            <button
              type="button"
              aria-label="Dismiss errors"
              onClick={() => setDropError(null)}
              className="-mr-1 -mt-1 rounded p-1 text-red-700 hover:bg-red-100"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
          <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">
            {dropError.errors.map((e, i) => (
              <li key={i} className="font-mono text-xs text-red-700">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
