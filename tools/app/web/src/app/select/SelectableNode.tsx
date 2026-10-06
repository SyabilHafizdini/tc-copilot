import { useSelection } from './selection'
import type { SelNode } from './selection'

export function SelectableNode({ node, onActivate, children }: {
  node: SelNode
  onActivate?: () => void
  children: React.ReactNode
}) {
  const { items, toggle, chatEnabled } = useSelection()
  // Chat Off: there is nothing to send a selection to, so the node is a plain
  // row -- it still shows its children, one click (or Enter or Space, as on
  // any button) opens it, and nothing is ever selected.
  if (!chatEnabled) {
    return (
      <div
        className="selectable"
        role="button"
        tabIndex={0}
        onClick={onActivate}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate?.() }
        }}
      >
        {children}
      </div>
    )
  }
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
