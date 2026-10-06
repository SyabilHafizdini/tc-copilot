// Shapes served by tools/app/workbook_model.py (GET /api/workbook/{kind}/{file}
// and GET /api/workbooks). Rows and columns are 1-based, as Excel numbers them.

export type WbRun = { text: string; bold: boolean }

export type WbCell = {
  runs: WbRun[]
  fill: string | null        // 'D9D9D9', no leading '#'
  bold: boolean
  align: string | null       // Excel horizontal alignment: 'center', 'left', ...
  valign: string | null      // 'top' | 'center' | 'bottom'
  wrap: boolean
  border: boolean
  color?: string             // font colour, when the file sets one
  size?: number              // font size in points, when it is a title size
  formula?: string           // present only when the formula could NOT be resolved
}

export type WbTc = { ref: string; id: string; changed: boolean }
export type WbRow = { height: number | null; tc: WbTc | null; cells: WbCell[] }

export type WbSheet = {
  name: string
  cols: number[]             // widths in Excel character units
  frozen_rows: number
  merges: [number, number, number, number][]   // [r1, c1, r2, c2]
  rows: WbRow[]
}

export type WbSource = { type: 'suite' | 'export'; name: string; story?: string; flow?: string }
export type WbVersion = { file: string; compiled_at: string | null }
export type WbLoc = { sheet: string; row: number }
export type WbLinks = { tcs: Record<string, WbLoc>; questions: Record<string, WbLoc> }
export type Freshness = 'fresh' | 'changed' | 'unknown'

type WbHead = {
  name: string
  file: string
  kind: string
  compiled_at: string | null
  source: WbSource | null
  freshness: Freshness
  changed_count: number
  versions: WbVersion[]
}

export type WorkbookPayload = WbHead & { sheets: WbSheet[]; links: WbLinks }
// One inventory entry: the -latest file of a workbook name, and where each
// test case (by ref) sits in it.
export type WorkbookEntry = WbHead & { tcs: Record<string, WbLoc> }
// A file under build/inventory/ the listing could not read, and why.
export type WbSkipped = { kind: string; file: string; error: string }
export type WorkbookInventory = { workbooks: WorkbookEntry[]; skipped: WbSkipped[] }
