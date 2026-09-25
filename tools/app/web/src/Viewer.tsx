import { useState, useMemo, useCallback } from 'react'
import type { ReactNode } from 'react'
import { X, Filter, Info } from 'lucide-react'
import type { GraphDocument, GraphNode, GraphEdge } from './lib/types'
import {
  computeStats, nodeRelationships, subgraph,
} from './lib/graph'
import GraphCanvas from './components/graph/GraphCanvas'
import TreeView from './components/graph/views/TreeView'
import IndentedTreeView from './components/graph/views/IndentedTreeView'
import ArcDiagramView from './components/graph/views/ArcDiagramView'
import MatrixView from './components/graph/views/MatrixView'
import TableView from './components/graph/views/TableView'
import { ViewSwitcher } from './components/graph/ViewSwitcher'
import { GraphControls } from './components/graph/GraphControls'
import MetricCards from './components/graph/MetricCards'
import AboutPanel from './components/graph/AboutPanel'
import { computeMetrics } from './lib/metrics'
import { NodeDetailPanel } from './components/graph/NodeDetailPanel'
import { useGraphConfig } from './lib/useGraphConfig'
import { filterGraph } from './lib/filterGraph'
import { PresetBar } from './components/graph/PresetBar'
import { resolvePreset, findDefaultPreset, matchActivePreset } from './lib/presets'
import type { GraphPreset, ViewMode } from './lib/types'
import { resolveTypeColors } from './lib/nodeStyle'
import { TypeColorProvider } from './lib/TypeColorContext'

const LARGE_GRAPH_THRESHOLD = 2000

