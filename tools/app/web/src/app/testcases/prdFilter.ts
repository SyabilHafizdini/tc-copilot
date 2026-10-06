import type { TcRow } from './types'

type HasPrds = Pick<TcRow, 'prds'>

/** The PRD ids present across the rows: sorted, once each. */
export function prdOptions(rows: HasPrds[]): string[] {
  return [...new Set(rows.flatMap((r) => r.prds))].sort()
}

/** A row passes when nothing is selected, or when it draws on at least one
 * selected PRD - the same rule as a suite's include_prds. */
export function matchesPrds(row: HasPrds, selected: string[]): boolean {
  return selected.length === 0 || row.prds.some((p) => selected.includes(p))
}

export function togglePrd(selected: string[], id: string): string[] {
  return selected.includes(id) ? selected.filter((p) => p !== id) : [...selected, id]
}
