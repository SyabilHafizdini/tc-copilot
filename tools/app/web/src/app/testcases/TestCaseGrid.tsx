import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { EMPTY_FILTERS, applyFilters, parseFilters, readHashQuery, serializeFilters, writeHashQuery } from './filters'
import type { TcFilters } from './filters'
import { ConfidenceTag, ReviewPanel } from './ReviewPanel'
import { PrdChips } from './PrdChips'
import { prdOptions, togglePrd } from './prdFilter'
import { getState, getWorkbooks } from '../api'
import { confirmDiscard, useUnsavedDraft } from '../shell/unsaved'
import { workbookHrefFor } from '../workbook/links'
import type { WorkbookEntry } from '../workbook/types'
import { RichText } from './richText'
import type { ConfidenceLevel, TcGroup, TcLevel, TcRow, TestCasesPayload } from './types'

export type { TcFilters } from './filters'

const COLUMNS = ['ID', 'Scenario', 'Test Steps', 'Field / Values', 'Expected Results', 'Confidence', 'Remarks']
const CONFIDENCE: ConfidenceLevel[] = ['High', 'Medium', 'Low']
const GROUP_WORD = { run: 'Run', flow: 'Flow', module: 'Module' } as const

/* The workbook's C-TC sheet as a grid: the same columns, grouped per run (or
 * per flow / module when a test case has no run), with a `Section:` row where
 * the section changes. A row opens the review panel docked on the right.
 *
 * Filters live in the URL hash query so a filtered view can be linked -
 * except under `lockStory`, where the grid is embedded in a story page that
 * owns the hash. */
