import { useEffect, useState } from 'react'
import { getTestCases, onChange } from '../api'
import { TestCaseGrid } from '../testcases/TestCaseGrid'
import type { TestCasesPayload } from '../testcases/types'
import { Banner, PageSkeleton } from '../ui'

/* Project-wide test case review: the workbook's sheet as a grid, with the
 * review panel. Reloads on every change event, so a saved edit shows up
 * without a manual refresh. */
export function TestCasesPage() {
  const [payload, setPayload] = useState<TestCasesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const load = () => getTestCases()
      .then((p) => { setPayload(p); setError(null) })
      .catch((e) => setError(String(e)))
    load()
    return onChange(load)
  }, [])

  if (!payload) {
    return error
      ? <div className="page"><Banner tone="blocked">{error}</Banner></div>
      : <PageSkeleton />
  }
  return (
    <div className="page tc-page">
      <div className="page-head"><h1>Test Cases</h1></div>
      {error && <Banner tone="blocked">{error}</Banner>}
      <TestCaseGrid payload={payload} />
    </div>
  )
}
