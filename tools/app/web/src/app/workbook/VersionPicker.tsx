import { runDownload } from '../api'
import { Button } from '../ui'
import type { WbVersion, WorkbookEntry } from './types'

function when(iso: string | null): string {
  if (!iso) return 'unknown time'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

// Header controls: which workbook, which compile of it, and Download for the
// file shown. `-latest` is the default compile; timestamped files follow,
// newest first (the server already orders `versions` that way).
export function VersionPicker({ books, kind, name, file, versions, onPick }: {
  books: WorkbookEntry[]
  kind: string
  name: string
  file: string
  versions: WbVersion[]
  onPick: (kind: string, file: string) => void
}) {
  const current = `${kind}/${name}`
  const known = books.some((b) => `${b.kind}/${b.name}` === current)
  return (
    <div className="wb-picker">
      <label>
        Workbook{' '}
        <select value={current} onChange={(e) => {
          const b = books.find((x) => `${x.kind}/${x.name}` === e.target.value)
          if (b) onPick(b.kind, b.file)
        }}>
          {!known && <option value={current}>{name}</option>}
          {books.map((b) => (
            <option key={`${b.kind}/${b.name}`} value={`${b.kind}/${b.name}`}>
              {b.name} ({b.kind.toUpperCase()})
            </option>
          ))}
        </select>
      </label>
      <label>
        Compile{' '}
        <select value={file} onChange={(e) => onPick(kind, e.target.value)}>
          {versions.map((v) => (
            <option key={v.file} value={v.file}>
              {v.file.endsWith('-latest.xlsx') ? `latest - ${when(v.compiled_at)}` : when(v.compiled_at)}
            </option>
          ))}
        </select>
      </label>
      <Button onClick={() => { void runDownload(`${kind}/${file}`) }}>Download</Button>
    </div>
  )
}
