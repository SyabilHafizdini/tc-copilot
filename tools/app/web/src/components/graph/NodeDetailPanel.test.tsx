import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NodeDetailPanel } from './NodeDetailPanel'
import type { GraphNode } from '../../lib/types'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'

const base: GraphNode = {
  nodeId: 'n1',
  nodeType: 'Component',
  displayLabel: 'Login Form',
  properties: {},
}

function renderPanel(over: Partial<GraphNode>) {
  render(
    <NodeDetailPanel node={{ ...base, ...over }} onClose={vi.fn()} onFocusSubgraph={vi.fn()} />,
  )
}

describe('NodeDetailPanel content', () => {
  it('shows the Content section when the node has content', () => {
    renderPanel({ content: '# About\n\n```tsx\nconst x = 1\n```' })
    expect(screen.getByTestId('node-content')).toBeInTheDocument()
    expect(screen.getByTestId('code-block')).toBeInTheDocument()
  })

  it('renders no Content section when the node has no content', () => {
    renderPanel({})
    expect(screen.queryByTestId('node-content')).not.toBeInTheDocument()
  })
})

describe('NodeDetailPanel expand + collapse', () => {
  it('toggles the expanded container and backdrop', () => {
    renderPanel({ content: '# hi' })
    expect(screen.getByTestId('graph-detail-panel')).toHaveAttribute('data-expanded', 'false')
    expect(screen.queryByTestId('detail-backdrop')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /expand details/i }))
    expect(screen.getByTestId('graph-detail-panel')).toHaveAttribute('data-expanded', 'true')
    expect(screen.getByTestId('detail-backdrop')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /collapse details/i }))
    expect(screen.getByTestId('graph-detail-panel')).toHaveAttribute('data-expanded', 'false')
  })

  it('collapses when the backdrop is clicked', () => {
    renderPanel({ content: '# hi' })
    fireEvent.click(screen.getByRole('button', { name: /expand details/i }))
    fireEvent.click(screen.getByTestId('detail-backdrop'))
    expect(screen.getByTestId('graph-detail-panel')).toHaveAttribute('data-expanded', 'false')
  })

  it('collapses on Escape while expanded without closing the panel', () => {
    const onClose = vi.fn()
    render(<NodeDetailPanel node={{ ...base, content: '# hi' }} onClose={onClose} onFocusSubgraph={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /expand details/i }))
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.getByTestId('graph-detail-panel')).toHaveAttribute('data-expanded', 'false')
    expect(onClose).not.toHaveBeenCalled()
  })

  it('collapses and re-expands the Properties section', () => {
    renderPanel({ properties: { route: '/login' } })
    const header = screen.getByRole('button', { name: /properties/i })
    expect(screen.getByText('/login')).toBeInTheDocument()
    fireEvent.click(header)
    expect(screen.queryByText('/login')).not.toBeInTheDocument()
    fireEvent.click(header)
    expect(screen.getByText('/login')).toBeInTheDocument()
  })
})

describe('NodeDetailPanel resize', () => {
  it('has a resize handle in compact mode', () => {
    renderPanel({})
    expect(screen.getByTestId('detail-resize-handle')).toBeInTheDocument()
  })

  it('widens the panel when the handle is dragged left', () => {
    renderPanel({})
    fireEvent.mouseDown(screen.getByTestId('detail-resize-handle'), { clientX: 500 })
    fireEvent.mouseMove(window, { clientX: 400 })
    fireEvent.mouseUp(window)
    // dragged left 100px from the default 360 → 460
    expect(screen.getByTestId('graph-detail-panel')).toHaveStyle({ width: '460px' })
  })

  it('clamps the width at the max (720) when dragged far left', () => {
    renderPanel({})
    fireEvent.mouseDown(screen.getByTestId('detail-resize-handle'), { clientX: 500 })
    fireEvent.mouseMove(window, { clientX: 0 })
    fireEvent.mouseUp(window)
    expect(screen.getByTestId('graph-detail-panel')).toHaveStyle({ width: '720px' })
  })

  it('renders no resize handle when the panel is expanded', () => {
    renderPanel({ content: '# hi' })
    fireEvent.click(screen.getByRole('button', { name: /expand details/i }))
    expect(screen.queryByTestId('detail-resize-handle')).not.toBeInTheDocument()
  })
})

describe('NodeDetailPanel type badge', () => {
  it('derives the badge from the built-in palette with no provider', () => {
    renderPanel({ nodeType: 'Page' })
    const badge = screen.getByText('Page')
    expect(badge).toHaveStyle({ color: '#3B82F6', backgroundColor: 'rgba(59, 130, 246, 0.1)' })
  })

  it('derives the badge from a custom palette when provided', () => {
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <NodeDetailPanel
          node={{ ...base, nodeType: 'VALIDATION_RULE' }}
          onClose={vi.fn()}
          onFocusSubgraph={vi.fn()}
        />
      </TypeColorProvider>,
    )
    const badge = screen.getByText('VALIDATION_RULE')
    expect(badge).toHaveStyle({ color: '#EF4444', backgroundColor: 'rgba(239, 68, 68, 0.1)' })
  })

  it('falls back to the default gray for a type in no palette', () => {
    renderPanel({ nodeType: 'MYSTERY' })
    const badge = screen.getByText('MYSTERY')
    expect(badge).toHaveStyle({ color: '#9CA3AF', backgroundColor: 'rgba(156, 163, 175, 0.1)' })
  })
})
