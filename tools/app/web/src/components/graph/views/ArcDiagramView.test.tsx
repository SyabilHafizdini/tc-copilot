import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import ArcDiagramView from './ArcDiagramView'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { TypeColorProvider } from '../../../lib/TypeColorContext'
import { resolveTypeColors } from '../../../lib/nodeStyle'

const nodes: GraphNode[] = [
  { nodeId: 'a', nodeType: 'Page', displayLabel: 'Alpha', properties: {} },
  { nodeId: 'b', nodeType: 'Component', displayLabel: 'Beta', properties: {} },
  { nodeId: 'c', nodeType: 'Field', displayLabel: 'Gamma', properties: {} },
]

const edges: GraphEdge[] = [
  { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  { edgeId: 'e2', edgeType: 'HAS_FIELD', fromNodeId: 'b', toNodeId: 'c', properties: {} },
  { edgeId: 'e3', edgeType: 'SELF', fromNodeId: 'c', toNodeId: 'c', properties: {} },
]

describe('ArcDiagramView', () => {
  it('renders a labeled point per node and an arc per edge (self-loops as circles)', () => {
    const { container } = render(
      <ArcDiagramView nodes={nodes} edges={edges} onNodeSelect={() => {}} />,
    )
    expect(container.querySelectorAll('g.nodes g')).toHaveLength(3)
    expect(container.querySelectorAll('g.arcs path')).toHaveLength(2)
    expect(container.querySelectorAll('g.arcs circle')).toHaveLength(1)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
  })

  it('clicking a node selects it', () => {
    const onSelect = vi.fn()
    render(<ArcDiagramView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: 'Component: Beta' }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'b' }))
  })

  it('shows the empty state with no nodes', () => {
    render(<ArcDiagramView nodes={[]} edges={[]} onNodeSelect={() => {}} />)
    expect(screen.getByText('No graph data available.')).toBeInTheDocument()
  })

  it("paints the node point with the graph's custom palette", () => {
    const custom: GraphNode[] = [
      { nodeId: 'v', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
    ]
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <ArcDiagramView nodes={custom} edges={[]} onNodeSelect={() => {}} />
      </TypeColorProvider>,
    )
    const group = screen.getByRole('button', { name: 'VALIDATION_RULE: Rule' })
    expect(group.querySelector('circle')).toHaveAttribute('fill', '#EF4444')
  })
})
