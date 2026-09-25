import type { Field } from './types'
import { Pill } from '../ui'


export function refToNodeId(ref: string): string {
  const [path, frag] = ref.replace(/^\//, '').split('#')
  const rel = path.replace(/\.md$/, '')
  return frag ? `${rel}#${frag}` : rel
}

/** An itemized field (acceptance_criteria, business_rules, …) is primary
 * content, not metadata, so callers render it in the wide main column (Jira
 * issue-body style), not the narrow sidebar. It is a full-width table —
 * Key · Status · Criterion — with a humanized section heading and count; the
 * criterion wraps freely now that it has room. Clicking the Key drills down to
 * the item's own view (ItemView), where select-to-chat lives. */
/** "acceptance_criteria" -> "Acceptance Criteria". */
const humanize = (key: string) =>
  key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

function ItemizedField({ field, onFocusItem }: {
  field: Extract<Field, { kind: 'itemized' }>; onFocusItem: (id: string) => void
}) {
  return (
    <div className="fm-field wide" key={field.key}>
      <dt className="itemized-title">{humanize(field.key)} <span className="itemized-count">{field.items.length}</span></dt>
      <dd>
        <div className="fm-itemized">
          <table className="itemized-table">
            <thead>
              <tr><th className="id">Key</th><th className="status">Status</th><th className="crit">Criterion</th></tr>
            </thead>
            <tbody>
              {field.items.map((it) => {
                // Every row in one story's table shares the section prefix
                // (1.1.3.1.1-AC1, -AC2, …); drop it for display so the ID
                // column stays narrow. Full id kept in the tooltip + select ref.
                const shortId = it.id.replace(/^[\d.]+-/, '')
                return (
                <tr key={it.id}>
                  <td className="id">
                    {/* Single click drills down to the item's own view (Jira
                        link behavior); select-to-chat lives on that view. */}
                    <button className="itemized-id" title={it.id} onClick={() => onFocusItem(it.id)}>{shortId}</button>
                  </td>
                  <td className="status">
                    {it.status && <Pill state={it.status === 'active' ? 'ready' : 'neutral'}>{it.status}</Pill>}
                  </td>
                  <td className="crit"><span className="crit-text" title={it.text ?? undefined}>{it.text}</span></td>
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </dd>
    </div>
  )
}

export function FrontmatterFields({ fields, onNavigate, onFocusItem }: {
  fields: Field[]; onNavigate: (nodeId: string) => void; onFocusItem: (id: string) => void
}) {
  return (
    <dl className="fm-fields">
      {fields.map((f) => (
        f.kind === 'itemized' ? (
          <ItemizedField key={f.key} field={f} onFocusItem={onFocusItem} />
        ) : (
          <div className="fm-field" key={f.key}>
            <dt>{f.key}</dt>
            <dd>
              {f.kind === 'link' && (
                <button className="ref-link" onClick={() => onNavigate(refToNodeId(f.ref))}>{f.label}</button>
              )}
              {f.kind === 'links' && f.refs.map((r) => (
                <button className="ref-link" key={r} onClick={() => onNavigate(refToNodeId(r))}>
                  {r.replace(/^\//, '').replace(/\.md.*$/, '').split('/').pop()}
                </button>
              ))}
              {f.kind === 'group' && (
                <FrontmatterFields fields={f.fields} onNavigate={onNavigate} onFocusItem={onFocusItem} />
              )}
              {f.kind === 'value' && <span>{String(f.value)}</span>}
            </dd>
          </div>
        )
      ))}
    </dl>
  )
}
