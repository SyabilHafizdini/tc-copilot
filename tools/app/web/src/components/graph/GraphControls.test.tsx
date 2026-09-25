import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GraphControls } from './GraphControls'
import { DEFAULT_GRAPH_CONFIG } from '../../lib/useGraphConfig'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'

function renderControls(over: Partial<Parameters<typeof GraphControls>[0]> = {}) {
  const props = {
    allNodeTypes: ['Page', 'Field'],
    visibleTypes: new Set(['Page', 'Field']),
    onSetVisibleTypes: vi.fn(),
    allEdgeTypes: ['HAS_FIELD', 'CALLS'],
    visibleEdgeTypes: new Set(['HAS_FIELD', 'CALLS']),
    onSetVisibleEdgeTypes: vi.fn(),
    searchQuery: '',
    onSearchChange: vi.fn(),
    subgraphDepth: 2,
    onDepthChange: vi.fn(),
    focusedNodeId: null,
    onResetView: vi.fn(),
    config: DEFAULT_GRAPH_CONFIG,
    onConfigChange: vi.fn(),
    onResetConfig: vi.fn(),
    onReheat: vi.fn(),
    ...over,
  }
  render(<GraphControls {...props} />)
  return props
}

describe('GraphControls type pills', () => {
  it('renders a pill per edge type', () => {
    renderControls()
    expect(screen.getByRole('button', { name: /HAS_FIELD/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CALLS/ })).toBeInTheDocument()
  })

  it('single click toggles an edge type OFF (others stay)', () => {
    const p = renderControls()
    fireEvent.click(screen.getByRole('button', { name: /CALLS/ }))
    expect(p.onSetVisibleEdgeTypes).toHaveBeenCalledWith(new Set(['HAS_FIELD']))
  })

  it('single click toggles a hidden edge type back ON', () => {
    const p = renderControls({ visibleEdgeTypes: new Set(['HAS_FIELD']) })
    fireEvent.click(screen.getByRole('button', { name: /CALLS/ }))
    expect(p.onSetVisibleEdgeTypes).toHaveBeenCalledWith(new Set(['HAS_FIELD', 'CALLS']))
  })

  it('single click toggles a node type OFF (others stay)', () => {
    const p = renderControls()
    fireEvent.click(screen.getByRole('button', { name: /Page/ }))
    expect(p.onSetVisibleTypes).toHaveBeenCalledWith(new Set(['Field']))
  })

  it('double click isolates a node type', () => {
    const p = renderControls()
    fireEvent.doubleClick(screen.getByRole('button', { name: /Page/ }))
    expect(p.onSetVisibleTypes).toHaveBeenCalledWith(new Set(['Page']))
  })

  it('double click on the only visible node type restores all', () => {
    const p = renderControls({ visibleTypes: new Set(['Page']) })
    fireEvent.doubleClick(screen.getByRole('button', { name: /Page/ }))
    expect(p.onSetVisibleTypes).toHaveBeenCalledWith(new Set(['Page', 'Field']))
  })

  it("paints an active pill's dot with the graph's custom palette", () => {
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <GraphControls
          allNodeTypes={['VALIDATION_RULE']}
          visibleTypes={new Set(['VALIDATION_RULE'])}
          onSetVisibleTypes={vi.fn()}
          allEdgeTypes={[]}
          visibleEdgeTypes={new Set()}
          onSetVisibleEdgeTypes={vi.fn()}
          searchQuery=""
          onSearchChange={vi.fn()}
          subgraphDepth={2}
          onDepthChange={vi.fn()}
          focusedNodeId={null}
          onResetView={vi.fn()}
          config={DEFAULT_GRAPH_CONFIG}
          onConfigChange={vi.fn()}
          onResetConfig={vi.fn()}
          onReheat={vi.fn()}
        />
      </TypeColorProvider>,
    )
    const pill = screen.getByRole('button', { name: /VALIDATION_RULE/ })
    expect(pill.querySelector('.rounded-full')).toHaveStyle({ backgroundColor: '#EF4444' })
  })
})
