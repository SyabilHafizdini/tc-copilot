import { useEffect, useState } from 'react'
import type { State } from '../api'
import { getExplorer } from '../api'
import type { ExplorerSnapshot } from '../explorer/types'
import { VaultTree } from '../explorer/VaultTree'
import { MarkdownBody } from '../explorer/MarkdownBody'
import { hrefFor } from '../shell/routes'
import { Pill, Banner, Card, Skeleton } from '../ui'

export function DocumentsPage({ state }: { state: State }) {
  const [snap, setSnap] = useState<ExplorerSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [sel, setSel] = useState<string | null>(null)

  useEffect(() => {
    getExplorer().then(setSnap).catch(() => setSnap(null)).finally(() => setLoading(false))
  }, [])

  // Documents/Ingest is scoped to sources/ only — stories/flows/etc live elsewhere.
  const sources = (snap?.tree ?? []).filter((g) => g.kind === 'sources')
  const doc = sel ? snap?.docs[sel] ?? null : null
  const skeleton = state.stories.filter((s) => s.status === 'draft')

  return (
    <div className="page documents-page">
      <div className="page-head doc-header">
        <h1>Documents</h1>
        {state.prd.adopted && <Pill state="ready">v{state.prd.adopted} adopted</Pill>}
        {state.prd.staged && <Pill state="attn">v{state.prd.staged} staged</Pill>}
      </div>

      <Card>
        <div className="ingest-note">
          <p className="section-label">Ingest</p>
          <p>
            Drop a PRD / Figma / deck here to ingest. A new version <b>stages — it
            will never overwrite</b> the adopted source; the staged version lands in{' '}
            <a href={hrefFor({ kind: 'changes' })}>Maintain › Changes</a> for review
            and approval. Ingest itself runs as a CLI / agent step
            (<code>wiki ingest</code>) — this panel states the rule and shows what
            is already ingested.
          </p>
        </div>
      </Card>

      <div className="explorer-panes">
        {loading
          ? <div className="pane"><Skeleton lines={8} /></div>
          : <VaultTree tree={sources} selected={sel} onSelect={setSel} />}
        {doc
          ? <div className="pane document-view"><MarkdownBody body={doc.body_md} onNavigate={() => {}} /></div>
          : <div className="pane"><p className="section-label">Select a source to preview it verbatim</p></div>}
      </div>

      {skeleton.length > 0 && (
        <Banner tone="attn">
          Ingest produced {skeleton.length} skeleton {skeleton.length === 1 ? 'story' : 'stories'} →{' '}
          <a href={hrefFor({ kind: 'board' })}>Go to Alignment →</a>
        </Banner>
      )}
    </div>
  )
}
