import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import TableView from './TableView'
import type { GraphNode, GraphEdge } from '../../../lib/types'

const nodes: GraphNode[] = [
  {
    nodeId: 'a',
    nodeType: 'Page',
    displayLabel: 'Alpha',
    properties: { route: '/a', auth: false },
  },
  { nodeId: 'b', nodeType: 'Component', displayLabel: 'Beta', properties: {} },
  { nodeId: 'c', nodeType: 'Service', displayLabel: 'Gamma', properties: { port: 8080 } },
]

// degrees: a = 0 in / 2 out, b = 1 in / 1 out, c = 2 in / 0 out
const edges: GraphEdge[] = [
  { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  { edgeId: 'e2', edgeType: 'USES', fromNodeId: 'a', toNodeId: 'c', properties: {} },
  { edgeId: 'e3', edgeType: 'CALLS', fromNodeId: 'b', toNodeId: 'c', properties: {} },
]

const withContent: GraphNode[] = [
  ...nodes,
  {
    nodeId: 'd',
    nodeType: 'Page',
    displayLabel: 'Delta',
    properties: {},
    content: '# Delta\n\nSome markdown.',
  },
]

const rowOrder = (): (string | undefined)[] =>
  screen.getAllByTestId(/^table-row-/).map((r) => r.dataset.testid)

describe('TableView', () => {
  it('renders one row per node with id, type, label, degrees and prop count', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    expect(screen.getAllByTestId(/^table-row-/)).toHaveLength(3)

    const row = screen.getByTestId('table-row-a')
    expect(within(row).getByTestId('cell-id')).toHaveTextContent('a')
    expect(within(row).getByTestId('cell-type')).toHaveTextContent('Page')
    expect(within(row).getByTestId('cell-label')).toHaveTextContent('Alpha')
    expect(within(row).getByTestId('cell-in')).toHaveTextContent('0')
    expect(within(row).getByTestId('cell-out')).toHaveTextContent('2')
    expect(within(row).getByTestId('cell-props')).toHaveTextContent('2')
  })

  it('counts degrees from the edges it is given', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    const c = screen.getByTestId('table-row-c')
    expect(within(c).getByTestId('cell-in')).toHaveTextContent('2')
    expect(within(c).getByTestId('cell-out')).toHaveTextContent('0')
  })

  it('shows zero in/out degree for a node absent from every edge', () => {
    const isolated: GraphNode[] = [
      ...nodes,
      { nodeId: 'iso', nodeType: 'Page', displayLabel: 'Isolated', properties: {} },
    ]
    render(<TableView nodes={isolated} edges={edges} onNodeSelect={() => {}} />)

    const row = screen.getByTestId('table-row-iso')
    expect(within(row).getByTestId('cell-in')).toHaveTextContent('0')
    expect(within(row).getByTestId('cell-out')).toHaveTextContent('0')
  })

  it('clicking a row selects the node', () => {
    const onSelect = vi.fn()
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)

    fireEvent.click(screen.getByTestId('table-row-b'))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'b' }))
  })

  it('exposes each row label as a keyboard-reachable button', () => {
    const onSelect = vi.fn()
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: 'Page: Alpha' }))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'a' }))
  })

  it('renders the source order by default', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    expect(rowOrder()).toEqual(['table-row-a', 'table-row-b', 'table-row-c'])
  })

  it('shows an empty state when the filters hide every node', () => {
    render(<TableView nodes={[]} edges={[]} onNodeSelect={() => {}} />)

    expect(screen.getByText('No nodes match the current filters.')).toBeInTheDocument()
  })

  it('sorts by label ascending, then descending, on repeated header clicks', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Label' }))
    expect(rowOrder()).toEqual(['table-row-a', 'table-row-b', 'table-row-c'])

    fireEvent.click(screen.getByRole('button', { name: 'Label' }))
    expect(rowOrder()).toEqual(['table-row-c', 'table-row-b', 'table-row-a'])
  })

  it('resets to ascending when switching sort column, not inheriting the previous descending direction', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Label' })) // ascending
    fireEvent.click(screen.getByRole('button', { name: 'Label' })) // descending
    expect(rowOrder()).toEqual(['table-row-c', 'table-row-b', 'table-row-a'])

    fireEvent.click(screen.getByRole('button', { name: 'Type' }))
    expect(
      screen.getByRole('columnheader', { name: 'Type' }),
    ).toHaveAttribute('aria-sort', 'ascending')
    // Component < Page < Service alphabetically — b, a, c.
    expect(rowOrder()).toEqual(['table-row-b', 'table-row-a', 'table-row-c'])
  })

  it('marks the active sort column with aria-sort', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    const header = (): HTMLElement =>
      screen.getByRole('columnheader', { name: 'Type' })

    expect(header()).toHaveAttribute('aria-sort', 'none')
    fireEvent.click(screen.getByRole('button', { name: 'Type' }))
    expect(header()).toHaveAttribute('aria-sort', 'ascending')
    fireEvent.click(screen.getByRole('button', { name: 'Type' }))
    expect(header()).toHaveAttribute('aria-sort', 'descending')
  })

  it('sorts degree columns numerically, not lexically', () => {
    // hub has in-degree 10, mid has 9 — a lexical sort would rank "9" above "10"
    const many: GraphNode[] = [
      { nodeId: 'hub', nodeType: 'Page', displayLabel: 'Hub', properties: {} },
      { nodeId: 'mid', nodeType: 'Page', displayLabel: 'Mid', properties: {} },
    ]
    const manyEdges: GraphEdge[] = []
    for (let i = 0; i < 10; i++) {
      many.push({
        nodeId: `s${i}`,
        nodeType: 'Leaf',
        displayLabel: `S${i}`,
        properties: {},
      })
      manyEdges.push({
        edgeId: `x${i}`,
        edgeType: 'R',
        fromNodeId: `s${i}`,
        toNodeId: 'hub',
        properties: {},
      })
    }
    for (let i = 0; i < 9; i++) {
      manyEdges.push({
        edgeId: `y${i}`,
        edgeType: 'R',
        fromNodeId: `s${i}`,
        toNodeId: 'mid',
        properties: {},
      })
    }

    render(<TableView nodes={many} edges={manyEdges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'In' })) // ascending
    fireEvent.click(screen.getByRole('button', { name: 'In' })) // descending

    expect(rowOrder().slice(0, 2)).toEqual(['table-row-hub', 'table-row-mid'])
  })

  it('sorts by property count numerically', () => {
    // a = 2 props, b = 0, c = 1
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Props' }))
    expect(rowOrder()).toEqual(['table-row-b', 'table-row-c', 'table-row-a'])
  })

  it('keeps source order for rows that tie on the sort key', () => {
    const tied: GraphNode[] = [
      { nodeId: 'p2', nodeType: 'Page', displayLabel: 'Second', properties: {} },
      { nodeId: 'p1', nodeType: 'Page', displayLabel: 'First', properties: {} },
      { nodeId: 'c1', nodeType: 'Component', displayLabel: 'Comp', properties: {} },
    ]
    render(<TableView nodes={tied} edges={[]} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Type' }))

    // Component sorts ahead of Page; the two Pages keep their source order,
    // which only holds if the comparator is stable.
    expect(rowOrder()).toEqual(['table-row-c1', 'table-row-p2', 'table-row-p1'])
  })

  it('does not select a node when a sort header is clicked', () => {
    const onSelect = vi.fn()
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: 'ID' }))

    expect(onSelect).not.toHaveBeenCalled()
  })

  it('expands a row to show its properties', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    expect(screen.queryByTestId('table-detail-a')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand Alpha' }))

    const detail = screen.getByTestId('table-detail-a')
    expect(within(detail).getByText('route')).toBeInTheDocument()
    expect(within(detail).getByText('/a')).toBeInTheDocument()
    expect(within(detail).getByText('auth')).toBeInTheDocument()
    expect(within(detail).getByText('false')).toBeInTheDocument()
  })

  it('lists outgoing and incoming edges in the expanded row', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Beta' }))

    const detail = screen.getByTestId('table-detail-b')
    expect(within(detail).getByRole('button', { name: '→ CALLS → Gamma (c)' })).toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: '← CONTAINS ← Alpha (a)' })).toBeInTheDocument()
  })

  it('clicking a neighbour in the expanded row selects that neighbour', () => {
    const onSelect = vi.fn()
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Beta' }))
    onSelect.mockClear()
    fireEvent.click(screen.getByRole('button', { name: '→ CALLS → Gamma (c)' }))

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ nodeId: 'c' }))
  })

  it('does not select the row when the chevron is clicked', () => {
    const onSelect = vi.fn()
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Alpha' }))

    expect(onSelect).not.toHaveBeenCalled()
    expect(screen.getByTestId('table-detail-a')).toBeInTheDocument()
  })

  it('collapses an expanded row and keeps several rows open at once', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Expand Beta' }))
    expect(screen.getByTestId('table-detail-a')).toBeInTheDocument()
    expect(screen.getByTestId('table-detail-b')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Alpha' }))
    expect(screen.queryByTestId('table-detail-a')).not.toBeInTheDocument()
    expect(screen.getByTestId('table-detail-b')).toBeInTheDocument()
  })

  it('shows empty messages for a node with no properties and no edges', () => {
    const lonely: GraphNode[] = [
      { nodeId: 'z', nodeType: 'Page', displayLabel: 'Zeta', properties: {} },
    ]
    render(<TableView nodes={lonely} edges={[]} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Zeta' }))

    const detail = screen.getByTestId('table-detail-z')
    expect(within(detail).getByText('No properties')).toBeInTheDocument()
    expect(within(detail).getByText('No connected edges')).toBeInTheDocument()
  })

  it('marks a node that carries markdown content', () => {
    render(<TableView nodes={withContent} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Delta' }))

    expect(screen.getByTestId('table-detail-d')).toHaveTextContent('content · 23 chars')
  })

  it('expand all opens every row, collapse all closes every row', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand all' }))
    expect(screen.getByTestId('table-detail-a')).toBeInTheDocument()
    expect(screen.getByTestId('table-detail-b')).toBeInTheDocument()
    expect(screen.getByTestId('table-detail-c')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse all' }))
    expect(screen.queryByTestId('table-detail-a')).not.toBeInTheDocument()
    expect(screen.queryByTestId('table-detail-b')).not.toBeInTheDocument()
    expect(screen.queryByTestId('table-detail-c')).not.toBeInTheDocument()
  })

  it('lets a single chevron collapse one row after expand all', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand all' }))
    // The bulk buttons and the per-row chevrons drive the same state, so the
    // chevron must read as "Collapse" and close only its own row.
    fireEvent.click(screen.getByRole('button', { name: 'Collapse Alpha' }))

    expect(screen.queryByTestId('table-detail-a')).not.toBeInTheDocument()
    expect(screen.getByTestId('table-detail-b')).toBeInTheDocument()
  })

  it('keeps a row expanded across a re-sort', () => {
    render(<TableView nodes={nodes} edges={edges} onNodeSelect={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Expand Alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Label' }))
    fireEvent.click(screen.getByRole('button', { name: 'Label' }))

    expect(screen.getByTestId('table-detail-a')).toBeInTheDocument()
  })
})
