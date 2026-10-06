import { useEffect, useMemo, useRef } from 'react'
import { hrefFor } from '../shell/routes'
import { linkPieces } from './links'
import type { WbCell, WbLinks, WbLoc, WbRow, WbSheet, WbTc } from './types'

// Excel measures a column in characters of the default font and a row in
// points; these turn both into CSS pixels at 96 dpi.
const PX_PER_CHAR = 7
const COL_PAD_PX = 5
const PX_PER_PT = 96 / 72

type Span = { rowSpan: number; colSpan: number }

// Anchor cells of each merge keyed 'row:col', and the cells a merge covers.
function mergeMap(sheet: WbSheet): { anchors: Map<string, Span>; covered: Set<string> } {
  const anchors = new Map<string, Span>()
  const covered = new Set<string>()
  for (const [r1, c1, r2, c2] of sheet.merges) {
    // A merge never crosses the frozen header: clamp it to its own band.
    const last = r1 <= sheet.frozen_rows ? Math.min(r2, sheet.frozen_rows) : r2
    anchors.set(`${r1}:${c1}`, { rowSpan: last - r1 + 1, colSpan: c2 - c1 + 1 })
    for (let r = r1; r <= r2; r++) {
      for (let c = c1; c <= c2; c++) if (r !== r1 || c !== c1) covered.add(`${r}:${c}`)
    }
  }
  return { anchors, covered }
}

// Colours come from the file: only a plain 6-digit hex is ever put in CSS.
const hex = (c?: string | null) => (c && /^[0-9A-Fa-f]{6}$/.test(c) ? `#${c}` : undefined)

function cellStyle(cell: WbCell): React.CSSProperties {
  return {
    background: hex(cell.fill),
    color: hex(cell.color),
    fontWeight: cell.bold ? 700 : undefined,
    fontSize: typeof cell.size === 'number' && cell.size > 0 ? `${cell.size * PX_PER_PT}px` : undefined,
    textAlign: (cell.align ?? undefined) as React.CSSProperties['textAlign'],
    verticalAlign: cell.valign === 'center' ? 'middle' : cell.valign ?? 'bottom',
  }
}

export function SheetView({ sheet, links, focusRow, onOpenTc, hrefForLoc }: {
  sheet: WbSheet
  links: WbLinks
  focusRow?: number
  onOpenTc: (tc: WbTc, row: number) => void
  hrefForLoc: (loc: WbLoc) => string
}) {
  const box = useRef<HTMLDivElement>(null)
  const { anchors, covered } = useMemo(() => mergeMap(sheet), [sheet])
  const widths = sheet.cols.map((w) => Math.round(w * PX_PER_CHAR + COL_PAD_PX))

  // Scroll the linked row into view. A row the sheet does not have (a link
  // made before a recompile) is simply not found: no scroll, no error.
  useEffect(() => {
    if (!focusRow) return
    const tr = box.current?.querySelector<HTMLElement>(`tr[data-row="${focusRow}"]`)
    tr?.scrollIntoView?.({ block: 'center' })
  }, [sheet.name, focusRow])

  const text = (cell: WbCell, r: number) => cell.runs.map((run, i) => {
    const pieces = linkPieces(run.text, links).map((p, j) => (
      // An id that names this very row is not a link to itself.
      p.loc && !(p.loc.sheet === sheet.name && p.loc.row === r)
        ? <a key={j} className="wb-link" href={hrefForLoc(p.loc)}
            onClick={(e) => e.stopPropagation()}>{p.text}</a>
        : p.text
    ))
    return run.bold ? <b key={i}>{pieces}</b> : <span key={i}>{pieces}</span>
  })

  const renderRow = (row: WbRow, index: number) => {
    const r = index + 1
    const cls = [
      row.tc ? 'wb-tc' : '',
      row.tc?.changed ? 'wb-changed' : '',
      r === focusRow ? 'wb-focus' : '',
    ].filter(Boolean).join(' ')
    const tc = row.tc
    return (
      <tr key={r} data-row={r} data-tc-ref={tc?.ref} className={cls || undefined}
        style={row.height ? { height: `${row.height * PX_PER_PT}px` } : undefined}
        title={tc?.changed ? 'Changed since this workbook was compiled' : undefined}
        tabIndex={tc ? 0 : undefined}
        onClick={tc ? () => {
          // Dragging to select text in a cell ends in a click: not an open.
          if (window.getSelection?.()?.toString()) return
          onOpenTc(tc, r)
        } : undefined}
        onKeyDown={tc ? (e) => {
          // Only the row's own key: Enter on a link inside it follows the link.
          if (e.target !== e.currentTarget) return
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpenTc(tc, r)
          }
        } : undefined}>
        {row.cells.map((cell, ci) => {
          const c = ci + 1
          if (covered.has(`${r}:${c}`)) return null
          const span = anchors.get(`${r}:${c}`)
          // Excel lets unwrapped text spill only into EMPTY neighbours. The
          // cell to the right (past this cell's own merge) holding text means
          // the spill stops at the border instead of painting over it.
          const right = row.cells[ci + (span?.colSpan ?? 1)]
          const blocked = !cell.wrap && !!right && right.runs.some((run) => run.text !== '')
          const className = [
            'wb-cell',
            cell.border ? 'wb-b' : '',
            cell.wrap ? 'wb-wrap' : 'wb-nowrap',
            blocked ? 'wb-clip' : '',
            cell.formula ? 'wb-formula' : '',
          ].filter(Boolean).join(' ')
          return (
            <td key={c} data-cell={`${r}:${c}`} className={className} style={cellStyle(cell)}
              rowSpan={span?.rowSpan} colSpan={span?.colSpan}
              title={cell.formula ? 'calculated in Excel' : undefined}>
              {tc && c === 1
                ? <a className="wb-id" href={hrefFor({ kind: 'explore', path: tc.ref })}
                    onClick={(e) => e.stopPropagation()}>
                    {cell.runs.map((run) => run.text).join('')}
                  </a>
                : text(cell, r)}
            </td>
          )
        })}
      </tr>
    )
  }

  return (
    <div className="wb-scroll" ref={box}>
      <table className="wb-sheet" style={{ width: widths.reduce((a, b) => a + b, 0) }}>
        <colgroup>{widths.map((w, i) => <col key={i} style={{ width: w }} />)}</colgroup>
        {sheet.frozen_rows > 0 && (
          <thead>{sheet.rows.slice(0, sheet.frozen_rows).map((row, i) => renderRow(row, i))}</thead>
        )}
        <tbody>
          {sheet.rows.slice(sheet.frozen_rows).map((row, i) => renderRow(row, i + sheet.frozen_rows))}
        </tbody>
      </table>
    </div>
  )
}
