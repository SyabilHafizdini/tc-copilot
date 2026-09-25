import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import Viewer from './Viewer'
import type { GraphDocument } from './lib/types'

const graph: GraphDocument = {
  meta: { title: 'Switcher Test' },
  nodes: [
    { nodeId: 'a', nodeType: 'Page', displayLabel: 'Alpha', properties: {} },
    { nodeId: 'b', nodeType: 'Component', displayLabel: 'Beta', properties: {} },
  ],
  edges: [
    { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  ],
}

describe('Viewer view switching', () => {
  it('defaults to the force view with advanced controls', () => {
    render(<Viewer graph={graph} />)
    expect(screen.getByRole('button', { name: 'Force' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /advanced/i })).toBeInTheDocument()
  })

  it('switches to the indented tree and hides force-only controls', () => {
    render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    expect(screen.getByTestId('indented-tree')).toBeInTheDocument()
    // Scoped to the tree: the summary bar's "most connected" card also renders
    // a node label, so an unscoped getByText would match twice.
    expect(within(screen.getByTestId('indented-tree')).getByText('Alpha')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /advanced/i })).not.toBeInTheDocument()
  })

  it('switches to tidy and radial tree views', () => {
    const { container } = render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Tidy tree' }))
    expect(container.querySelector('svg[aria-label="tidy tree visualization"]')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Radial' }))
    expect(container.querySelector('svg[aria-label="radial tree visualization"]')).toBeInTheDocument()
  })

  it('shows a description of the active view and updates it on switch', () => {
    render(<Viewer graph={graph} />)
    expect(screen.getByTestId('view-description')).toHaveTextContent(/force-directed/i)
    fireEvent.click(screen.getByRole('button', { name: 'Matrix' }))
    expect(screen.getByTestId('view-description')).toHaveTextContent(/adjacency matrix/i)
  })

  it('switches to arc and matrix views', () => {
    render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Arc' }))
    expect(screen.getByTestId('arc-diagram')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Matrix' }))
    expect(screen.getByTestId('matrix-view')).toBeInTheDocument()
  })

  it('selecting a node in a tree view opens the detail panel', () => {
    render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    fireEvent.click(screen.getByTestId('indented-row-b'))
    expect(screen.getByTestId('graph-detail-panel')).toBeInTheDocument()
  })

  it('offers seven view modes', () => {
    render(<Viewer graph={graph} />)
    const group = screen.getByRole('group', { name: 'Graph view' })
    expect(within(group).getAllByRole('button')).toHaveLength(7)
  })

  it('switches to the table view', () => {
    render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByTestId('table-view')).toBeInTheDocument()
    expect(screen.getByTestId('table-row-a')).toBeInTheDocument()
    expect(screen.getByTestId('table-row-b')).toBeInTheDocument()
  })

  it('selecting a node in the table opens the detail panel', () => {
    render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Table' }))
    fireEvent.click(screen.getByTestId('table-row-b'))
    expect(screen.getByTestId('graph-detail-panel')).toBeInTheDocument()
  })
})

