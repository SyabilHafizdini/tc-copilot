import type { Prd } from '../api'
import { Pill } from '../ui'

/* What stands where PRD state would be on a project that is not migrated to
 * the PRD registry yet: its list is empty whatever was adopted or staged, so
 * "none" would be a false statement. */
export const NOT_MIGRATED = 'PRD state is not shown until the project is migrated.'

/* The one PRD table. A product is described by several PRDs, each with its
 * own version line; Settings and the dashboard both show this list. */
export function PrdList({ prds, schema1 = false }: { prds: Prd[]; schema1?: boolean }) {
  if (schema1) return <p className="empty">{NOT_MIGRATED}</p>
  if (prds.length === 0) return <p className="empty">No PRD registered.</p>
  return (
    <table>
      <thead><tr><th>PRD</th><th>Title</th><th>Adopted</th><th>Staged</th></tr></thead>
      <tbody>
        {prds.map((p) => (
          <tr key={p.id}>
            <td><span className="id">{p.id}</span></td>
            <td>{p.title}</td>
            <td>
              {p.adopted === null
                ? <span className="muted">not adopted</span>
                : <Pill state="ready">v{p.adopted}</Pill>}
            </td>
            <td>
              {p.staged === null
                ? <span className="muted">none staged</span>
                : <Pill state="attn">v{p.staged} staged</Pill>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
