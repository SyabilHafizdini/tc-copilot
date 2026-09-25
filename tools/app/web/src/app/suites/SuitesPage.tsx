import { useCallback, useEffect, useState } from 'react'
import type { State, SuiteFilters, SuitePreview } from '../api'
import { getSuitePreview, runAction, runDownload } from '../api'
import { Card, Button, Pill, Spinner, StatTile } from '../ui'

const LEVELS = ['sit', 'uat', 'osat', 'mixed']

export function SuitesPage({ state }: { state: State }) {
  const [filters, setFilters] = useState<SuiteFilters>({ kind: 'sit' })
  const [preview, setPreview] = useState<SuitePreview | null>(null)

  useEffect(() => {
    let live = true
    getSuitePreview(filters)
      .then((p) => { if (live) setPreview(p) })
      .catch(() => { if (live) setPreview(null) })
    return () => { live = false }
  }, [filters])

  // Compile is an allowlisted CLI call; download hits Plan 2's /api/download.
  const compile = useCallback((name: string) => { void runAction('suite_compile', { name }) }, [])
  const download = useCallback((file: string) => { void runDownload(file, {}) }, [])

  return (
    <div className="page suites-page">
      <div className="page-head"><h1>Suites &amp; Export</h1></div>
      <p className="page-sub">
        A suite <b>selects</b> already-generated test cases — selection is never generation.
      </p>

      <Card>
        <p className="section-label">Builder</p>
        <label>
          Level{' '}
          <select value={filters.kind}
            onChange={(e) => setFilters((f) => ({ ...f, kind: e.target.value }))}>
            {LEVELS.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
          </select>
        </label>{' '}
        <label>
          Priority{' '}
          <select value={(filters.priorities ?? [])[0] ?? ''}
            onChange={(e) => setFilters((f) => ({
              ...f, priorities: e.target.value ? [e.target.value] : [],
            }))}>
            <option value="">All</option>
            {['P1', 'P2', 'P3'].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <div className="suite-preview">
          {preview
            ? <StatTile n={preview.count} label="test cases resolved"
                sub={`${preview.stale} stale · ${preview.retired} retired`} />
            : <span className="muted loading-inline"><Spinner size={14} /> Resolving selection…</span>}
        </div>
        <p className="muted">
          To save this selection as a named suite, run the <code>tc-suite-author</code> skill
          in chat — the app compiles authored suites and never writes selection YAML itself.
        </p>
      </Card>

      <Card>
        <p className="section-label">Existing suites</p>
        {state.suites.length === 0 && <p className="muted">No suites yet.</p>}
        {state.suites.map((name) => (
          <div key={name} className="suite-row">
            <span>{name}</span>
            <Button onClick={() => compile(name)}>Compile</Button>
          </div>
        ))}
      </Card>

      <Card>
        <p className="section-label">Compiled workbooks</p>
        {(state.inventory ?? []).length === 0 && <p className="muted">Nothing compiled yet.</p>}
        {(state.inventory ?? []).map((row) => (
          <div key={row.file} className="inventory-row">
            <Pill state="neutral">{row.kind.toUpperCase()}</Pill>
            <span>{row.file}</span>
            <Button onClick={() => download(row.file)}>Download ↓</Button>
          </div>
        ))}
      </Card>
    </div>
  )
}
