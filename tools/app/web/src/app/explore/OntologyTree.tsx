import { useEffect, useState } from 'react'
import type { KeyboardEvent, MouseEvent, ReactNode } from 'react'
import { ChevronRight, Folder, FolderOpen } from 'lucide-react'
import type { OntologyNode } from './ontology'
import { ancestorIds } from './ontology'

/** Shared VS Code tree metrics — 8px indent per level behind a fixed 16px
 * twisty gutter (see index.css `.tree-*`). */
const INDENT_STEP = 8
const BASE_GUTTER = 16

/** Emoji per graph node type. Group nodes use the lucide folder icon instead. */
const TYPE_ICON: Record<string, string> = {
  Module: '📦', Story: '🎫', AC: '◆', BR: '§', Component: '⬡', TC: '🧪',
  Term: '📖', 'PRD Section': '📄', Flow: '🔀', Resolution: '⚖', 'Figma Page': '🎨',
}

const dotColor = (status: string | null) =>
  status === 'stale' ? 'var(--color-blocked)'
    : status === 'aligned' || status === 'active' || status === 'asserted' ? 'var(--color-ready)'
    : status === 'voided' ? 'var(--color-muted, #9CA3AF)'
    : 'var(--color-muted, #9CA3AF)'

function IndentGuides({ depth }: { depth: number }) {
  if (depth === 0) return null
  const guides: ReactNode[] = []
  for (let level = 0; level < depth; level++) {
    guides.push(
      <span key={level} className="tree-guide" aria-hidden="true"
        style={{ left: level * INDENT_STEP + BASE_GUTTER / 2 }} />,
    )
  }
  return <>{guides}</>
}

/** Renders the logical-ontology forest (Module → Story → AC/BR/Component → TC,
 * plus sibling Sources/Glossary/Flows/Resolutions groups) with the same VS
 * Code Explorer chrome as the filesystem tree. Unlike that tree, a node here
 * can be BOTH expandable and selectable (a Module or Story is a real document
 * that also contains children): the twisty toggles, the icon+label opens the
 * doc. Only the Modules branch and its modules start open. */
export function OntologyTree({ tree, selected, onSelect }: {
  tree: OntologyNode[]; selected: string | null; onSelect: (ref: string) => void
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!selected) return
    setOpen((o) => {
      const next = { ...o }
      let changed = false
      for (const id of ancestorIds(tree, selected)) {
        if (!next[id]) { next[id] = true; changed = true }
      }
      return changed ? next : o
    })
  }, [selected, tree])

  const defaultOpen = (node: OntologyNode) =>
    node.id === 'grp::modules' || node.nodeType === 'Module'
  const isOpen = (node: OntologyNode) => open[node.id] ?? defaultOpen(node)
  const toggle = (node: OntologyNode) =>
    setOpen((o) => ({ ...o, [node.id]: !isOpen(node) }))

  const renderNode = (node: OntologyNode, depth: number): ReactNode => {
    const expandable = node.children.length > 0
    const selectable = node.ref !== null
    const expanded = expandable && isOpen(node)
    const isSelected = node.ref !== null && node.ref === selected
    const isGroup = node.nodeType === 'group'
    const style = { paddingLeft: depth * INDENT_STEP + BASE_GUTTER }

    const twisty = expandable ? (
      <span className="tree-twisty" aria-hidden="true" role="button"
        onClick={(e: MouseEvent) => { e.stopPropagation(); toggle(node) }}
        style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
        <ChevronRight size={10} />
      </span>
    ) : <span className="tree-twisty-spacer" aria-hidden="true" />

    const icon = isGroup
      ? (expanded ? <FolderOpen size={16} className="tree-icon" aria-hidden="true" />
                  : <Folder size={16} className="tree-icon" aria-hidden="true" />)
      : <span className="tree-icon tree-icon-emoji" aria-hidden="true">{TYPE_ICON[node.nodeType] ?? '📃'}</span>

    // A group toggles on any click; a document selects (and its twisty toggles).
    const onRowClick = () => { if (selectable) onSelect(node.ref!); else if (expandable) toggle(node) }
    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'ArrowRight' && expandable && !expanded) { e.preventDefault(); toggle(node) }
      else if (e.key === 'ArrowLeft' && expandable && expanded) { e.preventDefault(); toggle(node) }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick() }
    }

    return (
      <div key={node.id}>
        <div
          className={`tree-item${isGroup ? ' tree-folder' : ''}${isSelected ? ' selected' : ''}`}
          style={style} tabIndex={0} onClick={onRowClick} onKeyDown={onKeyDown}
        >
          <IndentGuides depth={depth} />
          {twisty}
          {icon}
          {!isGroup && node.nodeType !== 'Module' && node.nodeType !== 'Story' && (
            <span className="dot" style={{ background: dotColor(node.status) }} aria-hidden="true" />
          )}
          <span className="tree-label" title={node.label}>{node.label}</span>
          {isGroup && node.count !== null && <span className="ct">{node.count}</span>}
        </div>
        {expanded && node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    )
  }

  return <div className="pane dir-tree">{tree.map((n) => renderNode(n, 0))}</div>
}
