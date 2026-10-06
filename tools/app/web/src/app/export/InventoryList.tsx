import { Button } from '../ui/Button'
import { Pill } from '../ui/Pill'
import { runDownload } from '../api'
import type { InventoryItem } from '../api'
import { hrefFor } from '../shell/routes'

export function InventoryList({ items }: { items: InventoryItem[] }) {
  if (items.length === 0) {
    return <p className="muted">No workbooks yet — export a ready story.</p>
  }
  return (
    <ul className="inventory-list">
      {items.map((it) => (
        <li key={it.file}>
          <Pill state="neutral">{it.kind.toUpperCase()}</Pill>
          <span className="inv-story">{it.story ?? '—'}</span>
          <time dateTime={it.mtime}>{it.mtime}</time>
          <a className="row-link" href={hrefFor({
            kind: 'workbook', wbKind: it.kind, file: it.file.split('/').pop()!,
          })}>Open</a>
          <Button onClick={() => { void runDownload(it.file) }}>Download</Button>
        </li>
      ))}
    </ul>
  )
}
