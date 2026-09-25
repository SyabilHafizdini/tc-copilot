import { useCallback, useState } from 'react'
import type { DragEvent, ChangeEvent, ReactNode } from 'react'
import { ArrowLeft, UploadCloud } from 'lucide-react'
import type { GraphDocument } from '../lib/types'
import { loadGraphFile } from '../lib/loadGraphFile'

export function DropZone({
  onGraphLoaded,
  onCancel,
}: {
  onGraphLoaded: (graph: GraphDocument, title: string) => void
  onCancel?: () => void
}): ReactNode {
  const [errors, setErrors] = useState<string[]>([])
  const [fileName, setFileName] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)

  const handleFile = useCallback(
    async (file: File) => {
      setFileName(file.name)
      const result = await loadGraphFile(file)
      if (!result.ok) {
        setErrors(result.errors)
        return
      }
      setErrors([])
      onGraphLoaded(result.graph, result.title)
    },
    [onGraphLoaded],
  )

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragActive(false)
      const file = e.dataTransfer.files?.[0]
      if (file) void handleFile(file)
    },
    [handleFile],
  )

  const onInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) void handleFile(file)
      e.target.value = '' // allow re-selecting the same (fixed) file
    },
    [handleFile],
  )

  return (
    <div
      className="flex h-full items-center justify-center bg-zinc-50 p-6"
      onDragOver={(e) => {
        e.preventDefault()
        setDragActive(true)
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={onDrop}
    >
      <div className="w-full max-w-xl">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="mb-3 flex items-center gap-1.5 rounded border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
          >
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Back
          </button>
        )}
        <div
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed bg-white px-8 py-14 text-center transition-colors ${
            dragActive ? 'border-blue-400 bg-blue-50' : 'border-zinc-300'
          }`}
        >
          <UploadCloud className="size-8 text-zinc-400" aria-hidden="true" />
          <h1 className="mt-3 text-sm font-semibold text-zinc-800">
            Drag &amp; drop a graph JSON file
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Expected shape: {'{ "nodes": [...], "edges": [...] }'}
          </p>
          <label className="mt-4 cursor-pointer rounded-md border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100">
            Choose file
            <input
              type="file"
              accept=".json,application/json"
              onChange={onInputChange}
              className="sr-only"
            />
          </label>
        </div>

        {errors.length > 0 && (
          <div
            data-testid="dropzone-errors"
            className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4"
          >
            <p className="text-xs font-semibold text-red-900">
              {fileName ? `${fileName}: ` : ''}
              {errors.length} problem{errors.length !== 1 ? 's' : ''} found
            </p>
            <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">
              {errors.map((e, i) => (
                <li key={i} className="font-mono text-xs text-red-700">
                  {e}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-red-600">
              Fix the file and drop it again – no reload needed.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
