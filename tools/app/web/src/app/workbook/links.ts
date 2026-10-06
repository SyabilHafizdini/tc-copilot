import { hrefFor } from '../shell/routes'
import type { WbLinks, WbLoc, WorkbookEntry } from './types'

// Href of the most recent workbook that contains this test case, at its row.
// `books` arrives newest first (GET /api/workbooks), so the first hit wins.
export function workbookHrefFor(ref: string, books: WorkbookEntry[]): string | null {
  for (const b of books) {
    const loc = b.tcs[ref]
    if (loc) {
      return hrefFor({ kind: 'workbook', wbKind: b.kind, file: b.file, sheet: loc.sheet, row: loc.row })
    }
  }
  return null
}

// Question ids (Q-<STORY>-NN) and displayed test case ids (TC-... / BR-...).
const ID_RE = /Q-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-\d{2,}|(?:TC|BR)-[A-Za-z0-9.]+(?:-[A-Za-z0-9.]+)*/g

export type Piece = { text: string; loc: WbLoc | null }

// Split cell text into plain pieces and ids this workbook can locate. An id
// the workbook does not hold stays plain text.
export function linkPieces(text: string, links: WbLinks): Piece[] {
  const out: Piece[] = []
  let last = 0
  for (const m of text.matchAll(ID_RE)) {
    // A trailing '.' ends a sentence, it is not part of the id.
    const id = m[0].replace(/\.+$/, '')
    const loc = links.questions[id] ?? links.tcs[id] ?? null
    if (!loc) continue
    const at = m.index ?? 0
    if (at > last) out.push({ text: text.slice(last, at), loc: null })
    out.push({ text: id, loc })
    last = at + id.length
  }
  if (last < text.length) out.push({ text: text.slice(last), loc: null })
  return out
}
