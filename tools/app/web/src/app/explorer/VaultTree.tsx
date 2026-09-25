import { useState } from 'react'
import type { TreeGroup } from './types'
import { SelectableNode } from '../select'

const dotColor = (status: string | null) =>
  status === 'stale' ? 'var(--color-blocked)'
    : status === 'aligned' || status === 'active' ? 'var(--color-ready)'
    : 'var(--color-muted, #9CA3AF)'

export function VaultTree({ tree, selected, onSelect, selectable = false }: {
  tree: TreeGroup[]; selected: string | null; onSelect: (ref: string) => void; selectable?: boolean
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const selectedFile = selected?.split('#')[0]
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
            {isOpen && g.items.map((it) => {
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
            })}
          </div>
        )
      })}
    </div>
  )
}
