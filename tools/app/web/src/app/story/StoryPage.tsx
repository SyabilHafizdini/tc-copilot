import { useEffect, useMemo, useState } from 'react'
import { getExplorer, runDownload } from '../api'
import type { ActionResult, State } from '../api'
import type { ExplorerSnapshot, Field } from '../explorer/types'
import { Card, Banner, Breadcrumb, Console, Skeleton } from '../ui'
import { FrontmatterFields } from '../explorer/FrontmatterFields'
import { MarkdownBody } from '../explorer/MarkdownBody'
import { docTypeMeta } from '../explore/docType'
import { hrefFor } from '../shell/routes'
import { storyFromState, storyPhase, type StoryPhase } from './selectors'
import { storyTestCases } from './testcases'
import { PhaseStepper } from './PhaseStepper'
import { ReadinessBox } from './ReadinessBox'
import { TestCasesTab } from './TestCasesTab'
import { PropertiesRail } from './PropertiesRail'

const TABS = ['Overview', 'Acceptance Criteria', 'Components', 'Test Cases', 'Coverage', 'Traceability', 'Activity'] as const
type Tab = (typeof TABS)[number]
const PHASE_TAB: Record<StoryPhase, Tab> = { 0: 'Overview', 1: 'Acceptance Criteria', 2: 'Coverage', 3: 'Test Cases' }

// Pull one `# Heading` section's raw markdown from a body.
function bodySection(bodyMd: string, heading: string): string {
  const lines = bodyMd.split('\n')
  const out: string[] = []
  let inSec = false
  for (const ln of lines) {
    if (/^#\s+/.test(ln)) { inSec = ln.replace(/^#\s+/, '').trim() === heading; continue }
    if (inSec) out.push(ln)
  }
  return out.join('\n').trim()
}
function fieldsWhere(fields: Field[], keys: string[]): Field[] {
  return fields.filter((f) => keys.includes(f.key))
}

export function StoryPage({ id, state, result, onRun }: {
  id: string
  state: State
  result: ActionResult | { error: string } | null
  onRun: (name: string, params?: Record<string, unknown>) => void
}) {
  const [explorer, setExplorer] = useState<ExplorerSnapshot | null>(null)
  // The explorer snapshot is slow to arrive; every tab that renders from it
  // shows a skeleton until this flips, so tabs never sit silently empty.
  const [explorerLoading, setExplorerLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('Overview')
  useEffect(() => {
    getExplorer()
      .then(setExplorer)
      .catch(() => setExplorer(null))
      .finally(() => setExplorerLoading(false))
  }, [])

  const story = useMemo(() => storyFromState(state, id), [state, id])
  const doc = explorer?.docs[`stories/${id}`] ?? null
  const tcRows = useMemo(() => (explorer ? storyTestCases(explorer, id) : []), [explorer, id])

  if (!story) return <div className="page"><Banner tone="blocked">Story {id} not found</Banner></div>

  const meta = docTypeMeta('User Story')
  const phase = storyPhase(story)
  const fields = doc?.fields ?? []
  const onNavigate = (nodeId: string) => { window.location.hash = hrefFor({ kind: 'explore', path: nodeId }) }
  const c = story.components

  const go = (view: Parameters<typeof hrefFor>[0]) => { window.location.hash = hrefFor(view) }

  return (
    <div className="page story-view">
      <Breadcrumb items={[
        { label: 'Projects', onClick: () => go({ kind: 'projects' }) },
        { label: state.project, onClick: () => go({ kind: 'explore' }) },
        { label: 'Stories', onClick: () => go({ kind: 'stories' }) },
        { label: story.id },
      ]} />
      <div className="story-head">
        <span className={`doc-type-badge ${meta.cls}`}>{meta.icon} {meta.label}</span>
        <h1>{story.title ?? story.id}</h1>
        <span className="id">{story.id}</span>
      </div>

      <PhaseStepper phase={phase} onSelect={(p) => setTab(PHASE_TAB[p])} />
      <ReadinessBox story={story} onRun={onRun} onExport={(_action, params) => {
        // ReadinessBox's export action name ('export') is a CLI action, not a
        // download path -- runDownload's first arg is the artifact path under
        // build/inventory/. Mirror ExportButton: the stable download is always
        // sit/<name>-latest.xlsx, keyed off the same `name` used in params.
        const exportParams = params as { story?: string; flow?: string; name: string }
        void runDownload(`sit/${exportParams.name}-latest.xlsx`, exportParams)
      }} />

      <div className="story-body">
        <main className="story-main">
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t} className={`tab ${tab === t ? 'on' : ''}`} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>

          <div className="tab-body">
            {explorerLoading ? <Skeleton lines={5} /> : (
              <>
                {tab === 'Overview' && (doc ? <MarkdownBody body={doc.body_md} onNavigate={onNavigate} /> : <p className="section-label">No document.</p>)}
                {tab === 'Acceptance Criteria' && (
                  <FrontmatterFields fields={fieldsWhere(fields, ['acceptance_criteria'])} onNavigate={onNavigate}
                    onFocusItem={(itemId) => onNavigate(`stories/${id}#${itemId}`)} />
                )}
                {tab === 'Components' && (
                  <Card>
                    <p className="state">{c.total} components · {c.covered} covered · {c.out_of_scope} out-of-scope · {c.gaps} gap(s)</p>
                    <FrontmatterFields fields={fieldsWhere(fields, ['components'])} onNavigate={onNavigate}
                      onFocusItem={(itemId) => onNavigate(`stories/${id}#${itemId}`)} />
                  </Card>
                )}
                {tab === 'Test Cases' && <TestCasesTab rows={tcRows} />}
                {tab === 'Coverage' && (
                  <Card><p className="state">{c.covered}/{c.total} covered · {c.gaps} gap(s) · {c.acs_without_tcs} without active TCs</p></Card>
                )}
                {tab === 'Traceability' && (
                  <FrontmatterFields fields={fieldsWhere(fields, ['module', 'derived_from', 'uses_terms', 'illustrated_by'])}
                    onNavigate={onNavigate} onFocusItem={() => {}} />
                )}
                {tab === 'Activity' && (
                  <Card><pre className="activity">{doc ? bodySection(doc.body_md, 'Resolutions') || 'No activity yet.' : 'No activity yet.'}</pre></Card>
                )}
              </>
            )}
          </div>

          {result && 'error' in result ? (
            <Banner tone="blocked">{result.error}</Banner>
          ) : result ? (
            <Console result={result} />
          ) : null}
        </main>

        <PropertiesRail story={story} fields={fields} onRun={onRun} onNavigate={onNavigate} loading={explorerLoading} />
      </div>
    </div>
  )
}
