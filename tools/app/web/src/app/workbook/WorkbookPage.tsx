import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getTestCases, getWorkbook, onChange, runAction } from '../api'
import { hrefFor } from '../shell/routes'
import { confirmDiscard, useUnsavedDraft } from '../shell/unsaved'
import { ReviewPanel } from '../testcases/ReviewPanel'
import type { TcRow } from '../testcases/types'
import { Banner, PageSkeleton, Skeleton } from '../ui'
import { SheetTabs } from './SheetTabs'
import { SheetView } from './SheetView'
import { StaleBanner, canRecompile } from './StaleBanner'
import { VersionPicker } from './VersionPicker'
import { useWorkbooks } from './useWorkbooks'
import type { WbLoc, WbSkipped, WbTc, WorkbookPayload } from './types'

// Files the inventory could not read: named, so a workbook that is missing
// from the picker is explained instead of silently absent.
function SkippedFiles({ skipped }: { skipped: WbSkipped[] }) {
  if (!skipped.length) return null
  return (
    <Banner tone="attn">
      <span>Not listed, because the file could not be read:</span>
      <ul className="wb-skipped">
        {skipped.map((s) => <li key={`${s.kind}/${s.file}`}>{s.kind}/{s.file}: {s.error}</li>)}
      </ul>
    </Banner>
  )
}

/* A compiled workbook, drawn from the file exactly as testers receive it.
 * Read-only: the only writes are Recompile (the allowlisted suite_compile /
 * export actions) and the edits the review panel makes through its own
 * action. */
