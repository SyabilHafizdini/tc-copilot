import { useEffect, useState } from 'react'
import { getTestCases, onChange } from '../api'
import { TestCaseGrid } from '../testcases/TestCaseGrid'
import type { TestCasesPayload } from '../testcases/types'
import { Banner, Skeleton } from '../ui'

/* The story's test cases: the same review grid as the Test Cases page,
 * locked to this story. */
export function TestCasesTab({ storyId }: { storyId: string }) {
  const [payload, setPayload] = useState<TestCasesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const load = () => getTestCases()
      .then((p) => { setPayload(p); setError(null) })
      .catch((e) => setError(String(e)))
    load()
    return onChange(load)
  }, [])

  if (!payload) return error ? <Banner tone="blocked">{error}</Banner> : <Skeleton lines={5} />
  return (
    <div className="tc-tab">
      <TestCaseGrid payload={payload} lockStory={storyId} />
    </div>
  )
}
