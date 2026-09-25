import type { DocView, GraphModel } from '../explorer/types'
import { deriveBacklinks } from '../explorer/backlinks'
import { useSelection } from '../select'
import { Pill } from '../ui'
import type { PillState } from '../ui'

/* Drill-down view for a fragment item (AC, business rule, component). These
 * live in the parent story's frontmatter — they have no markdown file of their
 * own — so this view assembles a Jira-style "issue" page for one item from the
 * story doc plus the typed graph: header, criterion text, and every typed link
 * touching the item's graph node (covered by TCs, maps to components, …). */

const BADGES: Record<string, { icon: string; label: string; cls: string }> = {
  AC: { icon: '◆', label: 'Acceptance Criterion', cls: 'ds-ac' },
  BR: { icon: '§', label: 'Business Rule', cls: 'ds-prd' },
  Component: { icon: '🧩', label: 'Component', cls: 'ds-flow' },
}

const pillState = (status: string | null): PillState =>
  status === 'active' || status === 'aligned' ? 'ready'
    : status === 'voided' || status === 'stale' ? 'blocked'
      : 'neutral'

/** "testcases/sit/…/1.1.3.1.1-AC01-01.md" -> "1.1.3.1.1-AC01-01";
 *  "stories/US-VHLD.md#BR-VHLD-01" -> "BR-VHLD-01". */
const shortRef = (ref: string) => {
  const frag = ref.split('#')[1]
  return frag ?? ref.split('/').pop()!.replace(/\.md$/, '')
}

/** A linked row's display text. Fragment refs (a sibling AC/BR/component)
 * resolve to the item's own text inside its parent doc — the doc title would
 * just repeat the story name on every row. File refs keep the doc title. */
const titleFor = (ref: string, fallback: string | null, docs: Record<string, DocView>) => {
  const [file, frag] = ref.split('#')
  if (!frag) return fallback
  const item = docs[file]?.fields
    .flatMap((f) => (f.kind === 'itemized' ? f.items : []))
    .find((it) => it.id === frag)
  return item?.text ?? fallback
}

export function ItemView({ doc, frag, graph, docs, onNavigate }: {
  doc: DocView; frag: string; graph: GraphModel
  docs: Record<string, DocView>; onNavigate: (nodeId: string) => void
}) {
  const nodeId = `${doc.ref}#${frag}`
  const { items, toggle } = useSelection()
  const inChat = items.some((i) => i.ref === nodeId)
  const node = graph.nodes.find((n) => n.id === nodeId) ?? null
  const item = doc.fields
    .flatMap((f) => (f.kind === 'itemized' ? f.items : []))
    .find((it) => it.id === frag) ?? null
  const badge = BADGES[node?.type ?? ''] ?? { icon: '📃', label: node?.type ?? 'Item', cls: 'ds-default' }
  // "part of <story>" is rendered as the parent line, not as a link group
  const groups = deriveBacklinks(graph, nodeId, docs)
    .filter((g) => g.relation !== 'part of')

  return (
    <div className="item-view">
      <div className="doc-header">
        <span className={`doc-type-badge ${badge.cls}`}>
          <span aria-hidden="true">{badge.icon}</span> {badge.label}
        </span>
        <span className="id">{frag}</span>
        {item?.status && <Pill state={pillState(item.status)}>{item.status}</Pill>}
        <button
          className={`btn item-chat${inChat ? ' primary' : ''}`}
          onClick={() => toggle({ ref: nodeId, label: frag, type: node?.type?.toLowerCase() ?? 'item' })}
        >
          {inChat ? '✓ In chat selection' : 'Add to chat'}
        </button>
      </div>
      <p className="item-parent">
        In{' '}
        <button className="ref-link" onClick={() => onNavigate(doc.ref)}>
          {doc.title ?? doc.ref}
        </button>
      </p>
      {(item?.text || node?.label) && (
        <p className="item-text">{item?.text ?? node?.label}</p>
      )}
      <h3 className="itemized-title">Linked items</h3>
      {groups.length === 0 && <p className="section-label">No typed links</p>}
      {groups.map((g) => (
        <div className="link-group" key={g.relation}>
          <div className="link-group-head">
            {g.relation} <span className="itemized-count">{g.entries.length}</span>
          </div>
          <ul className="link-group-list">
            {g.entries.map((e) => (
              <li key={e.ref}>
                <button className="link-item" onClick={() => onNavigate(e.ref)}>
                  <b className="id">{shortRef(e.ref)}</b>
                  {titleFor(e.ref, e.title, docs) && (
                    <span className="link-item-title">{titleFor(e.ref, e.title, docs)}</span>
                  )}
                  {e.status && <Pill state={pillState(e.status)}>{e.status}</Pill>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
