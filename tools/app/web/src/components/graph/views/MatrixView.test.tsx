import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MatrixView from './MatrixView'
import type { GraphNode, GraphEdge } from '../../../lib/types'

const nodes: GraphNode[] = [
  { nodeId: 'a', nodeType: 'Page', displayLabel: 'Alpha', properties: {} },
  { nodeId: 'b', nodeType: 'Component', displayLabel: 'Beta', properties: {} },
]

const edges: GraphEdge[] = [
  { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  { edgeId: 'e2', edgeType: 'USES', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  { edgeId: 'e3', edgeType: 'CONTAINS', fromNodeId: 'b', toNodeId: 'a', properties: {} },
]

describe('MatrixView', () => {
  it('renders one cell per source→target pair with an edge-type legend', () => {
    const { container } = render(
      <MatrixView nodes={nodes} edges={edges} onNodeSelect={() => {}} />,
    )
    // a→b (2 parallel edges merged) and b→a
    expect(container.querySelectorAll('g.cells rect')).toHaveLength(2)
    expect(screen.getByText('CONTAINS')).toBeInTheDocument()
    expect(screen.getByText('USES')).toBeInTheDocument()
  })

  it('clicking a row label selects the node', () => {
    const onSelect = vi.fn()
    render(<MatrixView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: 'Page: Alpha' }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'a' }))
  })

  it('shows the empty state with no nodes', () => {
    render(<MatrixView nodes={[]} edges={[]} onNodeSelect={() => {}} />)
    expect(screen.getByText('No graph data available.')).toBeInTheDocument()
  })
})
