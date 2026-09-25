import { Component, useState, useMemo } from 'react'
import type { ReactNode } from 'react'
import type { GraphModel, DocView } from './types'
import { deriveBacklinks } from './backlinks'
import { toGraphDocument } from './graphAdapter'
import GraphCanvas from '../../components/graph/GraphCanvas'
import IndentedTreeView from '../../components/graph/views/IndentedTreeView'
import { subgraph } from '../../lib/graph'
import { DEFAULT_GRAPH_CONFIG } from '../../lib/useGraphConfig'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'
import type { GraphNode } from '../../lib/types'

type Layout = 'force' | 'indented'

const fileRefOf = (nodeId: string) => nodeId.split('#')[0]

/** GraphCanvas drives a d3 force simulation against a real SVG box. It is
 * defensive under jsdom (its mount effect bails out early when the container
 * reports a 0x0 rect, which is jsdom's default), but nothing guarantees every
 * future jsdom/d3 combination stays that well-behaved. This boundary makes
 * that guarantee explicit: if the graph subtree ever throws during render, it
 * is swallowed here instead of taking down the whole LinksPanel (backlinks +
 * toggle stay interactive) — in a real browser, where the container has a
 * real size, this boundary never triggers and GraphCanvas renders normally. */
class GraphErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

export function LinksPanel({ graph, docs, selected, onNavigate }: {
  graph: GraphModel; docs: Record<string, DocView>; selected: string | null; onNavigate: (nodeId: string) => void
}) {
  const [scope, setScope] = useState<'local' | 'global'>('local')
  const [layout, setLayout] = useState<Layout>('force')
  const colors = useMemo(() => resolveTypeColors(), [])
  const doc = useMemo(() => toGraphDocument(graph.nodes, graph.links), [graph])
  const groups = selected ? deriveBacklinks(graph, selected, docs) : []
  const view = useMemo(
    () => (scope === 'local' && selected ? subgraph(doc, fileRefOf(selected), 1) : doc),
    [doc, scope, selected],
  )
  const visibleTypes = useMemo(() => new Set(view.nodes.map((n) => n.nodeType)), [view])
  const visibleEdgeTypes = useMemo(() => new Set(view.edges.map((e) => e.edgeType)), [view])
  const onNodeSelect = (n: GraphNode) => onNavigate(n.nodeId)
  return (
    <div className="pane links-panel">
      <h4>Links</h4>
      {groups.length === 0 && <p className="section-label">No typed links</p>}
      {groups.map((g) => (
        <div className="link-row" key={g.relation}>
          <span className="relation">{g.relation}</span>
          {g.entries.map((e) => (
            <button key={e.ref} className="ref-link" onClick={() => onNavigate(e.ref)}>
              {e.title ?? e.ref.split('/').pop()}
            </button>
          ))}
        </div>
      ))}
      <div className="graph-toggle">
        <button className={scope === 'local' ? 'active' : ''} onClick={() => setScope('local')}>Local</button>
        <button className={scope === 'global' ? 'active' : ''} onClick={() => setScope('global')}>Global</button>
      </div>
      <div className="graph-toggle">
        <button className={layout === 'force' ? 'active' : ''} onClick={() => setLayout('force')}>Force</button>
        <button className={layout === 'indented' ? 'active' : ''} onClick={() => setLayout('indented')}>Indented</button>
      </div>
      <div className="graph-holder" style={{ height: 280 }}>
        <TypeColorProvider colors={colors}>
          {layout === 'force' ? (
            <GraphErrorBoundary>
              <GraphCanvas
                nodes={view.nodes} edges={view.edges}
                visibleTypes={visibleTypes}
                visibleEdgeTypes={visibleEdgeTypes}
                searchQuery="" onNodeSelect={onNodeSelect}
                config={DEFAULT_GRAPH_CONFIG} reheatToken={0}
              />
            </GraphErrorBoundary>
          ) : (
            <IndentedTreeView nodes={view.nodes} edges={view.edges} onNodeSelect={onNodeSelect} />
          )}
        </TypeColorProvider>
      </div>
    </div>
  )
}
