import type { WbCell, WbRow, WorkbookEntry, WorkbookPayload } from './types'

// Test fixture: a two-sheet workbook shaped like the exporter's output.
export function cell(text = '', over: Partial<WbCell> = {}): WbCell {
  return {
    runs: text ? [{ text, bold: false }] : [], fill: null, bold: false,
    align: null, valign: null, wrap: false, border: false, ...over,
  }
}

const row = (cells: WbCell[], over: Partial<WbRow> = {}): WbRow =>
  ({ height: null, tc: null, cells, ...over })

export const MAIN = 'C-TC-1 (Main flow)'
export const REF_1 = 'testcases/sit/m/1.1-AC01-01'
export const REF_2 = 'testcases/sit/m/1.1-AC01-02'

export function payload(over: Partial<WorkbookPayload> = {}): WorkbookPayload {
  return {
    name: 'demo', file: 'demo-latest.xlsx', kind: 'sit',
    compiled_at: '2026-10-04T10:15:00+08:00',
    source: { type: 'suite', name: 'demo' },
    freshness: 'fresh', changed_count: 0,
    versions: [
      { file: 'demo-latest.xlsx', compiled_at: '2026-10-04T10:15:00+08:00' },
      { file: 'demo_20261003-090000.xlsx', compiled_at: '2026-10-03T09:00:00+08:00' },
    ],
    links: {
      tcs: { 'TC-1.1-AC01-01': { sheet: MAIN, row: 3 }, 'TC-1.1-AC01-02': { sheet: MAIN, row: 4 } },
      questions: { 'Q-US-X-01': { sheet: 'AI Doubts', row: 2 } },
    },
    sheets: [
      {
        name: MAIN, cols: [26, 51, 56], frozen_rows: 1, merges: [[2, 1, 2, 3]],
        rows: [
          row([
            cell('Test Case ID', { fill: 'D9D9D9', bold: true, align: 'center', valign: 'center', wrap: true, border: true }),
            cell('Test Steps', { fill: 'D9D9D9', bold: true, border: true }),
            cell('AI Remarks', { fill: 'D9D9D9', bold: true, border: true }),
          ], { height: 38 }),
          row([cell('Section: Step 1', { fill: 'DDEBF7', bold: true, border: true }), cell(), cell()],
            { height: 18 }),
          row([
            cell('TC-1.1-AC01-01', { border: true, wrap: true, valign: 'top' }),
            { ...cell('', { border: true, wrap: true, valign: 'top' }),
              runs: [{ text: '1. Click ', bold: false }, { text: 'Save', bold: true }, { text: '.', bold: false }] },
            cell('Field / Values: Low [Q-US-X-01] - Inferred.', { border: true, wrap: true }),
          ], { tc: { ref: REF_1, id: '1.1-AC01-01', changed: false } }),
          row([
            cell('TC-1.1-AC01-02', { border: true, wrap: true, valign: 'top' }),
            cell('Continue from TC-1.1-AC01-01: Step 1 completed.', { border: true, wrap: true }),
            cell('', { border: true }),
          ], { tc: { ref: REF_2, id: '1.1-AC01-02', changed: true } }),
          row([cell('=SUM(A1:A2)', { formula: '=SUM(A1:A2)' }), cell(), cell()]),
        ],
      },
      {
        name: 'AI Doubts', cols: [16, 60, 44], frozen_rows: 1, merges: [],
        rows: [
          row([cell('Question ID', { bold: true }), cell('Question', { bold: true }), cell('Affected (TC id / column)', { bold: true })]),
          row([cell('Q-US-X-01'), cell('Which value?'), cell('TC-1.1-AC01-01 / Field / Values', { wrap: true })]),
        ],
      },
    ],
    ...over,
  }
}

export function entry(over: Partial<WorkbookEntry> = {}): WorkbookEntry {
  const { sheets: _sheets, links: _links, ...head } = payload()
  return {
    ...head,
    tcs: { [REF_1]: { sheet: MAIN, row: 3 }, [REF_2]: { sheet: MAIN, row: 4 } },
    ...over,
  }
}
