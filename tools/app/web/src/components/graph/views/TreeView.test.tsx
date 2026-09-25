import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TreeView from './TreeView'
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
  { edgeId: 'e2', edgeType: 'HAS_FIELD', fromNodeId: 'a', toNodeId: 'c', properties: {} },
]

describe.each(['tidy', 'radial'] as const)('TreeView (%s)', (variant) => {
  it('renders one selectable node group per graph node', () => {
    const { container } = render(
      <TreeView nodes={nodes} edges={edges} variant={variant} onNodeSelect={() => {}} />,
    )
    expect(container.querySelectorAll('g.node')).toHaveLength(3)
    expect(container.querySelectorAll('g.links path')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Page: Alpha' })).toBeInTheDocument()
  })

  it('clicking a node fires onNodeSelect', () => {
    const onSelect = vi.fn()
    render(<TreeView nodes={nodes} edges={edges} variant={variant} onNodeSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: 'Component: Beta' }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'b' }))
  })

  it('renders a synthetic root and cross-link caption for multi-root cyclic graphs', () => {
    const cyclic: GraphEdge[] = [
      ...edges,
      { edgeId: 'e3', edgeType: 'REL', fromNodeId: 'b', toNodeId: 'c', properties: {} },
    ]
    const lone: GraphNode = { nodeId: 'z', nodeType: 'State', displayLabel: 'Zed', properties: {} }
    const { container } = render(
      <TreeView
        nodes={[...nodes, lone]}
        edges={cyclic}
        variant={variant}
        graphTitle="My Graph"
        onNodeSelect={() => {}}
      />,
    )
    // 4 real nodes + synthetic root
    expect(container.querySelectorAll('g.node')).toHaveLength(5)
    expect(screen.getByTestId('cross-edge-caption')).toHaveTextContent('1 cross-link not drawn')
    expect(container.textContent).toContain('My Graph')
  })

  it("paints a node circle with the graph's custom palette", () => {
    const custom: GraphNode[] = [
      { nodeId: 'v', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
    ]
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <TreeView nodes={custom} edges={[]} variant={variant} onNodeSelect={() => {}} />
      </TypeColorProvider>,
    )
    const group = screen.getByRole('button', { name: 'VALIDATION_RULE: Rule' })
    expect(group.querySelector('circle')).toHaveAttribute('fill', '#EF4444')
  })
})
