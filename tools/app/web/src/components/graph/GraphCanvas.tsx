import { useRef, useEffect, useMemo, useCallback } from 'react'
import type { ReactNode } from 'react'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../../lib/types'
import type { GraphConfig } from '../../lib/useGraphConfig'
import { getNodeLabel } from '../../lib/nodeStyle'
import { useNodeColor } from '../../lib/TypeColorContext'
import { filterGraph } from '../../lib/filterGraph'

export interface GraphCanvasProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  visibleTypes: Set<string>
  searchQuery: string
  visibleEdgeTypes: Set<string>
  onNodeSelect: (node: GraphNode) => void
  /** Fires when the user clicks empty SVG background. Used to dismiss the
   * detail panel + clear any active highlight. */
  onBackgroundClick?: () => void
  // Advanced config (Task 9):
  config: GraphConfig
  reheatToken: number  // changing this triggers simulation.alpha(0.5).restart()
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  data: GraphNode
  fx?: number | null
  fy?: number | null
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  data: GraphEdge
}

function getTooltipContent(node: GraphNode): string {
  return `${getNodeLabel(node)}\nType: ${node.nodeType}`
}

// Stable hash: deterministic angle per nodeId so layout doesn't jitter on reload.
function hashStringToFloat(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  // Normalize to [0, 1)
  return ((h % 1000) + 1000) % 1000 / 1000
}

// Stable per-node random seed: nodes start scattered (not clustered by type)
// so the simulation is free to find connectivity-based clusters via link
// forces. Using two independent hashes for x and y so the spread is even.
const SEED_RADIUS_PX = 350

function hashStringToFloat2(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0
  }
  return ((h % 1000) + 1000) % 1000 / 1000
}

function getRadialSeedPosition(
  nodeId: string,
  _nodeType: string,
): { x: number; y: number } {
  const a = hashStringToFloat(nodeId) * 2 * Math.PI
  const r = (0.3 + hashStringToFloat2(nodeId) * 0.7) * SEED_RADIUS_PX
  return { x: r * Math.cos(a), y: r * Math.sin(a) }
}

