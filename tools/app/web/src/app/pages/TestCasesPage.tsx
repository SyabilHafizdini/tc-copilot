import { useEffect, useMemo, useState } from 'react'
import { getExplorer, onChange } from '../api'
import type { ExplorerSnapshot } from '../explorer/types'
import { levelOf, type TcLevel } from '../story/testcases'
import { hrefFor } from '../shell/routes'
import { PageSkeleton, Pill, type PillState } from '../ui'

type Row = {
  ref: string; id: string; title: string | null
  level: TcLevel; story: string | null; status: string | null
}

const statusPill = (status: string | null): PillState =>
  status === 'active' ? 'ready'
    : status === 'stale' ? 'attn'
      : status === 'retired' || status === 'voided' ? 'blocked'
        : 'neutral'

function rows(snap: ExplorerSnapshot): Row[] {
  return Object.values(snap.docs)
    .map((d) => {
      const level = levelOf(d.ref)
      if (!level) return null
      return {
        ref: d.ref,
        id: d.ref.split('/').pop()!.replace(/\.md$/, ''),
        title: d.title,
        level,
        story: d.facets.story ? d.facets.story.split('/').pop()!.replace(/\.md$/, '') : null,
        status: d.status,
      }
    })
    .filter((r): r is Row => r !== null)
    .sort((a, b) => a.id.localeCompare(b.id))
}

/* Project-wide test case inventory (stitch screen 8): every generated TC
 * across SIT / UAT / OSAT with a level filter. Keys open the document in
 * Explore; the story column jumps to the issue view. */
export function TestCasesPage() {
  const [snap, setSnap] = useState<ExplorerSnapshot | null>(null)
  const [level, setLevel] = useState<TcLevel | null>(null)
  useEffect(() => {
    const load = () => getExplorer().then(setSnap).catch(() => setSnap(null))
    load()
    return onChange(load)
  }, [])

  const all = useMemo(() => (snap ? rows(snap) : []), [snap])
  const shown = level ? all.filter((r) => r.level === level) : all
  const counts = useMemo(() => {
    const c: Record<TcLevel, number> = { sit: 0, uat: 0, osat: 0 }
    for (const r of all) c[r.level] += 1
    return c
  }, [all])

  if (!snap) return <PageSkeleton />

  return (
    <div className="page">
      <div className="page-head">
        <h1>Test Cases</h1>
        <div className="level-filter">
          <button className={`chip${level === null ? ' on' : ''}`} onClick={() => setLevel(null)}>
            All {all.length}
          </button>
          {(['sit', 'uat', 'osat'] as const).map((l) => (
            <button key={l} className={`chip${level === l ? ' on' : ''}`} onClick={() => setLevel(level === l ? null : l)}>
              {l.toUpperCase()} {counts[l]}
            </button>
          ))}
        </div>
      </div>
      <div className="card">
        <table>
          <thead>
            <tr><th>Key</th><th>Title</th><th>Level</th><th>Story</th><th>Status</th></tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.ref}>
                <td><a className="id row-link" href={hrefFor({ kind: 'explore', path: r.ref })}>{r.id}</a></td>
                <td>{r.title ?? '—'}</td>
                <td><span className="level-tag">{r.level.toUpperCase()}</span></td>
                <td>
                  {r.story
                    ? <a className="id row-link" href={hrefFor({ kind: 'story', id: r.story })}>{r.story}</a>
                    : '—'}
                </td>
                <td>{r.status && <Pill state={statusPill(r.status)}>{r.status}</Pill>}</td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={5}><p className="empty">No test cases at this level yet.</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
