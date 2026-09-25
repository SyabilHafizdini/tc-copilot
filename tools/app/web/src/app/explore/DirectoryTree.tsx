import { useEffect, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { ChevronRight, Folder, FolderOpen } from 'lucide-react'
import type { FileNode } from './fileTree'
import type { DocView } from '../explorer/types'
import { docTypeMeta } from './docType'
import { SelectableNode } from '../select'

const dotColor = (status: string | null) =>
  status === 'stale' ? 'var(--color-blocked)'
    : status === 'aligned' || status === 'active' ? 'var(--color-ready)'
    : 'var(--color-muted, #9CA3AF)'

/** VS Code tree metrics (`tree.indent` = 8px per level, plus a fixed 16px
 * "twisty gutter" every row reserves for the expand arrow — files render an
 * empty spacer there so file labels line up under folder labels). */
const INDENT_STEP = 8
const BASE_GUTTER = 16

/** Every proper-ancestor folder path of a file ref, shallowest first —
 * "a/b/c" -> ["a", "a/b"]. Used to auto-expand the selected file's folders. */
function ancestorPaths(ref: string): string[] {
  const segments = ref.split('/')
  const paths: string[] = []
  for (let i = 1; i < segments.length; i++) paths.push(segments.slice(0, i).join('/'))
  return paths
}

/** Faint 1px vertical indent guides, one per ancestor level, aligned under
 * each ancestor row's twisty column (VS Code `tree.indentGuidesStroke`). */
function IndentGuides({ depth }: { depth: number }) {
  if (depth === 0) return null
  const guides: ReactNode[] = []
  for (let level = 0; level < depth; level++) {
    guides.push(
      <span
        key={level}
        className="tree-guide"
        aria-hidden="true"
        style={{ left: level * INDENT_STEP + BASE_GUTTER / 2 }}
      />,
    )
  }
  return <>{guides}</>
}

/** Renders the real doc-ref filesystem as a navigable folder/file tree,
 * restyled to VS Code Explorer conventions: 22px rows, 8px-per-level indent
 * behind a fixed 16px twisty gutter, faint indent guides, full-row hover and
 * selection tinting (no left accent bar), and a lucide chevron/folder icon
 * pair. Files keep the meaningful document-type icon plus a subtle status
 * dot. Folders are never selectable — only file leaves can be wrapped in
 * SelectableNode when `selectable` is set.
 *
 * Default open/closed: top-level folders (flows/glossary/modules/...) start
 * open, as in the mockup, so a document is reachable in one glance; folders
 * nested deeper start closed to avoid dumping the whole vault, except that
 * every ancestor of the currently-selected file is forced open so the
 * selection stays visible. */
export function DirectoryTree({ tree, docs, selected, onSelect, selectable = false }: {
  tree: FileNode[]; docs: Record<string, DocView>; selected: string | null
  onSelect: (ref: string) => void; selectable?: boolean
}) {
  const selectedFile = selected?.split('#')[0] ?? null
  const [open, setOpen] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!selectedFile) return
    setOpen((o) => {
      const next = { ...o }
      let changed = false
      for (const p of ancestorPaths(selectedFile)) {
        if (!next[p]) { next[p] = true; changed = true }
      }
      return changed ? next : o
    })
  }, [selectedFile])

  const isOpen = (path: string, depth: number) => open[path] ?? depth === 0
  const toggle = (path: string, depth: number) =>
    setOpen((o) => ({ ...o, [path]: !isOpen(path, depth) }))

  const renderFolder = (node: Extract<FileNode, { kind: 'folder' }>, depth: number): ReactNode => {
    const expanded = isOpen(node.path, depth)
    const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'ArrowRight' && !expanded) { e.preventDefault(); toggle(node.path, depth) }
      else if (e.key === 'ArrowLeft' && expanded) { e.preventDefault(); toggle(node.path, depth) }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(node.path, depth) }
    }
    return (
      <div key={node.path}>
        <div
          className="tree-item tree-folder"
          style={{ paddingLeft: depth * INDENT_STEP + BASE_GUTTER }}
          onClick={() => toggle(node.path, depth)}
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          <IndentGuides depth={depth} />
          <span
            className="tree-twisty"
            aria-hidden="true"
            style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
          >
            <ChevronRight size={10} />
          </span>
          {expanded
            ? <FolderOpen size={16} className="tree-icon" aria-hidden="true" />
            : <Folder size={16} className="tree-icon" aria-hidden="true" />}
          <span className="tree-label" title={node.name}>{node.name}</span>
        </div>
        {expanded && node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    )
  }

  const renderFile = (node: Extract<FileNode, { kind: 'file' }>, depth: number): ReactNode => {
    const doc = docs[node.ref]
    const meta = docTypeMeta(doc?.type ?? doc?.kind ?? '')
    const title = doc?.title ?? node.name
    const status = doc?.status ?? null
    const isSelected = node.ref === selectedFile
    const style = { paddingLeft: depth * INDENT_STEP + BASE_GUTTER }
    const rest = (
      <>
        <span className="tree-twisty-spacer" aria-hidden="true" />
        <span className="tree-icon tree-icon-emoji" aria-hidden="true">{meta.icon}</span>
        <span className="dot" style={{ background: dotColor(status) }} aria-hidden="true" />
        <span className="tree-label" title={title}>{title}</span>
      </>
    )

    if (selectable) {
      return (
        <div key={node.ref} className={`tree-item${isSelected ? ' selected' : ''}`} style={style}>
          <IndentGuides depth={depth} />
          <SelectableNode
            node={{ ref: node.ref, label: title, type: 'file' }}
            onActivate={() => onSelect(node.ref)}>
            {rest}
          </SelectableNode>
        </div>
      )
    }
    const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter') { e.preventDefault(); onSelect(node.ref) }
    }
    return (
      <div
        key={node.ref}
        className={`tree-item${isSelected ? ' selected' : ''}`}
        style={style}
        onClick={() => onSelect(node.ref)}
        tabIndex={0}
        onKeyDown={handleKeyDown}
      >
        <IndentGuides depth={depth} />
        {rest}
      </div>
    )
  }

  const renderNode = (node: FileNode, depth: number): ReactNode =>
    node.kind === 'folder' ? renderFolder(node, depth) : renderFile(node, depth)

  return <div className="pane dir-tree">{tree.map((n) => renderNode(n, 0))}</div>
}
