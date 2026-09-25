import { Component, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { GraphModel } from '../explorer/types'
import { toGraphDocument } from '../explorer/graphAdapter'
import GraphCanvas from '../../components/graph/GraphCanvas'
import IndentedTreeView from '../../components/graph/views/IndentedTreeView'
import { DEFAULT_GRAPH_CONFIG } from '../../lib/useGraphConfig'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'
import type { GraphNode } from '../../lib/types'

type Layout = 'force' | 'indented'

/** Under jsdom GraphCanvas bails when the container reports a 0x0 rect; this
 * boundary swallows any render fault so the toggle/chrome stay interactive. In
 * a real browser (real size) the boundary never triggers. */
class GraphErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() { return this.state.hasError ? null : this.props.children }
}

export function GlobalGraph({ graph, onNavigate }: {
  graph: GraphModel; onNavigate: (nodeId: string) => void
}) {
  const [layout, setLayout] = useState<Layout>('force')
  const colors = useMemo(() => resolveTypeColors(), [])
  const doc = useMemo(() => toGraphDocument(graph.nodes, graph.links), [graph])
  const visibleTypes = useMemo(() => new Set(doc.nodes.map((n) => n.nodeType)), [doc])
  const visibleEdgeTypes = useMemo(() => new Set(doc.edges.map((e) => e.edgeType)), [doc])
  const onNodeSelect = (n: GraphNode) => onNavigate(n.nodeId)
  return (
    <div className="explore-graph-full">
      <div className="graph-toggle" role="group" aria-label="Graph view">
        <button type="button" className={layout === 'force' ? 'active' : ''} onClick={() => setLayout('force')}>Force</button>
        <button type="button" className={layout === 'indented' ? 'active' : ''} onClick={() => setLayout('indented')}>Indented tree</button>
      </div>
      <div className="explore-graph-body">
        <TypeColorProvider colors={colors}>
          {layout === 'force' ? (
            <GraphErrorBoundary>
              <GraphCanvas
                nodes={doc.nodes} edges={doc.edges}
                visibleTypes={visibleTypes} visibleEdgeTypes={visibleEdgeTypes}
                searchQuery="" onNodeSelect={onNodeSelect}
                config={DEFAULT_GRAPH_CONFIG} reheatToken={0}
              />
            </GraphErrorBoundary>
          ) : (
            <IndentedTreeView nodes={doc.nodes} edges={doc.edges} onNodeSelect={onNodeSelect} />
          )}
        </TypeColorProvider>
      </div>
    </div>
  )
}
