import { useEffect, useMemo, useState } from 'react'
import { getExplorer, onChange } from '../api'
import type { DocView, ExplorerSnapshot, Field } from '../explorer/types'
import { hrefFor } from '../shell/routes'
import { PageSkeleton, Pill } from '../ui'

type Entry = { ref: string; id: string; title: string | null; by: string; at: string; status: string | null }

function fieldValue(fields: Field[], key: string): string | null {
  const f = fields.find((x) => x.key === key)
  return f && f.kind === 'value' ? String(f.value) : null
}

/* Every resolution is an asserted, timestamped decision — the project's audit
 * trail. Newest first, like a Jira activity feed. */
function entries(snap: ExplorerSnapshot): Entry[] {
  return Object.values(snap.docs)
    .filter((d: DocView) => d.ref.startsWith('resolutions/'))
    .map((d) => ({
      ref: d.ref,
      id: d.ref.split('/').pop()!.replace(/\.md$/, ''),
      title: d.title,
      by: fieldValue(d.fields, 'asserted_by') ?? 'unknown',
      at: fieldValue(d.fields, 'asserted_at') ?? '',
      status: d.status,
    }))
    .sort((a, b) => b.at.localeCompare(a.at))
}

const fmtDate = (iso: string) => (iso ? iso.replace('T', ' ').replace(/[+Z].*$/, '').slice(0, 16) : '—')

export function ActivityPage() {
  const [snap, setSnap] = useState<ExplorerSnapshot | null>(null)
  useEffect(() => {
    const load = () => getExplorer().then(setSnap).catch(() => setSnap(null))
    load()
    return onChange(load)
  }, [])
  const feed = useMemo(() => (snap ? entries(snap) : []), [snap])

  if (!snap) return <PageSkeleton />

  return (
    <div className="page">
      <div className="page-head"><h1>Activity</h1></div>
      <div className="card activity-feed">
        {feed.length === 0 && <p className="empty">No asserted resolutions yet.</p>}
        {feed.map((e) => (
          <div className="activity-row" key={e.ref}>
            <span className="av">{e.by.slice(0, 2).toUpperCase()}</span>
            <div className="activity-text">
              <p>
                <b>{e.by}</b> asserted{' '}
                <a className="id row-link" href={hrefFor({ kind: 'explore', path: e.ref })}>{e.id}</a>
                {e.status === 'superseded' && <> <Pill state="neutral">superseded</Pill></>}
              </p>
              {e.title && <p className="activity-title">{e.title.replace(/^R-[\w-]+:\s*/, '')}</p>}
            </div>
            <span className="activity-when">{fmtDate(e.at)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
