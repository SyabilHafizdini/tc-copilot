import { useEffect, useMemo, useState } from 'react'
import { DirectoryTree } from './DirectoryTree'
import { OntologyTree } from './OntologyTree'
import { buildFileTree } from './fileTree'
import { buildOntologyTree } from './ontology'
import { FrontmatterFields } from '../explorer/FrontmatterFields'
import { LinksPanel } from '../explorer/LinksPanel'
import { MarkdownBody } from '../explorer/MarkdownBody'
import type { ExplorerSnapshot } from '../explorer/types'
import { getExplorer, onChange } from '../api'
import { useView, hrefFor } from '../shell/routes'
import { docTypeMeta } from './docType'
import { Banner, Breadcrumb, PageSkeleton, Pill, type Crumb } from '../ui'
import { GlobalGraph } from './GlobalGraph'
import { ItemView } from './ItemView'

const fileRefOf = (nodeId: string) => nodeId.split('#')[0]
const fragOf = (nodeId: string) => nodeId.split('#')[1] ?? null

export function ExplorePage() {
  const view = useView()
  const path = view.kind === 'explore' ? view.path ?? null : null
  const [snapshot, setSnapshot] = useState<ExplorerSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'files' | 'graph'>('files')
  const [treeMode, setTreeMode] = useState<'ontology' | 'type'>('ontology')

  useEffect(() => {
    const load = () => getExplorer().then(setSnapshot).catch((e) => setError(String(e)))
    load()
    return onChange(load)
  }, [])

  const fileTree = useMemo(
    () => buildFileTree(snapshot ? Object.keys(snapshot.docs) : []),
    [snapshot],
  )
  const ontologyTree = useMemo(
    () => (snapshot ? buildOntologyTree(snapshot.graph, snapshot.docs) : []),
    [snapshot],
  )

  if (error && !snapshot) return <div className="page"><Banner tone="blocked">{error}</Banner></div>
  if (!snapshot) return <PageSkeleton />

  const doc = path ? snapshot.docs[fileRefOf(path)] ?? null : null
  const frag = path ? fragOf(path) : null
  const meta = doc ? docTypeMeta(doc.type ?? '') : null
  // Jira-style split: itemized fields (acceptance_criteria, business_rules) are
  // primary content and get the wide main column; everything else is compact
  // metadata for the sidebar.
  const itemizedFields = doc ? doc.fields.filter((f) => f.kind === 'itemized') : []
  const metaFields = doc ? doc.fields.filter((f) => f.kind !== 'itemized') : []

  const select = (nodeId: string) => { window.location.hash = hrefFor({ kind: 'explore', path: nodeId }) }
  const focusItem = (id: string) => { if (doc) select(`${doc.ref}#${id}`) }

  return (
    <div className="explore">
      <div className="explore-topbar">
        {path
          ? (() => {
              const segments = fileRefOf(path).split('/')
              const items: Crumb[] = segments.map((seg, i) => ({
                label: seg,
                onClick: () => select(segments.slice(0, i + 1).join('/')),
              }))
              // A fragment item (AC/BR/component id) is the terminal,
              // current-location crumb.
              if (frag) items.push({ label: frag })
              return <Breadcrumb items={items} />
            })()
          : <span />}
        <div className="explore-mode">
          <button className={mode === 'files' ? 'active' : ''} onClick={() => setMode('files')}>Files</button>
          <button className={mode === 'graph' ? 'active' : ''} onClick={() => setMode('graph')}><span aria-hidden="true">🕸 </span>Graph</button>
        </div>
      </div>
      {mode === 'graph'
        ? <GlobalGraph graph={snapshot.graph} onNavigate={select} />
        : (
          <div className="explore-body">
            <div className="explore-tree">
              <div className="tree-switch" aria-label="tree grouping">
                <button type="button" aria-pressed={treeMode === 'ontology'}
                  className={treeMode === 'ontology' ? 'active' : ''}
                  onClick={() => setTreeMode('ontology')}>Ontology</button>
                <button type="button" aria-pressed={treeMode === 'type'}
                  className={treeMode === 'type' ? 'active' : ''}
                  onClick={() => setTreeMode('type')}>By type</button>
              </div>
              {treeMode === 'ontology'
                ? <OntologyTree tree={ontologyTree} selected={path} onSelect={select} />
                : <DirectoryTree tree={fileTree} docs={snapshot.docs} selected={path} onSelect={select} />}
            </div>

            <div className="pane explore-content">
              {doc && frag ? (
                <ItemView doc={doc} frag={frag} graph={snapshot.graph} docs={snapshot.docs} onNavigate={select} />
              ) : doc && meta ? (
                <>
                  <div className="doc-header">
                    <span className={`doc-type-badge ${meta.cls}`}>
                      <span aria-hidden="true">{meta.icon}</span> {meta.label}
                    </span>
                    {doc.status && <Pill state="ready">{doc.status}</Pill>}
                  </div>
                  {itemizedFields.length > 0 && (
                    <FrontmatterFields fields={itemizedFields} onNavigate={select} onFocusItem={focusItem} />
                  )}
                  <MarkdownBody body={doc.body_md} onNavigate={select} />
                </>
              ) : (
                <p className="section-label">Select a document</p>
              )}
            </div>

            <div className="pane explore-panel">
              <h4>Metadata</h4>
              {doc
                ? <FrontmatterFields fields={metaFields} onNavigate={select} onFocusItem={focusItem} />
                : <p className="section-label">No document selected</p>}
              <LinksPanel graph={snapshot.graph} docs={snapshot.docs} selected={path} onNavigate={select} />
            </div>
          </div>
        )}
    </div>
  )
}
