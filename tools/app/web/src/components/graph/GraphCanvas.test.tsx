import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import GraphCanvas from './GraphCanvas'
import type { GraphNode, GraphEdge } from '../../lib/types'
import { DEFAULT_GRAPH_CONFIG } from '../../lib/useGraphConfig'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'

const nodes: GraphNode[] = [
  { nodeId: 'v', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
]
const edges: GraphEdge[] = []

function renderCanvas() {
  return render(
    <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        visibleTypes={new Set(['VALIDATION_RULE'])}
        searchQuery=""
        visibleEdgeTypes={new Set()}
        onNodeSelect={() => {}}
        config={DEFAULT_GRAPH_CONFIG}
        reheatToken={0}
      />
    </TypeColorProvider>,
  )
}

describe('GraphCanvas legend', () => {
  it("paints the legend swatch with the graph's custom palette", () => {
    renderCanvas()
    const legendRow = screen.getByText('VALIDATION_RULE').closest('div')!
    expect(legendRow.querySelector('circle')).toHaveAttribute('fill', '#EF4444')
  })
})

describe('GraphCanvas D3 node fill', () => {
  // The force simulation effect bails out early when the container reports a
  // 0x0 rect (jsdom's default), so the node circles never render without a
  // stubbed layout size.
  beforeEach(() => {
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 800,
      height: 600,
      top: 0,
      left: 0,
      right: 800,
      bottom: 600,
      x: 0,
      y: 0,
      toJSON() {},
    } as DOMRect)
    // The circle's fill is set synchronously while the D3 selection is built,
    // before the force simulation ticks. Freeze time so the simulation never
    // advances past that point — letting it run for real risks it settling
    // and firing an animated re-fit transition that jsdom's SVG (no working
    // viewBox.baseVal) can't handle, an unrelated pre-existing jsdom/d3-zoom
    // incompatibility that has nothing to do with what this test checks.
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("paints a node circle with the graph's custom palette", () => {
    const { container } = renderCanvas()
    const circle = container.querySelector('g.nodes g.node circle')
    expect(circle).toHaveAttribute('fill', '#EF4444')
  })
})