export default function GraphCanvas({
  nodes,
  edges,
  visibleTypes,
  searchQuery,
  visibleEdgeTypes,
  onNodeSelect,
  onBackgroundClick,
  config,
  reheatToken,
}: GraphCanvasProps): ReactNode {
  const nodeColor = useNodeColor()
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const prevSimNodesRef = useRef<Map<string, { x: number; y: number }>>(new Map())
  const onNodeSelectRef = useRef(onNodeSelect)
  const onBackgroundClickRef = useRef(onBackgroundClick)
  const labelShowZoomRef = useRef(config.labelShowZoom)
  const svgSelRef = useRef<d3.Selection<SVGSVGElement, unknown, null, undefined> | null>(null)
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)

  onNodeSelectRef.current = onNodeSelect
  onBackgroundClickRef.current = onBackgroundClick
  labelShowZoomRef.current = config.labelShowZoom

  // Compute edge count per node from the FULL edge set (before any filtering),
  // so we can distinguish nodes that exist in isolation from nodes that just
  // happen to have their neighbours hidden by the current type filter.
  const fullEdgeCount = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of edges) {
      counts.set(e.fromNodeId, (counts.get(e.fromNodeId) ?? 0) + 1)
      counts.set(e.toNodeId, (counts.get(e.toNodeId) ?? 0) + 1)
    }
    return counts
  }, [edges])

  // Memoize the filtered node/edge sets so references are stable
  const { nodes: filteredNodes, edges: filteredEdges } = useMemo(
    () => filterGraph(nodes, edges, visibleTypes, visibleEdgeTypes, searchQuery),
    [nodes, edges, visibleTypes, visibleEdgeTypes, searchQuery],
  )

  // Tooltip helpers — manipulate DOM directly to avoid re-renders
  const showTooltip = useCallback((x: number, y: number, content: string) => {
    const el = tooltipRef.current
    if (!el) return
    el.style.left = `${x}px`
    el.style.top = `${y}px`
    el.style.display = 'block'
    el.replaceChildren(
      ...content.split('\n').map((line) => {
        const div = document.createElement('div')
        div.textContent = line
        return div
      }),
    )
  }, [])

  const hideTooltip = useCallback(() => {
    const el = tooltipRef.current
    if (!el) return
    el.style.display = 'none'
  }, [])

  useEffect(() => {
    const container = containerRef.current
    const svgEl = svgRef.current
    if (!container || !svgEl) return

    const { width, height } = container.getBoundingClientRect()
    if (width === 0 || height === 0) return

    const svgSel = d3.select(svgEl)
    svgSel.selectAll('*').remove()
    svgSel.on('.zoom', null)
    svgSel.on('click', null)

    // Save positions from old simulation before stopping it
    if (simulationRef.current) {
      const oldNodes = simulationRef.current.nodes()
      const posMap = new Map<string, { x: number; y: number }>()
      for (const n of oldNodes) {
        if (n.x != null && n.y != null) {
          posMap.set(n.id, { x: n.x, y: n.y })
        }
      }
      prevSimNodesRef.current = posMap
      simulationRef.current.stop()
    }

    // Build sim nodes, preserving positions from previous simulation.
    // New nodes get a deterministic radial-by-type seed so the layout starts
    // pre-clustered instead of converging from random.
    const prevPositions = prevSimNodesRef.current
    const simNodes: SimNode[] = filteredNodes.map((n) => {
      const prev = prevPositions.get(n.nodeId)
      if (prev) {
        return { id: n.nodeId, data: n, x: prev.x, y: prev.y }
      }
      const seed = getRadialSeedPosition(n.nodeId, n.nodeType)
      return { id: n.nodeId, data: n, x: seed.x, y: seed.y }
    })
    const nodeIndex = new Map(simNodes.map((n) => [n.id, n]))

    const simLinks: SimLink[] = filteredEdges
      .filter((e) => nodeIndex.has(e.fromNodeId) && nodeIndex.has(e.toNodeId))
      .map((e) => ({
        source: e.fromNodeId,
        target: e.toNodeId,
        data: e,
      }))

    if (simNodes.length === 0) {
      svgSel.attr('width', width).attr('height', height)
      svgSel
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#71717a')
        .attr('font-size', 14)
        .text('No graph data available.')
      return
    }

    const isLarge = simNodes.length > 80
    const chargeStrength = isLarge ? -300 : -500

    // Use lower alpha when positions are being preserved to avoid big jumps
    const hasPreservedPositions = simNodes.some((n) => n.x != null && n.y != null)

    svgSel
      .attr('width', width)
      .attr('height', height)
      .attr('role', 'img')
      .attr('aria-label', 'Knowledge graph visualization')
      .style('cursor', 'move')

    // Drop shadow filter
    const defs = svgSel.append('defs')
    const filter = defs
      .append('filter')
      .attr('id', 'kg-drop-shadow')
      .attr('x', '-50%')
      .attr('y', '-50%')
      .attr('width', '200%')
      .attr('height', '200%')
    filter
      .append('feDropShadow')
      .attr('dx', 0)
      .attr('dy', 1)
      .attr('stdDeviation', 2)
      .attr('flood-opacity', 0.15)

    // Arrow marker for directed edges
    defs
      .append('marker')
      .attr('id', 'kg-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#a1a1aa')

    const g = svgSel.append('g')

    // Zoom & pan
    const zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        const showLabels = event.transform.k >= labelShowZoomRef.current
        g.selectAll<SVGTextElement, SimNode>('g.nodes text')
          .attr('display', showLabels ? null : 'none')
      })

    svgSelRef.current = svgSel
    zoomBehaviorRef.current = zoomBehavior

    svgSel.call(zoomBehavior)

    // Auto-fit helper. Computes the bbox of current node positions and fits
    // them centered with 10% padding. Called both right after the simulation
    // is set up (so the new view appears centered immediately when filter or
    // focused-subgraph changes) and again when the simulation settles (in
    // case positions shifted during the layout pass).
    const runAutoFit = (animated: boolean) => {
      if (simNodes.length === 0) return
      // Hidden containers (a display:none tab) have zero client extent;
      // d3's zoom interpolator divides by it and emits NaN transforms.
      const rect = container.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) return
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const n of simNodes) {
        if (n.x == null || n.y == null) continue
        if (n.x < minX) minX = n.x
        if (n.y < minY) minY = n.y
        if (n.x > maxX) maxX = n.x
        if (n.y > maxY) maxY = n.y
      }
      if (!Number.isFinite(minX)) return
      const bbW = Math.max(1, maxX - minX)
      const bbH = Math.max(1, maxY - minY)
      const pad = 1.1
      // Clamp the lower bound to labelShowZoom so labels are visible at the
      // default fit. For large graphs this can clip outer nodes — the user
      // can pan/zoom out to see them.
      const fitScale = Math.min(width / (bbW * pad), height / (bbH * pad), 4)
      const scale = Math.max(fitScale, labelShowZoomRef.current)
      const cx = (minX + maxX) / 2
      const cy = (minY + maxY) / 2
      const tx = width / 2 - cx * scale
      const ty = height / 2 - cy * scale
      const target = d3.zoomIdentity.translate(tx, ty).scale(scale)
      if (animated) {
        svgSel.transition().duration(400).call(zoomBehavior.transform, target)
      } else {
        svgSel.call(zoomBehavior.transform, target)
      }
    }

    // Force simulation
    const simulation = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(config.linkDistance),
      )
      .force('charge', d3.forceManyBody<SimNode>().strength(chargeStrength))
      // Soft gravity toward origin instead of forceCenter, so disconnected
      // sub-clusters can drift apart and form visible gaps between them.
      // Strength is tiny (0.02) so it just keeps the layout from flying off.
      .force('grav-x', d3.forceX<SimNode>(0).strength(0.02))
      .force('grav-y', d3.forceY<SimNode>(0).strength(0.02))
      .force(
        'collide',
        // Collide radius is set from config (default 34) so it can be tuned
        // via the Advanced drawer. Larger collide pushes non-connected
        // neighbours further apart, carving visible gaps between clusters.
        d3.forceCollide<SimNode>().radius(config.collideRadius),
      )
      .force(
        'cluster-x',
        d3
          .forceX<SimNode>((d) => getRadialSeedPosition(d.id, d.data.nodeType).x)
          .strength(config.clusterStrength),
      )
      .force(
        'cluster-y',
        d3
          .forceY<SimNode>((d) => getRadialSeedPosition(d.id, d.data.nodeType).y)
          .strength(config.clusterStrength),
      )
      .alphaDecay(isLarge ? 0.03 : 0.0228)
      .velocityDecay(0.4)

    // When nodes have preserved positions, start with low alpha so they don't jump
    if (hasPreservedPositions) {
      simulation.alpha(0.15)
    }

    simulationRef.current = simulation

    // Immediate auto-fit so the new view (after a filter change, focus subgraph,
    // or initial mount) is centered without waiting for the simulation to settle.
    // Animated unless the simulation is starting cold (in which case nodes are
    // still settling and an animation here would visually fight the layout).
    runAutoFit(hasPreservedPositions)

    // Edge labels group (shown on hover)
    const edgeLabelGroup = g.append('g').attr('class', 'edge-labels')

    // Links
    const linkGroup = g.append('g').attr('class', 'links')
    const link = linkGroup
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', '#d4d4d8')
      .attr('stroke-opacity', hasPreservedPositions ? 0.6 : 0)
      .attr('stroke-width', 1)
      .attr('marker-end', 'url(#kg-arrow)')

    // Edge label elements (hidden by default)
    const edgeLabel = edgeLabelGroup
      .selectAll('text')
      .data(simLinks)
      .join('text')
      .text((d) => d.data.edgeType)
      .attr('font-size', 9)
      .attr('fill', '#71717a')
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')
      .attr('visibility', 'hidden')

    // Node groups
    const nodeGroup = g.append('g').attr('class', 'nodes')
    const node = nodeGroup
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'grab')
      .attr('role', 'button')
      .attr('tabindex', '0')
      .attr('aria-label', (d) => `${d.data.nodeType}: ${getNodeLabel(d.data)}`)

    // Node circles. Orphan nodes (no edges anywhere in the full graph) render
    // with a dashed grey outline + lower opacity so they're visually distinct
    // from connected nodes — useful when a single-type filter (e.g.
    // UserStory) hides the neighbours that gave context.
    node
      .append('circle')
      .attr('r', 14)
      .attr('fill', (d) => nodeColor(d.data.nodeType))
      .attr('stroke', (d) => ((fullEdgeCount.get(d.id) ?? 0) === 0 ? '#9CA3AF' : '#fff'))
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', (d) => ((fullEdgeCount.get(d.id) ?? 0) === 0 ? '3 2' : 'none'))
      .attr('opacity', (d) => ((fullEdgeCount.get(d.id) ?? 0) === 0 ? 0.45 : 1))
      .attr('filter', 'url(#kg-drop-shadow)')

    // Node labels
    node
      .append('text')
      .text((d) => {
        const label = getNodeLabel(d.data)
        return label.length > 24 ? label.slice(0, 22) + '…' : label
      })
      .attr('text-anchor', 'middle')
      .attr('dy', 28)
      .attr('font-size', 10)
      .attr('fill', (d) => ((fullEdgeCount.get(d.id) ?? 0) === 0 ? '#9CA3AF' : '#374151'))
      .attr('pointer-events', 'none')
      .attr('display', 'none') // hidden until auto-fit zoom event fires the zoom callback above

    // Edge-count badge — small numeric label in the top-right of connected
    // nodes. Hidden for orphans (their dashed outline already conveys 0).
    const badgeGroup = node
      .filter((d) => (fullEdgeCount.get(d.id) ?? 0) > 0)
      .append('g')
      .attr('class', 'edge-count-badge')
      .attr('transform', 'translate(11, -11)')
      .attr('pointer-events', 'none')
    badgeGroup
      .append('circle')
      .attr('r', 7)
      .attr('fill', '#1F2937')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
    badgeGroup
      .append('text')
      .text((d) => String(fullEdgeCount.get(d.id) ?? 0))
      .attr('text-anchor', 'middle')
      .attr('dy', 3)
      .attr('font-size', 8)
      .attr('font-weight', 600)
      .attr('fill', '#fff')

    // Highlight state
    let highlightedId: string | null = null

    function highlightConnected(nodeId: string) {
      highlightedId = nodeId
      const connectedIds = new Set<string>([nodeId])
      simLinks.forEach((l) => {
        const sId = typeof l.source === 'string' ? l.source : (l.source as SimNode).id
        const tId = typeof l.target === 'string' ? l.target : (l.target as SimNode).id
        if (sId === nodeId) connectedIds.add(tId)
        if (tId === nodeId) connectedIds.add(sId)
      })

      node
        .transition()
        .duration(300)
        .style('opacity', (d) => (connectedIds.has(d.id) ? 1 : 0.15))

      link
        .transition()
        .duration(300)
        .attr('stroke-opacity', (d) => {
          const sId = typeof d.source === 'string' ? d.source : (d.source as SimNode).id
          const tId = typeof d.target === 'string' ? d.target : (d.target as SimNode).id
          return sId === nodeId || tId === nodeId ? 0.8 : 0.05
        })

      // Show edge labels for connected edges
      edgeLabel.attr('visibility', (d) => {
        const sId = typeof d.source === 'string' ? d.source : (d.source as SimNode).id
        const tId = typeof d.target === 'string' ? d.target : (d.target as SimNode).id
        return sId === nodeId || tId === nodeId ? 'visible' : 'hidden'
      })
    }

    function clearHighlight() {
      highlightedId = null
      node.transition().duration(300).style('opacity', 1)
      link.transition().duration(300).attr('stroke-opacity', 0.6)
      edgeLabel.attr('visibility', 'hidden')
    }

    // Click on node
    node.on('click', (event, d) => {
      event.stopPropagation()
      onNodeSelectRef.current(d.data)
      highlightConnected(d.id)
    })

    // Keyboard support
    node.on('keydown', (event: KeyboardEvent, d) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onNodeSelectRef.current(d.data)
        highlightConnected(d.id)
      }
    })

    // Click background clears highlight AND notifies the parent so it can
    // dismiss the detail panel.
    svgSel.on('click', () => {
      if (highlightedId) clearHighlight()
      onBackgroundClickRef.current?.()
    })

    // Hover — use refs to avoid re-renders
    node
      .on('mouseenter', (event, d) => {
        d3.select(event.currentTarget).select('circle').attr('stroke-width', 3)
        const [px, py] = d3.pointer(event, container)
        const cRect = container.getBoundingClientRect()
        const clampedX = Math.min(px + 12, cRect.width - 220)
        const clampedY = Math.max(py - 12, 10)
        const edges = fullEdgeCount.get(d.id) ?? 0
        const conn = edges === 0 ? 'Orphan (no edges)' : `${edges} edge${edges === 1 ? '' : 's'}`
        showTooltip(clampedX, clampedY, `${getTooltipContent(d.data)}\n${conn}`)
      })
      .on('mouseleave', (event) => {
        d3.select(event.currentTarget).select('circle').attr('stroke-width', 2)
        hideTooltip()
      })

    // Drag
    const dragBehavior = d3
      .drag<SVGGElement, SimNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
        d3.select(event.sourceEvent.target).style('cursor', 'grabbing')
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
        d3.select(event.sourceEvent.target).style('cursor', 'grab')
      })

    node.call(dragBehavior)

    // Double-click to release pinned node
    node.on('dblclick', (event, d) => {
      event.stopPropagation()
      d.fx = null
      d.fy = null
      simulation.alpha(0.3).restart()
    })

    // Tick
    let tickCount = 0
    let linksShown = hasPreservedPositions

    simulation.on('tick', () => {
      tickCount++
      if (isLarge && tickCount % 2 !== 0) return

      if (!linksShown && simulation.alpha() < 0.5) {
        linksShown = true
        link.transition().duration(400).attr('stroke-opacity', 0.6)
      }

      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!)

      edgeLabel
        .attr('x', (d) => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', (d) => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2 - 4)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    simulation.on('end', () => {
      if (!linksShown) {
        linksShown = true
        link.attr('stroke-opacity', 0.6)
      }
      // Re-fit once the layout has settled, in case node positions shifted
      // meaningfully during the simulation pass.
      runAutoFit(true)
    })

    // Resize observer
    // Track the size we last reacted to so spurious sub-threshold resizes
    // (e.g. scrollbars appearing, internal layout reflows) don't re-heat the simulation.
    let lastObservedWidth = width
    let lastObservedHeight = height
    const RESIZE_THRESHOLD_PX = 20

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width: w, height: h } = entry.contentRect
      // 0x0 means the canvas is hidden (inactive tab) - keep the last real
      // size and don't reheat; the re-show resize handles the rest.
      if (w === 0 || h === 0) return
      svgSel.attr('width', w).attr('height', h)
      if (
        Math.abs(w - lastObservedWidth) < RESIZE_THRESHOLD_PX &&
        Math.abs(h - lastObservedHeight) < RESIZE_THRESHOLD_PX
      ) {
        return
      }
      lastObservedWidth = w
      lastObservedHeight = h
      simulation.alpha(0.1).restart()
    })
    resizeObserver.observe(container)

    return () => {
      simulation.stop()
      resizeObserver.disconnect()
      svgSel.on('.zoom', null)
      svgSel.on('click', null)
      node.on('click', null)
      node.on('keydown', null)
      node.on('mouseenter', null)
      node.on('mouseleave', null)
      node.on('dblclick', null)
      simulationRef.current = null
    }
  }, [filteredNodes, filteredEdges, fullEdgeCount, showTooltip, hideTooltip, nodeColor])

  // Re-heat effect: fires when reheatToken increments
  useEffect(() => {
    if (reheatToken === 0) return // initial render
    if (simulationRef.current) {
      simulationRef.current.alpha(0.5).restart()
    }
  }, [reheatToken])

  // Live-config effect: re-applies force params without rebuilding simulation
  useEffect(() => {
    const sim = simulationRef.current
    if (!sim) return
    const linkForce = sim.force('link') as d3.ForceLink<SimNode, SimLink> | undefined
    const chargeForce = sim.force('charge') as d3.ForceManyBody<SimNode> | undefined
    const collideForce = sim.force('collide') as d3.ForceCollide<SimNode> | undefined
    const clusterX = sim.force('cluster-x') as d3.ForceX<SimNode> | undefined
    const clusterY = sim.force('cluster-y') as d3.ForceY<SimNode> | undefined
    if (linkForce) linkForce.distance(config.linkDistance)
    if (chargeForce) chargeForce.strength(config.chargeStrength)
    if (collideForce) collideForce.radius(config.collideRadius)
    if (clusterX) clusterX.strength(config.clusterStrength)
    if (clusterY) clusterY.strength(config.clusterStrength)
    sim.alpha(0.3).restart()

    // Apply labelShowZoom immediately by recomputing label visibility
    // against the current zoom transform (otherwise sliding the threshold
    // does nothing until the user pans/zooms).
    const svg = svgSelRef.current
    if (svg) {
      const currentTransform = d3.zoomTransform(svg.node() as SVGSVGElement)
      const showLabels = currentTransform.k >= config.labelShowZoom
      svg
        .select('g')
        .selectAll<SVGTextElement, SimNode>('g.nodes text')
        .attr('display', showLabels ? null : 'none')
    }
  }, [config])

  // Build legend from visible types that exist in data
  const presentTypes = [...new Set(nodes.map((n) => n.nodeType))].sort()

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <svg ref={svgRef} className="h-full w-full" />

      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 max-w-xs rounded bg-zinc-800 px-3 py-2 text-xs text-white shadow-lg"
        style={{ display: 'none', left: 0, top: 0 }}
      />

      {filteredNodes.length > 0 && (
        <div className="absolute bottom-3 left-3 rounded border border-zinc-200 bg-white/90 px-3 py-2 text-xs shadow-sm">
          <div className="mb-1 font-medium text-zinc-600">Legend</div>
          {presentTypes.map((type) => (
            <div key={type} className="flex items-center gap-2 py-0.5">
              <svg width={14} height={14}>
                <circle
                  cx={7}
                  cy={7}
                  r={6}
                  fill={nodeColor(type)}
                  stroke="#fff"
                  strokeWidth={1}
                />
              </svg>
              <span className="text-zinc-600">{type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
