import { useState } from 'react'
import type { TreeGroup } from './types'
import { SelectableNode } from '../select'

type Item = TreeGroup['items'][number]

const dotColor = (status: string | null) =>
  status === 'stale' ? 'var(--color-blocked)'
    : status === 'aligned' || status === 'active' ? 'var(--color-ready)'
    : 'var(--color-muted, #9CA3AF)'

/** Items in tree order, bucketed by PRD: the items that belong to no PRD
 * first (one unnamed bucket), then one bucket per PRD in first-appearance
 * order. A group with no PRD items is a single unnamed bucket. */
export function bucketByPrd(items: Item[]): Array<[string | null, Item[]]> {
  const out: Array<[string | null, Item[]]> = []
  const at = new Map<string | null, Item[]>()
  for (const it of items) {
    const key = it.prd ?? null
    let bucket = at.get(key)
    if (!bucket) {
      bucket = []
      at.set(key, bucket)
      out.push([key, bucket])
    }
    bucket.push(it)
  }
  return out.sort((a, b) => (a[0] === null ? -1 : b[0] === null ? 1 : 0))
}

export function VaultTree({ tree, selected, onSelect, selectable = false, subLabels = {} }: {
  tree: TreeGroup[]; selected: string | null; onSelect: (ref: string) => void
  selectable?: boolean
  /** Display names for PRD sub-headings, keyed by PRD id. Falls back to the id. */
  subLabels?: Record<string, string>
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const selectedFile = selected?.split('#')[0]

  const renderItem = (it: Item) => {
    const body = (
      <>
        <span className="dot" style={{ background: dotColor(it.status) }} />
        {it.title ?? it.ref.split('/').pop()}
      </>
    )
    if (selectable) {
      return (
        <div key={it.ref} className={`tree-item${it.ref === selectedFile ? ' selected' : ''}`}>
          <SelectableNode
            node={{ ref: it.ref, label: it.title ?? it.ref.split('/').pop() ?? it.ref, type: 'file' }}
            onActivate={() => onSelect(it.ref)}>
            {body}
          </SelectableNode>
        </div>
      )
    }
    return (
      <div key={it.ref}
        className={`tree-item${it.ref === selectedFile ? ' selected' : ''}`}
        onClick={() => onSelect(it.ref)} style={{ cursor: 'pointer' }}>
        {body}
      </div>
    )
  }

  return (
    <div className="pane">
      {tree.map((g) => {
        const isOpen = open[g.kind] ?? true
        return (
          <div key={g.kind}>
            <h4 onClick={() => setOpen((o) => ({ ...o, [g.kind]: !isOpen }))} style={{ cursor: 'pointer' }}>
              <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span> <span>{g.label}</span>
              <span className="ct">{g.count}</span>
            </h4>
            {isOpen && bucketByPrd(g.items).map(([prd, items]) => (
              <div key={prd ?? ''}>
                {prd !== null && <p className="section-label tree-sub">{subLabels[prd] ?? prd}</p>}
                {items.map(renderItem)}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
