import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IndentedTreeView from './IndentedTreeView'
import type { GraphNode, GraphEdge } from '../../../lib/types'
import { TypeColorProvider } from '../../../lib/TypeColorContext'
import { resolveTypeColors } from '../../../lib/nodeStyle'

const nodes: GraphNode[] = [
  { nodeId: 'root', nodeType: 'Page', displayLabel: 'Root Page', properties: {} },
  { nodeId: 'child', nodeType: 'Component', displayLabel: 'Child Comp', properties: {} },
  { nodeId: 'leaf', nodeType: 'Field', displayLabel: 'Leaf Field', properties: {} },
]

const edges: GraphEdge[] = [
  { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'root', toNodeId: 'child', properties: {} },
  { edgeId: 'e2', edgeType: 'HAS_FIELD', fromNodeId: 'child', toNodeId: 'leaf', properties: {} },
]

describe('IndentedTreeView', () => {
  it('renders every node as a row with type badge and incoming edge type', () => {
    render(<IndentedTreeView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)
    expect(screen.getByText('Root Page')).toBeInTheDocument()
    expect(screen.getByText('Child Comp')).toBeInTheDocument()
    expect(screen.getByText('Leaf Field')).toBeInTheDocument()
    expect(screen.getByText('via CONTAINS')).toBeInTheDocument()
    expect(screen.getByText('via HAS_FIELD')).toBeInTheDocument()
  })

  it('collapses and re-expands a subtree via the chevron', () => {
    render(<IndentedTreeView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Collapse Root Page' }))
    expect(screen.queryByText('Child Comp')).not.toBeInTheDocument()
    expect(screen.queryByText('Leaf Field')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand Root Page' }))
    expect(screen.getByText('Child Comp')).toBeInTheDocument()
  })

  it('collapse all / expand all toggle every parent', () => {
    render(<IndentedTreeView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Collapse all' }))
    expect(screen.queryByText('Child Comp')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand all' }))
    expect(screen.getByText('Leaf Field')).toBeInTheDocument()
  })

  it('clicking a row selects the node', () => {
    const onSelect = vi.fn()
    render(<IndentedTreeView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)
    fireEvent.click(screen.getByTestId('indented-row-child'))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'child' }))
  })

  it('shows the cross-link caption when edges are not representable', () => {
    const extraEdge: GraphEdge = {
      edgeId: 'e3', edgeType: 'REL', fromNodeId: 'leaf', toNodeId: 'root', properties: {},
    }
    render(
      <IndentedTreeView nodes={nodes} edges={[...edges, extraEdge]} onNodeSelect={() => {}} />,
    )
    expect(screen.getByTestId('cross-edge-caption')).toHaveTextContent('1 cross-link not shown')
  })

  it('shows the empty state with no nodes', () => {
    render(<IndentedTreeView nodes={[]} edges={[]} onNodeSelect={() => {}} />)
    expect(screen.getByText('No graph data available.')).toBeInTheDocument()
  })

  it("paints the row swatch with the graph's custom palette", () => {
    const custom: GraphNode[] = [
      { nodeId: 'v', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
    ]
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <IndentedTreeView nodes={custom} edges={[]} onNodeSelect={() => {}} />
      </TypeColorProvider>,
    )
    const row = screen.getByTestId('indented-row-v')
    expect(row.querySelector('.rounded-full')).toHaveStyle({ backgroundColor: '#EF4444' })
  })
})