export function WorkbookPage({ wbKind, file, sheet, row }: {
  wbKind: string
  file: string
  sheet?: string
  row?: number
}) {
  const { books, skipped, error: booksError, reload: reloadBooks } = useWorkbooks(false)
  const [book, setBook] = useState<WorkbookPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The wiki's test cases. null until a read has SUCCEEDED: "not read yet" and
  // "the read failed" are not "this test case is gone".
  const [tcRows, setTcRows] = useState<TcRow[] | null>(null)
  const [tcError, setTcError] = useState<string | null>(null)
  const [openRef, setOpenRef] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)
  // Only the newest read may land: a slow read of a file the operator has
  // already left must not overwrite the one on screen.
  const seq = useRef(0)
  // Whether a workbook is on screen, and which route this page shows now:
  // async work started for one route must not act on another.
  const haveBook = useRef(false)
  const route = useRef('')
  route.current = `${wbKind}/${file}`

  const go = useCallback((kind: string, f: string, s?: string, r?: number) => {
    window.location.hash = hrefFor({ kind: 'workbook', wbKind: kind, file: f, sheet: s, row: r })
  }, [])

  // A bare #/workbook: land on the newest workbook once the inventory is in.
  // The address is REPLACED: the bare route must not stay in the history, or
  // Back would return to it and be sent forward again.
  useEffect(() => {
    if (!file && books && books.length > 0) {
      window.location.replace(hrefFor({ kind: 'workbook', wbKind: books[0].kind, file: books[0].file }))
    }
  }, [file, books])

  // `first` is the read after the file changed (nothing on screen yet). A
  // re-read (wiki change, recompile) that fails keeps what is on screen, so
  // an open review panel and its draft are never thrown away by it.
  const load = useCallback((first: boolean) => {
    if (!file) return
    const mine = ++seq.current
    // While nothing is on screen every read is a first read: its failure must
    // show the error, whichever read happens to be the newest.
    const initial = first || !haveBook.current
    getWorkbook(wbKind, file)
      .then((b) => { if (mine === seq.current) { haveBook.current = true; setBook(b); setError(null) } })
      .catch((e) => {
        if (mine !== seq.current || !initial) return
        haveBook.current = false
        setBook(null)
        setError(e instanceof Error ? e.message : String(e))
      })
    getTestCases()
      .then((p) => { if (mine === seq.current) { setTcRows(p.rows); setTcError(null) } })
      // A failed read keeps the rows already held; with none held it is an
      // error to show, never an empty wiki.
      .catch((e) => { if (mine === seq.current) setTcError(e instanceof Error ? e.message : String(e)) })
  }, [wbKind, file])

  useEffect(() => {
    haveBook.current = false
    setBook(null)
    setError(null)
    setOpenRef(null)
    setRefusal(null)
    setBusy(false)
    load(true)
    // A wiki change (an edit saved from the panel, a seal) moves freshness.
    return onChange(() => { load(false); reloadBooks() })
  }, [load, reloadBooks])

  // The sheet named in the URL; an unknown name (a link made before a
  // recompile renamed a run) falls back to the first test case sheet.
  const active = useMemo(() => {
    if (!book) return null
    return book.sheets.find((s) => s.name === sheet)
      ?? book.sheets.find((s) => s.name.startsWith('C-TC'))
      ?? book.sheets[0] ?? null
  }, [book, sheet])

  const hrefForLoc = useCallback((loc: WbLoc) =>
    hrefFor({ kind: 'workbook', wbKind, file, sheet: loc.sheet, row: loc.row }), [wbKind, file])

  const recompile = useCallback(async () => {
    if (!book || !canRecompile(book.source)) return
    const src = book.source
    const token = route.current
    const here = () => route.current === token
    setBusy(true)
    setRefusal(null)
    try {
      const res = src.type === 'suite'
        ? await runAction('suite_compile', { name: src.name })
        : await runAction('export', { story: src.story, name: src.name })
      if ('error' in res) { if (here()) setRefusal(res.error); return }
      if (res.rc !== 0) { if (here()) setRefusal((res.stdout + res.stderr).trim()); return }
      // The compile rewrote <name>-latest.xlsx and fired no change event
      // (build/ is not watched): show that file, re-read it and the inventory.
      const latest = `${book.name}-latest.xlsx`
      reloadBooks()
      if (!here()) return          // the operator moved on: leave their page alone
      if (latest !== file) go(wbKind, latest, active?.name)
      else load(false)
    } catch (e) {
      if (here()) setRefusal(e instanceof Error ? e.message : String(e))
    } finally {
      if (here()) setBusy(false)
    }
  }, [book, file, wbKind, active, go, load, reloadBooks])

  // The open test case as the panel shows it. A re-read can drop it from the
  // sheet or from the wiki; while its editor holds unsaved text the panel
  // keeps the row as it last was, so the draft is never unmounted by a reload.
  const unsaved = useUnsavedDraft()
  const held = useRef<{ tc: WbTc; row: TcRow } | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  if (!file) {
    if (booksError) {
      return (
        <div className="page">
          <div className="page-head"><h1>Workbook</h1></div>
          <Banner tone="blocked">The compiled workbooks could not be listed: {booksError}</Banner>
        </div>
      )
    }
    if (books === null) return <PageSkeleton />
    return (
      <div className="page">
        <div className="page-head"><h1>Workbook</h1></div>
        <SkippedFiles skipped={skipped} />
        <p className="empty">Nothing compiled yet — compile a suite on Suites &amp; Export.</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        <div className="page-head"><h1>Workbook</h1></div>
        <Banner tone="blocked">{wbKind}/{file}: {error}</Banner>
        <p><a className="row-link" href={hrefFor({ kind: 'suites' })}>Back to Suites &amp; Export</a></p>
      </div>
    )
  }
  if (!book || !active) return <PageSkeleton />

  // Only rows the read model linked to a test case take part; a TC- id in
  // column A without `tc` (old or mismatched sidecar) is plain text here.
  const tcsOnSheet = active.rows.flatMap((r) => (r.tc ? [r.tc] : []))
  const liveTc: WbTc | undefined = tcsOnSheet.find((t) => t.ref === openRef)
  const liveRow = tcRows?.find((r) => r.ref === openRef)
  if (liveTc && liveRow) held.current = { tc: liveTc, row: liveRow }
  const kept = unsaved && held.current?.tc.ref === openRef ? held.current : null
  const openTc = liveTc ?? kept?.tc
  const openRow = liveRow ?? kept?.row

  // Another row, another sheet or Close would replace or unmount the panel's
  // editors: with unsaved text the operator is asked first.
  const open = (ref: string) => { if (ref === openRef || confirmDiscard()) setOpenRef(ref) }
  const close = () => {
    // Focus goes back to the sheet row the panel was opened from.
    const at = [...(scroller.current?.querySelectorAll<HTMLElement>('tr[data-tc-ref]') ?? [])]
      .find((el) => el.dataset.tcRef === openRef)
    at?.focus()
    setOpenRef(null)
  }
  // The review panel owns the Arrow/Escape keys; this page adds no listener.
  const step = (dir: -1 | 1) => {
    const at = tcsOnSheet.findIndex((t) => t.ref === openRef)
    const next = tcsOnSheet[at + dir]
    if (at >= 0 && next) setOpenRef(next.ref)
  }

  return (
    <div className="wb-page">
      <div className="page-head">
        <h1>{book.name}</h1>
        <VersionPicker books={books ?? []} kind={book.kind} name={book.name} file={book.file}
          versions={book.versions} onPick={(k, f) => go(k, f)} />
      </div>
      <StaleBanner freshness={book.freshness} changedCount={book.changed_count}
        source={book.source} busy={busy} refusal={refusal} onRecompile={() => { void recompile() }} />
      {(booksError || skipped.length > 0) && (
        <div className="wb-stale">
          {booksError && <Banner tone="attn">The list of compiled workbooks could not be read: {booksError}</Banner>}
          <SkippedFiles skipped={skipped} />
        </div>
      )}
      <div className="wb-body" ref={scroller}>
        <SheetView sheet={active} links={book.links} focusRow={row}
          onOpenTc={(tc) => open(tc.ref)} hrefForLoc={hrefForLoc} />
        {openTc && openRow && (
          <ReviewPanel row={openRow} onClose={close} onNavigate={step} />
        )}
        {openTc && !openRow && tcRows === null && (
          // The wiki's test cases are not in yet (a cold read takes seconds),
          // or could not be read: say which, never "no longer in the wiki".
          <aside className="wb-missing" aria-label={`Review ${openTc.id}`}>
            {tcError
              ? (
                <Banner tone="blocked" onDismiss={() => setOpenRef(null)}>
                  {openTc.id} could not be opened: the test cases could not be read ({tcError}).
                </Banner>
              )
              : <div role="status" aria-label="Loading test case"><Skeleton lines={6} /></div>}
          </aside>
        )}
        {openTc && !openRow && tcRows !== null && (
          <aside className="wb-missing">
            <Banner tone="blocked" onDismiss={() => setOpenRef(null)}>
              {openTc.id} is no longer in the wiki. Recompile to drop it from the workbook.
            </Banner>
          </aside>
        )}
      </div>
      <SheetTabs names={book.sheets.map((s) => s.name)} active={active.name}
        onSelect={(name) => {
          // Clicking the sheet already shown is a no-op: keep the open panel.
          // Another sheet closes the panel, so unsaved text is asked about
          // here, before anything moves (the route guard then has nothing to ask).
          if (name !== active.name) {
            if (!confirmDiscard()) return
            setOpenRef(null)
          }
          go(wbKind, file, name)
        }} />
    </div>
  )
}
