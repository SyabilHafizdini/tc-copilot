import { useCallback, useEffect, useState } from 'react'
import type { State, SuiteFilters, SuitePreview } from '../api'
import { getSuitePreview, runAction, runDownload } from '../api'
import { hrefFor } from '../shell/routes'
import { Banner, Card, Button, Pill, Spinner, StatTile } from '../ui'
import { useWorkbooks } from '../workbook/useWorkbooks'

const LEVELS = ['sit', 'uat', 'osat', 'mixed']

export function SuitesPage({ state }: { state: State }) {
  const [filters, setFilters] = useState<SuiteFilters>({ kind: 'sit' })
  // One state, so a settled read is a single update: the resolved preview, or
  // the server's own words when it refused the filters.
  const [read, setRead] = useState<{ preview: SuitePreview | null; error: string | null }>(
    { preview: null, error: null })
  const { preview, error: previewError } = read

  useEffect(() => {
    let live = true
    getSuitePreview(filters)
      .then((p) => { if (live) setRead({ preview: p, error: null }) })
      .catch((e: unknown) => {
        if (live) setRead({ preview: null, error: e instanceof Error ? e.message : String(e) })
      })
    return () => { live = false }
  }, [filters])

  const { books, reload } = useWorkbooks()

  // Compile is an allowlisted CLI call; download hits Plan 2's /api/download.
  // A compile writes only under build/, which fires no change event, so the
  // workbook inventory is re-read once the command returns.
  // A refusal (not sealed, an unknown PRD id in the suite) is the command's
  // own words: shown, never swallowed.
  const [refusal, setRefusal] = useState<{ name: string; text: string } | null>(null)
  const compile = useCallback((name: string) => {
    setRefusal(null)
    runAction('suite_compile', { name })
      .then((res) => {
        if ('error' in res) setRefusal({ name, text: res.error })
        else if (res.rc !== 0) setRefusal({ name, text: (res.stdout + res.stderr).trim() || `exit ${res.rc}` })
        reload()
      })
      .catch((e: unknown) => setRefusal({ name, text: e instanceof Error ? e.message : String(e) }))
  }, [reload])
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
        {state.prds.length > 0 && (
          <>
            {' '}
            <label>
              PRD{' '}
              <select value={(filters.include_prds ?? [])[0] ?? ''}
                onChange={(e) => setFilters((f) => ({
                  ...f, include_prds: e.target.value ? [e.target.value] : [],
                }))}>
                <option value="">All</option>
                {state.prds.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </label>
          </>
        )}
        <div className="suite-preview">
          {preview
            ? <StatTile n={preview.count} label="test cases resolved"
                sub={`${preview.stale} stale · ${preview.retired} retired`} />
            : previewError
              ? <span role="alert" className="muted">{previewError}</span>
              : <span className="muted loading-inline"><Spinner size={14} /> Resolving selection…</span>}
        </div>
        <p className="muted">
          To save this selection as a named suite, ask the agent for
          the <code>tc-suite-author</code> skill. The app compiles authored suites and never
          writes selection YAML itself.
        </p>
      </Card>

      <Card>
        <p className="section-label">Existing suites</p>
        {refusal && (
          <Banner tone="blocked" onDismiss={() => setRefusal(null)}>
            <span>Compile {refusal.name} did not go through:</span>
            <pre className="wb-refusal">{refusal.text}</pre>
          </Banner>
        )}
        {state.suites.length === 0 && <p className="muted">No suites yet.</p>}
        {state.suites.map((name) => {
          // The suite's compiled workbook, when it has one.
          const book = (books ?? []).find((b) => b.name === name)
          return (
            <div key={name} className="suite-row">
              <span>{name}</span>
              {book?.freshness === 'changed' && (
                <Pill state="attn">{book.changed_count} changed</Pill>
              )}
              {book && (
                <a className="row-link" aria-label={`Open ${name}`}
                  href={hrefFor({ kind: 'workbook', wbKind: book.kind, file: book.file })}>Open</a>
              )}
              <Button onClick={() => compile(name)}>Compile</Button>
            </div>
          )
        })}
      </Card>

      <Card>
        <p className="section-label">Compiled workbooks</p>
        {(state.inventory ?? []).length === 0 && <p className="muted">Nothing compiled yet.</p>}
        {(state.inventory ?? []).map((row) => (
          <div key={row.file} className="inventory-row">
            <Pill state="neutral">{row.kind.toUpperCase()}</Pill>
            <span>{row.file}</span>
            <a className="row-link" aria-label={`Open ${row.file}`}
              href={hrefFor({ kind: 'workbook', wbKind: row.kind, file: row.file.split('/').pop()! })}>Open</a>
            <Button onClick={() => download(row.file)}>Download ↓</Button>
          </div>
        ))}
      </Card>
    </div>
  )
}