export default function Viewer({ graph }: { graph: GraphDocument }): ReactNode {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null)
  const [subgraphDepth, setSubgraphDepth] = useState(2)
  const [largeWarningDismissed, setLargeWarningDismissed] = useState(false)

  const presets = useMemo<GraphPreset[]>(() => graph.presets ?? [], [graph])

  const allNodeTypes = useMemo(
    () => [...new Set(graph.nodes.map((n) => n.nodeType))].sort(),
    [graph],
  )
  const allEdgeTypes = useMemo(
    () => [...new Set(graph.edges.map((e) => e.edgeType))].sort(),
    [graph],
  )

  // Resolved once per graph. Memoized because useNodeColor's identity depends on
  // it and that resolver is a D3 effect dependency in GraphCanvas/TreeView — an
  // unstable palette would re-run the force simulation on every render.
  const typeColors = useMemo(
    () => resolveTypeColors(graph.meta?.typeColors),
    [graph.meta?.typeColors],
  )

  // Seed-once: consumed only by the lazy useState initializers below, which run
  // at mount. A new graph arrives as a new tab (keyed remount), so this never
  // needs to re-seed an existing instance.
  const initial = useMemo(() => {
    const nts = graph.nodes.map((n) => n.nodeType)
    const ets = graph.edges.map((e) => e.edgeType)
    const def = findDefaultPreset(graph.presets ?? [])
    return def
      ? resolvePreset(def, nts, ets)
      : {
          visibleTypes: new Set(nts),
          visibleEdgeTypes: new Set(ets),
          search: '',
        }
  }, [graph])

  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(() => initial.visibleTypes)
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<string>>(() => initial.visibleEdgeTypes)
  const [searchQuery, setSearchQuery] = useState(() => initial.search)
  // Presets are a filter overlay only — the view stays whatever the user selects.
  const [viewMode, setViewMode] = useState<ViewMode>('force')
  const [aboutOpen, setAboutOpen] = useState(false)

  const { config, setConfig, resetConfig } = useGraphConfig()
  const [reheatToken, setReheatToken] = useState(0)
  const handleReheat = useCallback(() => setReheatToken((n) => n + 1), [])

  const applyPreset = useCallback(
    (preset: GraphPreset) => {
      const r = resolvePreset(preset, allNodeTypes, allEdgeTypes)
      setVisibleTypes(r.visibleTypes)
      setVisibleEdgeTypes(r.visibleEdgeTypes)
      setSearchQuery(r.search)
    },
    [allNodeTypes, allEdgeTypes],
  )

  const clearPreset = useCallback(() => {
    setVisibleTypes(new Set(allNodeTypes))
    setVisibleEdgeTypes(new Set(allEdgeTypes))
    setSearchQuery('')
  }, [allNodeTypes, allEdgeTypes])

  const activePresetName = useMemo(
    () =>
      matchActivePreset(
        presets, visibleTypes, visibleEdgeTypes, searchQuery, allNodeTypes, allEdgeTypes,
      ),
    [presets, visibleTypes, visibleEdgeTypes, searchQuery, allNodeTypes, allEdgeTypes],
  )

  const stats = useMemo(() => computeStats(graph), [graph])

  // Which nodes/edges to render: full graph, or the focused subgraph.
  const { displayNodes, displayEdges } = useMemo<{
    displayNodes: GraphNode[]
    displayEdges: GraphEdge[]
  }>(() => {
    if (focusedNodeId) {
      const sub = subgraph(graph, focusedNodeId, subgraphDepth)
      return { displayNodes: sub.nodes, displayEdges: sub.edges }
    }
    return { displayNodes: graph.nodes, displayEdges: graph.edges }
  }, [graph, focusedNodeId, subgraphDepth])

  // Tree views take pre-filtered data; the force canvas filters internally.
  const filtered = useMemo(
    () => filterGraph(displayNodes, displayEdges, visibleTypes, visibleEdgeTypes, searchQuery),
    [displayNodes, displayEdges, visibleTypes, visibleEdgeTypes, searchQuery],
  )

  // Summary bar: the filtered set measured against whole-graph totals.
  const metrics = useMemo(
    () => computeMetrics(filtered.nodes, filtered.edges, stats),
    [filtered, stats],
  )

  const handleNodeSelect = useCallback(
    (node: GraphNode) => {
      setSelectedNode({
        ...node,
        relationships: nodeRelationships(graph, node.nodeId) as unknown as Record<string, unknown>[]
      })
    },
    [graph],
  )

  const handleFocusSubgraph = useCallback((nodeId: string) => {
    setFocusedNodeId(nodeId)
  }, [])

  const handleResetView = useCallback(() => {
    setFocusedNodeId(null)
    setSelectedNode(null)
    const def = findDefaultPreset(presets)
    if (def) {
      const r = resolvePreset(def, allNodeTypes, allEdgeTypes)
      setVisibleTypes(r.visibleTypes)
      setVisibleEdgeTypes(r.visibleEdgeTypes)
      setSearchQuery(r.search)
      return
    }
    setSearchQuery('')
    setVisibleTypes(new Set(graph.nodes.map((n) => n.nodeType)))
    setVisibleEdgeTypes(new Set(graph.edges.map((e) => e.edgeType)))
  }, [graph, presets, allNodeTypes, allEdgeTypes])

  const showLargeWarning =
    graph.nodes.length > LARGE_GRAPH_THRESHOLD && !largeWarningDismissed

  return (
    <TypeColorProvider colors={typeColors}>
      <div className="flex h-full flex-col p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            {/* About sits with the graph's identity rather than the view
                controls — it describes the dataset, not the layout. Centering it
                against ViewSwitcher was also visually off, since that component
                is a two-row column (buttons plus caption). */}
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-semibold text-zinc-900">
                {graph.meta?.title ?? 'Knowledge Graph Explorer'}
              </h1>
              <button
                type="button"
                onClick={() => setAboutOpen(true)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs font-medium text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
              >
                <Info className="size-3.5" aria-hidden="true" />
                About
              </button>
            </div>
            <p className="mt-1 text-sm text-zinc-500">
              {graph.meta?.description ?? 'Explore the knowledge graph.'}
              {focusedNodeId && (
                <span className="ml-2 inline-flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                  Subgraph view – depth {subgraphDepth}
                  <button
                    type="button"
                    onClick={() => setFocusedNodeId(null)}
                    className="ml-1 text-blue-500 hover:text-blue-700"
                  >
                    ✕
                  </button>
                </span>
              )}
              {activePresetName && (
                <span
                  data-testid="active-preset-badge"
                  className="ml-2 inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
                >
                  <Filter className="size-3" aria-hidden="true" />
                  Preset: {activePresetName}
                  <button
                    type="button"
                    onClick={clearPreset}
                    aria-label="Clear preset"
                    className="ml-1 text-indigo-500 hover:text-indigo-700"
                  >
                    <X className="size-3" aria-hidden="true" />
                  </button>
                </span>
              )}
            </p>
          </div>
          <ViewSwitcher mode={viewMode} onModeChange={setViewMode} />
        </div>

        {aboutOpen && (
          <AboutPanel
            meta={graph.meta}
            presets={presets}
            stats={stats}
            onClose={() => setAboutOpen(false)}
          />
        )}

        {showLargeWarning && (
          <div
            role="status"
            className="mb-3 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800"
          >
            <span>
              Large graph ({graph.nodes.length.toLocaleString()} nodes) – rendering may be slow.
            </span>
            <button
              type="button"
              onClick={() => setLargeWarningDismissed(true)}
              aria-label="Dismiss warning"
              className="rounded p-1 text-amber-700 hover:bg-amber-100"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        )}

        {presets.length > 0 && (
          <PresetBar
            presets={presets}
            activeName={activePresetName}
            onApply={applyPreset}
            onClear={clearPreset}
          />
        )}

        <GraphControls
          allNodeTypes={allNodeTypes}
          visibleTypes={visibleTypes}
          onSetVisibleTypes={setVisibleTypes}
          allEdgeTypes={allEdgeTypes}
          visibleEdgeTypes={visibleEdgeTypes}
          onSetVisibleEdgeTypes={setVisibleEdgeTypes}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          subgraphDepth={subgraphDepth}
          onDepthChange={setSubgraphDepth}
          focusedNodeId={focusedNodeId}
          onResetView={handleResetView}
          config={config}
          onConfigChange={setConfig}
          onResetConfig={resetConfig}
          onReheat={handleReheat}
          showAdvanced={viewMode === 'force'}
        />

        {displayNodes.length > 0 && <MetricCards metrics={metrics} />}

        <div className="mt-3 flex flex-1 overflow-hidden rounded-lg border border-zinc-200 bg-white">
          {displayNodes.length === 0 ? (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-sm text-zinc-500">No graph data available.</p>
            </div>
          ) : (
            <>
              <div className="relative flex-1 overflow-hidden">
                {viewMode === 'force' && (
                  <GraphCanvas
                    nodes={displayNodes}
                    edges={displayEdges}
                    visibleTypes={visibleTypes}
                    visibleEdgeTypes={visibleEdgeTypes}
                    searchQuery={searchQuery}
                    onNodeSelect={handleNodeSelect}
                    onBackgroundClick={() => setSelectedNode(null)}
                    config={config}
                    reheatToken={reheatToken}
                  />
                )}
                {(viewMode === 'tidy' || viewMode === 'radial') && (
                  <TreeView
                    nodes={filtered.nodes}
                    edges={filtered.edges}
                    variant={viewMode}
                    graphTitle={graph.meta?.title}
                    onNodeSelect={handleNodeSelect}
                    onBackgroundClick={() => setSelectedNode(null)}
                  />
                )}
                {viewMode === 'indented' && (
                  <IndentedTreeView
                    nodes={filtered.nodes}
                    edges={filtered.edges}
                    onNodeSelect={handleNodeSelect}
                  />
                )}
                {viewMode === 'arc' && (
                  <ArcDiagramView
                    nodes={filtered.nodes}
                    edges={filtered.edges}
                    onNodeSelect={handleNodeSelect}
                  />
                )}
                {viewMode === 'matrix' && (
                  <MatrixView
                    nodes={filtered.nodes}
                    edges={filtered.edges}
                    onNodeSelect={handleNodeSelect}
                  />
                )}
                {viewMode === 'table' && (
                  <TableView
                    nodes={filtered.nodes}
                    edges={filtered.edges}
                    onNodeSelect={handleNodeSelect}
                  />
                )}
                <NodeDetailPanel
                  node={selectedNode}
                  onClose={() => setSelectedNode(null)}
                  onFocusSubgraph={handleFocusSubgraph}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </TypeColorProvider>
  )
}
