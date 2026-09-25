import { Button } from '../ui/Button'
import { Pill } from '../ui/Pill'
import { runDownload } from '../api'
import type { InventoryItem } from '../api'

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
          <Button onClick={() => { void runDownload(it.file) }}>Download</Button>
        </li>
      ))}
    </ul>
  )
}