export function TestCaseGrid({ payload, initialFilters, lockStory }: {
  payload: TestCasesPayload
  initialFilters?: Partial<TcFilters>
  lockStory?: string
}) {
  const scope = useMemo(
    () => (lockStory ? payload.rows.filter((r) => r.story === lockStory) : payload.rows),
    [payload.rows, lockStory])
  // Options come from every row in scope, not the filtered ones, so a chip
  // does not vanish when another filter hides its rows. A selected id that no
  // row draws on any more (the payload reloaded) is not applied.
  const prdIds = useMemo(() => prdOptions(scope), [scope])

  const [filters, setFilters] = useState<TcFilters>(() => {
    const f = {
      ...(lockStory ? EMPTY_FILTERS : parseFilters(readHashQuery())),
      ...initialFilters,
      ...(lockStory ? { story: lockStory } : {}),
    }
    // A PRD id no row draws on (a stale link, a typed hash) is dropped.
    return { ...f, prds: f.prds.filter((id) => prdIds.includes(id)) }
  })
  const [selected, setSelected] = useState<string | null>(null)
  useEffect(() => {
    if (!lockStory) writeHashQuery(serializeFilters(filters))
  }, [filters, lockStory])
  // A link to another filtered view of this page (`#/testcases?level=sit`),
  // followed while the grid is already on screen, changes only the query:
  // read it again. The grid's own writes use replaceState and fire nothing.
  const known = useRef(prdIds)
  known.current = prdIds
  useEffect(() => {
    if (lockStory) return
    const onHash = () => {
      // Leaving the page is the router's business; the grid is about to go.
      if (!/^#\/?testcases(?:\?|$)/.test(window.location.hash)) return
      const f = parseFilters(readHashQuery())
      setFilters({ ...f, prds: f.prds.filter((id) => known.current.includes(id)) })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [lockStory])

  const set = (patch: Partial<TcFilters>) => setFilters((f) => ({ ...f, ...patch }))

  const selectedPrds = useMemo(
    () => filters.prds.filter((id) => prdIds.includes(id)), [filters.prds, prdIds])
  // While the open row holds unsaved text it stays in the grid whatever the
  // filters say, so a chip or a select cannot unmount its editor.
  const unsaved = useUnsavedDraft()
  const visible = useMemo(() => {
    const pass = new Set(applyFilters(scope, { ...filters, prds: selectedPrds }))
    return scope.filter((r) => pass.has(r) || (unsaved && r.id === selected))
  }, [scope, filters, selectedPrds, unsaved, selected])

  // PRD titles for the chips, read once when there is a PRD to label. A
  // failed read leaves the ids as labels.
  const [prdTitles, setPrdTitles] = useState<Record<string, string>>({})
  const hasPrds = prdIds.length > 0
  useEffect(() => {
    if (!hasPrds) return
    let live = true
    getState().then((s) => {
      if (live) setPrdTitles(Object.fromEntries((s.prds ?? []).map((p) => [p.id, p.title])))
    }).catch(() => {})
    return () => { live = false }
  }, [hasPrds])
  const groups = useMemo(
    () => payload.groups.filter((g) => scope.some((r) => r.group === g.key)
      && (!filters.level || g.level === filters.level)),
    [payload.groups, scope, filters.level])
  const stories = useMemo(
    () => [...new Set(scope.map((r) => r.story).filter((s): s is string => !!s))].sort(), [scope])
  const statuses = useMemo(
    () => [...new Set(scope.map((r) => r.status).filter((s): s is string => !!s))].sort(), [scope])

  // The open row. A reload can drop it from the payload altogether (retired
  // elsewhere, regenerated): while it holds unsaved text the panel keeps the
  // row as it last was, so the draft is still there to copy or save.
  const held = useRef<TcRow | null>(null)
  const found = visible.find((r) => r.id === selected) ?? null
  if (found) held.current = found
  const current = found ?? (unsaved && held.current?.id === selected ? held.current : null)

  // The compiled workbooks, newest first, to link the open test case to its
  // row. Read when the panel OPENS (not per row, no change subscription): a
  // workbook compiled elsewhere shows up on the next open. A failed read keeps
  // the links already held. null until the first read: nothing is claimed
  // about a workbook before the inventory is known.
  const [books, setBooks] = useState<WorkbookEntry[] | null>(null)
  const panelOpen = current !== null
  useEffect(() => {
    if (!panelOpen) return
    let live = true
    getWorkbooks().then((b) => { if (live) setBooks(b) }).catch(() => {})
    return () => { live = false }
  }, [panelOpen])

  // Opening another row replaces the panel's editors: ask before unsaved
  // text goes. Prev / Next / Close ask inside the panel.
  const select = useCallback((id: string) => {
    if (id !== selected && !confirmDiscard()) return
    setSelected(id)
  }, [selected])
  const navigate = useCallback((dir: -1 | 1) => {
    const i = visible.findIndex((r) => r.id === selected)
    if (i < 0) return
    const next = visible[Math.min(visible.length - 1, Math.max(0, i + dir))]
    setSelected(next.id)
  }, [visible, selected])
  const gridRef = useRef<HTMLDivElement>(null)
  const rowEl = useCallback((id: string | null) =>
    [...(gridRef.current?.querySelectorAll<HTMLElement>('tr[data-tc]') ?? [])]
      .find((el) => el.dataset.tc === id), [])
  const close = useCallback(() => {
    // Focus goes back to the row the panel was opened from.
    rowEl(selected)?.focus()
    setSelected(null)
  }, [rowEl, selected])

  // Keep the open row on screen when the arrows move it past the card's edge.
  const currentId = current?.id ?? null
  useEffect(() => {
    if (!currentId) return
    rowEl(currentId)?.scrollIntoView?.({ block: 'nearest' })
  }, [currentId, rowEl])

  const toggleConfidence = (c: ConfidenceLevel) =>
    set({ confidence: filters.confidence.includes(c)
      ? filters.confidence.filter((x) => x !== c) : [...filters.confidence, c] })

  return (
    <div className="tc-review">
      <div className="tc-filters" role="group" aria-label="Filters">
        <div className="level-filter" role="group" aria-label="Level">
          {([null, 'sit', 'uat'] as Array<TcLevel | null>).map((l) => (
            <button key={l ?? 'all'} className={`chip${filters.level === l ? ' on' : ''}`}
              aria-pressed={filters.level === l}
              onClick={() => set({ level: l, group: null })}>
              {l ? l.toUpperCase() : 'All'}
            </button>
          ))}
        </div>
        <select aria-label="Run or flow" value={filters.group ?? ''} onChange={(e) => set({ group: e.target.value || null })}>
          <option value="">All runs and flows</option>
          {groups.map((g) => <option key={g.key} value={g.key}>{GROUP_WORD[g.kind]}: {g.label}</option>)}
        </select>
        {!lockStory && (
          <select aria-label="Story" value={filters.story ?? ''} onChange={(e) => set({ story: e.target.value || null })}>
            <option value="">All stories</option>
            {stories.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <select aria-label="Status" value={filters.status ?? ''} onChange={(e) => set({ status: e.target.value || null })}>
          <option value="">Any status</option>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="level-filter" role="group" aria-label="Confidence">
          {CONFIDENCE.map((c) => (
            <button key={c} className={`chip${filters.confidence.includes(c) ? ' on' : ''}`}
              aria-pressed={filters.confidence.includes(c)} onClick={() => toggleConfidence(c)}>
              {c}
            </button>
          ))}
        </div>
        <PrdChips
          options={prdIds}
          selected={selectedPrds}
          titles={prdTitles}
          onToggle={(id) => setFilters((f) => ({ ...f, prds: togglePrd(f.prds, id) }))}
        />
        <span className="tc-count">{visible.length} of {scope.length} test cases</span>
      </div>

      <div className={`tc-split${current ? ' open' : ''}`}>
        <div className="card tc-grid-card" ref={gridRef}>
          <table className="tc-grid">
            <thead>
              <tr>{COLUMNS.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {payload.groups.map((g) => {
                const rows = visible.filter((r) => r.group === g.key)
                if (!rows.length) return null
                let section: string | null = null
                return (
                  <Fragment key={g.key}>
                    <tr className="tc-group-row">
                      <td colSpan={COLUMNS.length}>
                        <span className="tc-band">
                          {GROUP_WORD[g.kind]}: {g.label} <span className="level-tag">{g.level.toUpperCase()}</span>
                        </span>
                      </td>
                    </tr>
                    <CommonRow group={g} />
                    {rows.map((r) => {
                      const head = r.section && r.section !== section
                      section = r.section ?? section
                      return (
                        <Fragment key={r.id}>
                          {head && (
                            <tr className="tc-section-row">
                              <td colSpan={COLUMNS.length}><span className="tc-band">Section: {r.section}</span></td>
                            </tr>
                          )}
                          <GridRow row={r} selected={r.id === selected} onSelect={select} />
                        </Fragment>
                      )
                    })}
                  </Fragment>
                )
              })}
              {visible.length === 0 && (
                <tr><td colSpan={COLUMNS.length}>
                  <p className="empty">
                    {scope.length === 0
                      ? (lockStory ? 'This story has no test cases yet.' : 'No test cases yet.')
                      : 'No test cases match these filters.'}
                  </p>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {current && (
          <ReviewPanel row={current} onClose={close} onNavigate={navigate}
            workbookHref={books === null ? undefined : workbookHrefFor(current.ref, books)} />
        )}
      </div>
    </div>
  )
}

// The sheet's shared pre-condition block (the lines every test case on the
// sheet has in common), collapsed by default. Read-only: it is defined once
// in the story.
function CommonRow({ group }: { group: TcGroup }) {
  const [open, setOpen] = useState(false)
  if (!group.common?.length) return null
  return (
    <tr className="tc-common-row">
      <td colSpan={COLUMNS.length}>
        <button className="btn tc-common-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Hide' : 'Show'} Pre-condition
        </button>
        {open && (
          <div className="tc-common">
            {group.common.map((line, i) => <RichText key={i} text={line} />)}
            <p className="tc-where">Shared by every test case in this group - defined once for the story</p>
          </div>
        )}
      </td>
    </tr>
  )
}

/* One cell of workbook text. The grid shows at most eight lines of it; a
 * cell that holds more fades out at the bottom, so the reviewer can tell
 * there is more to read in the panel. Measured, because CSS cannot ask
 * whether an element overflows. */
function Cell({ text }: { text: string }) {
  const box = useRef<HTMLDivElement>(null)
  const [clipped, setClipped] = useState(false)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const measure = () => setClipped(el.scrollHeight > el.clientHeight + 1)
    measure()
    // The column narrows when the panel opens: the same text may clip then.
    if (typeof ResizeObserver === 'undefined') return
    const watch = new ResizeObserver(measure)
    watch.observe(el)
    return () => watch.disconnect()
  }, [text])
  return (
    <div ref={box} className={`tc-cell${clipped ? ' clipped' : ''}`}
      title={clipped ? 'More text: open the row to read all of it' : undefined}>
      <RichText text={text} />
    </div>
  )
}

function GridRow({ row, selected, onSelect }: {
  row: TcRow; selected: boolean; onSelect: (id: string) => void
}) {
  return (
    <tr
      className={`tc-row${selected ? ' selected' : ''}`} data-tc={row.id} tabIndex={0}
      aria-current={selected ? 'true' : undefined}
      onClick={() => {
        // Dragging to select text in a cell ends in a click: not an open.
        if (window.getSelection?.()?.toString()) return
        onSelect(row.id)
      }}
      onKeyDown={(e) => {
        // Only the row's own key: a key pressed on a control inside it is that control's.
        if (e.target !== e.currentTarget) return
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(row.id) }
      }}
    >
      <td className="tc-id">
        <span className="id">{row.display_id}</span>
        {row.status && row.status !== 'active' && <span className="pill attn">{row.status}</span>}
      </td>
      <td><Cell text={row.cells.scenario} /></td>
      <td><Cell text={row.cells.steps} /></td>
      <td><Cell text={row.cells.data} /></td>
      <td><Cell text={row.cells.expected} /></td>
      <td><ConfidenceTag level={row.confidence || null} /></td>
      <td><Cell text={row.cells.remarks} /></td>
    </tr>
  )
}