const tableFilterGraph: GraphDocument = {
  meta: { title: 'Table Filter Test' },
  nodes: [
    { nodeId: 'a', nodeType: 'Page', displayLabel: 'Alpha', properties: {} },
    { nodeId: 'b', nodeType: 'Page', displayLabel: 'Beta', properties: {} },
    { nodeId: 'c', nodeType: 'Component', displayLabel: 'Gamma', properties: {} },
  ],
  edges: [
    { edgeId: 'e1', edgeType: 'CALLS', fromNodeId: 'a', toNodeId: 'c', properties: {} },
    { edgeId: 'e2', edgeType: 'CALLS', fromNodeId: 'b', toNodeId: 'c', properties: {} },
    { edgeId: 'e3', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  ],
}

describe('Viewer table view filtering', () => {
  it('toggling a node type pill off removes its rows and drops a surviving row\'s degree', () => {
    render(<Viewer graph={tableFilterGraph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Table' }))

    // Initial rows: a, b, c all present; a has out-degree 2 (-> c, -> b).
    expect(screen.getByTestId('table-row-a')).toBeInTheDocument()
    expect(screen.getByTestId('table-row-b')).toBeInTheDocument()
    expect(screen.getByTestId('table-row-c')).toBeInTheDocument()
    expect(within(screen.getByTestId('table-row-a')).getByTestId('cell-out')).toHaveTextContent('2')

    // Toggle the Component pill off — node c (and its edges) drop out of the filter.
    fireEvent.click(screen.getByRole('button', { name: /^Component$/ }))

    expect(screen.queryByTestId('table-row-c')).not.toBeInTheDocument()
    expect(screen.getByTestId('table-row-a')).toBeInTheDocument()
    expect(screen.getByTestId('table-row-b')).toBeInTheDocument()
    // a's out-degree drops from 2 to 1 now that a -> c is filtered out.
    expect(within(screen.getByTestId('table-row-a')).getByTestId('cell-out')).toHaveTextContent('1')
  })
})

describe('Viewer about panel', () => {
  it('opens from the header and explains the graph and its presets', () => {
    render(<Viewer graph={presetGraph} />)
    expect(screen.queryByTestId('about-panel')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^About$/ }))

    const panel = within(screen.getByTestId('about-panel'))
    expect(panel.getByText('Preset Test')).toBeInTheDocument()
    expect(screen.getByTestId('about-preset-Only pages')).toBeInTheDocument()
    expect(screen.getByTestId('about-preset-Everything else')).toBeInTheDocument()
  })

  it('closes again', () => {
    render(<Viewer graph={presetGraph} />)
    fireEvent.click(screen.getByRole('button', { name: /^About$/ }))
    fireEvent.click(screen.getByRole('button', { name: /close about/i }))

    expect(screen.queryByTestId('about-panel')).not.toBeInTheDocument()
  })
})

describe('Viewer summary bar', () => {
  it('renders above every view, not just the table', () => {
    render(<Viewer graph={tableFilterGraph} />)

    // Force is the default view; the bar is outside the view container.
    expect(screen.getByTestId('metric-cards')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    expect(screen.getByTestId('metric-cards')).toBeInTheDocument()
  })

  it('tracks the filtered set while the denominator stays the whole graph', () => {
    render(<Viewer graph={tableFilterGraph} />)
    // The bar ships collapsed; open it to read the cards.
    fireEvent.click(screen.getByRole('button', { name: /Summary/ }))

    expect(within(screen.getByTestId('metric-nodes')).getByText('3 of 3')).toBeInTheDocument()

    // Dropping the Component pill removes node c and both edges touching it.
    fireEvent.click(screen.getByRole('button', { name: /^Component$/ }))

    expect(within(screen.getByTestId('metric-nodes')).getByText('2 of 3')).toBeInTheDocument()
    expect(within(screen.getByTestId('metric-edges')).getByText('1 of 3')).toBeInTheDocument()
  })
})

const presetGraph: GraphDocument = {
  meta: { title: 'Preset Test' },
  presets: [
    { name: 'Only pages', nodeTypes: ['Page'], default: true },
    { name: 'Everything else', nodeTypes: ['Component'] },
  ],
  nodes: [
    { nodeId: 'a', nodeType: 'Page', displayLabel: 'Alpha', properties: {} },
    { nodeId: 'b', nodeType: 'Component', displayLabel: 'Beta', properties: {} },
  ],
  edges: [
    { edgeId: 'e1', edgeType: 'CONTAINS', fromNodeId: 'a', toNodeId: 'b', properties: {} },
  ],
}

describe('Viewer presets', () => {
  it('renders no preset bar and no badge when the graph has no presets', () => {
    render(<Viewer graph={graph} />)
    expect(screen.queryByTestId('preset-bar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('active-preset-badge')).not.toBeInTheDocument()
  })

  it('applies the default preset on mount WITHOUT changing the view', () => {
    render(<Viewer graph={presetGraph} />)
    // the default preset's filter is applied: chip active + badge shown...
    expect(screen.getByRole('button', { name: 'Only pages' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('active-preset-badge')).toHaveTextContent('Only pages')
    // ...but the view stays the default Force view — presets never switch views.
    expect(screen.getByRole('button', { name: 'Force' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('the default preset filters the graph (only Page nodes visible)', () => {
    render(<Viewer graph={presetGraph} />)
    // switch to a label-rendering view to read node text; the filter persists.
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.queryByText('Beta')).not.toBeInTheDocument()
  })

  it('clicking a preset filters without changing the current view', () => {
    render(<Viewer graph={presetGraph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    fireEvent.click(screen.getByRole('button', { name: 'Everything else' }))
    // still in the Indented view the user picked...
    expect(screen.getByRole('button', { name: 'Indented' })).toHaveAttribute('aria-pressed', 'true')
    // ...now showing the Component slice, and the badge names it.
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.queryByText('Alpha')).not.toBeInTheDocument()
    expect(screen.getByTestId('active-preset-badge')).toHaveTextContent('Everything else')
  })

  it('clearing the preset via the badge restores all types and hides the badge', () => {
    render(<Viewer graph={presetGraph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    fireEvent.click(screen.getByRole('button', { name: /clear preset/i }))
    expect(screen.queryByTestId('active-preset-badge')).not.toBeInTheDocument()
    const tree = within(screen.getByTestId('indented-tree'))
    expect(tree.getByText('Alpha')).toBeInTheDocument()
    expect(tree.getByText('Beta')).toBeInTheDocument()
  })

  it('Reset re-applies the default preset when one exists', () => {
    render(<Viewer graph={presetGraph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indented' }))
    // move away from the default by selecting the other preset
    fireEvent.click(screen.getByRole('button', { name: 'Everything else' }))
    expect(screen.getByText('Beta')).toBeInTheDocument()
    // Reset should return to the default 'Only pages' slice (Alpha only).
    // Exact name avoids matching the badge's "Clear preset" button ("p·reset").
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.getByRole('button', { name: 'Only pages' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.queryByText('Beta')).not.toBeInTheDocument()
  })
})

describe('Viewer per-graph type colors', () => {
  const custom: GraphDocument = {
    meta: { title: 'Custom', typeColors: { VALIDATION_RULE: '#EF4444' } },
    nodes: [
      { nodeId: 'v1', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
      { nodeId: 'u1', nodeType: 'UNCOLORED', displayLabel: 'Other', properties: {} },
    ],
    edges: [],
  }

  function typeDots(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll('[data-testid="cell-type"] span span'))
  }

  it('paints a declared custom type with its color and leaves undeclared types gray', () => {
    const { container } = render(<Viewer graph={custom} />)
    fireEvent.click(screen.getByRole('button', { name: 'Table' }))
    const dots = typeDots(container)
    expect(dots).toHaveLength(2)
    expect(dots[0]).toHaveStyle({ backgroundColor: '#EF4444' })
    expect(dots[1]).toHaveStyle({ backgroundColor: '#9CA3AF' })
  })

  it('leaves a graph without typeColors on the built-in palette', () => {
    const { container } = render(<Viewer graph={graph} />)
    fireEvent.click(screen.getByRole('button', { name: 'Table' }))
    expect(typeDots(container)[0]).toHaveStyle({ backgroundColor: '#3B82F6' })
  })

  it('keeps two simultaneously mounted Viewers on their own palettes, even when only a leaf below the provider re-renders', () => {
    const other: GraphDocument = {
      ...custom,
      meta: { title: 'Other', typeColors: { VALIDATION_RULE: '#00FF00' } },
    }
    render(
      <>
        <div data-testid="left"><Viewer graph={custom} /></div>
        <div data-testid="right"><Viewer graph={other} /></div>
      </>,
    )
    // Left is earlier in the tree, so switch it to Table first and right second —
    // under a module-global palette implementation, the right Viewer's provider
    // would be the last one to run, leaving the global holding right's colors.
    const [leftTableBtn, rightTableBtn] = screen.getAllByRole('button', { name: 'Table' })
    fireEvent.click(leftTableBtn)
    fireEvent.click(rightTableBtn)
    expect(typeDots(screen.getByTestId('left'))[0]).toHaveStyle({ backgroundColor: '#EF4444' })
    expect(typeDots(screen.getByTestId('right'))[0]).toHaveStyle({ backgroundColor: '#00FF00' })

    // Re-render ONLY the left Viewer's TableView leaf: expanding a row is state
    // local to TableView, not lifted to Viewer, so left's TypeColorProvider does
    // NOT re-run for this click. A module-global palette would read whichever
    // provider ran last (right's, from the clicks above) during this repaint and
    // leak green into the left dot; per-instance context does not.
    const leftRow = within(screen.getByTestId('left')).getByTestId('table-row-v1')
    fireEvent.click(within(leftRow).getByRole('button', { name: /^Expand/ }))
    expect(typeDots(screen.getByTestId('left'))[0]).toHaveStyle({ backgroundColor: '#EF4444' })
    expect(typeDots(screen.getByTestId('right'))[0]).toHaveStyle({ backgroundColor: '#00FF00' })
  })
})

describe('Viewer per-graph type colors — Matrix view', () => {
  const custom: GraphDocument = {
    meta: { title: 'Custom', typeColors: { VALIDATION_RULE: '#EF4444' } },
    nodes: [
      { nodeId: 'v1', nodeType: 'VALIDATION_RULE', displayLabel: 'Rule', properties: {} },
      { nodeId: 'u1', nodeType: 'UNCOLORED', displayLabel: 'Other', properties: {} },
    ],
    edges: [],
  }

  it('paints the row-label dots with the graph\'s custom palette', () => {
    const { container } = render(<Viewer graph={custom} />)
    fireEvent.click(screen.getByRole('button', { name: 'Matrix' }))
    const matrix = container.querySelector('[data-testid="matrix-view"]')!
    const ruleDot = matrix.querySelector('g[aria-label="VALIDATION_RULE: Rule"] circle')
    const otherDot = matrix.querySelector('g[aria-label="UNCOLORED: Other"] circle')
    expect(ruleDot).toHaveAttribute('fill', '#EF4444')
    expect(otherDot).toHaveAttribute('fill', '#9CA3AF')
  })
})
