import { useSelection } from './selection'
import type { SelNode } from './selection'

export function SelectableNode({ node, onActivate, children }: {
  node: SelNode
  onActivate?: () => void
  children: React.ReactNode
}) {
  const { items, toggle } = useSelection()
  const selected = items.some((i) => i.ref === node.ref)
  return (
    <div
      className={`selectable${selected ? ' selected' : ''}`}
      role="button"
      aria-pressed={selected}
      tabIndex={0}
      onClick={() => toggle(node)}
      onDoubleClick={onActivate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(node) }
      }}
    >
      {children}
    </div>
  )
}
