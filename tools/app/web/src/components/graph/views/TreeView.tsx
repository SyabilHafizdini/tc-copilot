import { useRef, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { buildHierarchy, type TreeDatum } from '../../../lib/hierarchy'
import { getNodeLabel, DEFAULT_NODE_COLOR } from '../../../lib/nodeStyle'
import { useNodeColor } from '../../../lib/TypeColorContext'

export interface TreeViewProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  variant: 'tidy' | 'radial'
  /** Label for the synthetic root when the graph has multiple roots. */
  graphTitle?: string
  onNodeSelect: (node: GraphNode) => void
  onBackgroundClick?: () => void
}

const ROW_HEIGHT = 26
const COLUMN_WIDTH = 210

function truncate(label: string): string {
  return label.length > 24 ? label.slice(0, 22) + '…' : label
}

export default function TreeView({
  nodes,
  edges,
  variant,
  graphTitle,
  onNodeSelect,
  onBackgroundClick,
}: TreeViewProps): ReactNode {
  const nodeColor = useNodeColor()
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const onNodeSelectRef = useRef(onNodeSelect)
  const onBackgroundClickRef = useRef(onBackgroundClick)
  onNodeSelectRef.current = onNodeSelect
  onBackgroundClickRef.current = onBackgroundClick

  const { root, crossEdgeCount } = useMemo(
    () => buildHierarchy(nodes, edges),
    [nodes, edges],
  )

  useEffect(() => {
    const container = containerRef.current
    const svgEl = svgRef.current
    if (!container || !svgEl) return

    const svgSel = d3.select(svgEl)
    svgSel.selectAll('*').remove()
    svgSel.on('.zoom', null)
    svgSel.on('click', null)

    if (nodes.length === 0) return

    const hierarchy = d3.hierarchy<TreeDatum>(root, (d) => d.children)

    if (variant === 'tidy') {
      d3.tree<TreeDatum>().nodeSize([ROW_HEIGHT, COLUMN_WIDTH])(hierarchy)
    } else {
      // Room per ring (labels are ~120px long) and per leaf along the rim.
      const radius = Math.max(
        180,
        hierarchy.height * 150,
        (hierarchy.leaves().length * 26) / (2 * Math.PI),
      )
      d3
        .tree<TreeDatum>()
        .size([2 * Math.PI, radius])
        .separation((a, b) => (a.parent === b.parent ? 1 : 2) / (a.depth || 1))(
        hierarchy,
      )
    }

    // Project layout coords to screen coords per variant.
    const point = (d: d3.HierarchyNode<TreeDatum>): [number, number] => {
      const { x, y } = d as unknown as { x: number; y: number }
      if (variant === 'tidy') return [y, x]
      return [Math.cos(x - Math.PI / 2) * y, Math.sin(x - Math.PI / 2) * y]
    }

    svgSel.attr('role', 'img').attr('aria-label', `${variant} tree visualization`)

    const g = svgSel.append('g')

    const zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 4])
      .on('zoom', (event) => g.attr('transform', event.transform))
    svgSel.call(zoomBehavior)

    // Links
    const linkPath =
      variant === 'tidy'
        ? (d: d3.HierarchyLink<TreeDatum>) =>
            d3.linkHorizontal()({
              source: point(d.source),
              target: point(d.target),
            })
        : (d: d3.HierarchyLink<TreeDatum>) =>
            d3
              .linkRadial<d3.HierarchyLink<TreeDatum>, d3.HierarchyNode<TreeDatum>>()
              .angle((n) => (n as unknown as { x: number }).x)
              .radius((n) => (n as unknown as { y: number }).y)(d)

    g.append('g')
      .attr('class', 'links')
      .selectAll('path')
      .data(hierarchy.links())
      .join('path')
      .attr('d', linkPath)
      .attr('fill', 'none')
      .attr('stroke', '#d4d4d8')
      .attr('stroke-width', 1.2)

    // Nodes
    const node = g
      .append('g')
      .attr('class', 'nodes')
      .selectAll<SVGGElement, d3.HierarchyNode<TreeDatum>>('g')
      .data(hierarchy.descendants())
      .join('g')
      .attr('class', 'node')
      .attr('transform', (d) => {
        const [px, py] = point(d)
        return `translate(${px},${py})`
      })

    const isSynthetic = (d: d3.HierarchyNode<TreeDatum>) => d.data.node === null

    node
      .append('circle')
      .attr('r', (d) => (isSynthetic(d) ? 5 : 6))
      .attr('fill', (d) =>
        d.data.node ? nodeColor(d.data.node.nodeType) : '#f4f4f5',
      )
      .attr('stroke', (d) => (isSynthetic(d) ? DEFAULT_NODE_COLOR : '#fff'))
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', (d) => (isSynthetic(d) ? '2 2' : 'none'))

    const real = node.filter((d) => !isSynthetic(d))
    real
      .style('cursor', 'pointer')
      .attr('role', 'button')
      .attr('tabindex', '0')
      .attr(
        'aria-label',
        (d) => `${d.data.node!.nodeType}: ${getNodeLabel(d.data.node!)}`,
      )

    real.append('title').text((d) => {
      const n = d.data.node!
      const via = d.data.edge ? `\nvia ${d.data.edge.edgeType}` : ''
      return `${getNodeLabel(n)}\nType: ${n.nodeType}${via}`
    })

    // Labels — leaves to the outside, internal nodes to the inside (gallery
    // convention), rotated along the ray in the radial variant.
    const label = node
      .append('text')
      .text((d) =>
        d.data.node ? truncate(getNodeLabel(d.data.node)) : (graphTitle ?? 'root'),
      )
      .attr('font-size', 10)
      .attr('fill', (d) => (isSynthetic(d) ? '#9CA3AF' : '#374151'))
      .attr('dy', '0.32em')
      .attr('paint-order', 'stroke')
      .attr('stroke', '#fff')
      .attr('stroke-width', 3)

    if (variant === 'tidy') {
      label
        .attr('x', (d) => (d.children ? -9 : 9))
        .attr('text-anchor', (d) => (d.children ? 'end' : 'start'))
    } else {
      label
        .attr('transform', (d) => {
          const { x } = d as unknown as { x: number }
          if (d.depth === 0) return null
          const deg = (x * 180) / Math.PI - 90
          return `rotate(${deg}) ${x >= Math.PI ? 'rotate(180)' : ''}`
        })
        .attr('x', (d) => {
          const { x } = d as unknown as { x: number }
          if (d.depth === 0) return 9
          return (x < Math.PI) === !d.children ? 9 : -9
        })
        .attr('text-anchor', (d) => {
          const { x } = d as unknown as { x: number }
          if (d.depth === 0) return 'start'
          return (x < Math.PI) === !d.children ? 'start' : 'end'
        })
    }

    // Declutter: labels live inside the zoomed group, so overlap is
    // scale-invariant — one greedy pass (pre-order, so shallower nodes win)
    // hides any label colliding with an already-kept one. Hidden names stay
    // reachable via the node tooltip. jsdom reports 0-size rects and is
    // skipped.
    {
      const kept: DOMRect[] = []
      const pad = 2
      label.each(function () {
        const r = this.getBoundingClientRect()
        if (!r || (r.width === 0 && r.height === 0)) return
        const collides = kept.some(
          (k) =>
            r.left - pad < k.right &&
            r.right + pad > k.left &&
            r.top - pad < k.bottom &&
            r.bottom + pad > k.top,
        )
        if (collides) d3.select(this).attr('display', 'none')
        else kept.push(r)
      })
    }

    real
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeSelectRef.current(d.data.node!)
      })
      .on('keydown', (event: KeyboardEvent, d) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onNodeSelectRef.current(d.data.node!)
        }
      })

    svgSel.on('click', () => onBackgroundClickRef.current?.())

    // Auto-fit: center the laid-out tree with padding. Skipped while the
    // container is hidden (0x0) — the ResizeObserver below fits on reveal.
    let fitted = false
    const runAutoFit = () => {
      const rect = container.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) return
      svgSel.attr('width', rect.width).attr('height', rect.height)
      const pts = hierarchy.descendants().map(point)
      const minX = Math.min(...pts.map((p) => p[0]))
      const maxX = Math.max(...pts.map((p) => p[0]))
      const minY = Math.min(...pts.map((p) => p[1]))
      const maxY = Math.max(...pts.map((p) => p[1]))
      // Pad the bbox for label text sticking out: tidy labels extend
      // horizontally; radial labels extend along rays in every direction.
      const padX = 240
      const padY = variant === 'radial' ? 240 : 60
      const bbW = Math.max(1, maxX - minX + padX)
      const bbH = Math.max(1, maxY - minY + padY)
      const scale = Math.min(rect.width / bbW, rect.height / bbH, 1.5)
      const cx = (minX + maxX) / 2
      const cy = (minY + maxY) / 2
      const target = d3.zoomIdentity
        .translate(rect.width / 2 - cx * scale, rect.height / 2 - cy * scale)
        .scale(scale)
      svgSel.call(zoomBehavior.transform, target)
      fitted = true
    }

    runAutoFit()

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      if (width === 0 || height === 0) return
      svgSel.attr('width', width).attr('height', height)
      if (!fitted) runAutoFit()
    })
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      svgSel.on('.zoom', null)
      svgSel.on('click', null)
      real.on('click', null)
      real.on('keydown', null)
    }
  }, [nodes, edges, root, variant, graphTitle, nodeColor])

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <svg ref={svgRef} className="h-full w-full" style={{ cursor: 'move' }} />
      {crossEdgeCount > 0 && (
        <div
          data-testid="cross-edge-caption"
          className="absolute bottom-3 left-3 rounded border border-zinc-200 bg-white/90 px-2 py-1 text-xs text-zinc-500 shadow-sm"
        >
          {crossEdgeCount} cross-link{crossEdgeCount === 1 ? '' : 's'} not drawn
          — tree shows one path per node
        </div>
      )}
    </div>
  )
}
