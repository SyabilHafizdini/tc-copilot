import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SelectionProvider, useSelection } from './selection'
import { SelectableNode } from './SelectableNode'

const a = { ref: 'stories/US-VHLD#AC1', label: 'AC1', type: 'ac' }
const b = { ref: 'glossary/hold', label: 'hold', type: 'glossary' }

// A probe that renders the current selection count so tests can assert the bus.
function Count() {
  const { items } = useSelection()
  return <div data-testid="count">{items.length}</div>
}

function Harness({ onActivate }: { onActivate?: () => void }) {
  return (
    <SelectionProvider>
      <SelectableNode node={a} onActivate={onActivate}><span>AC1 body</span></SelectableNode>
      <SelectableNode node={b}><span>hold body</span></SelectableNode>
      <Count />
    </SelectionProvider>
  )
}

describe('SelectableNode', () => {
  it('is an accessible toggle button, unpressed by default', () => {
    render(<Harness />)
    const node = screen.getByRole('button', { name: /AC1 body/i })
    expect(node).toHaveAttribute('aria-pressed', 'false')
    expect(node).toHaveAttribute('tabindex', '0')
  })

  it('click toggles selection and reflects aria-pressed + selected class', () => {
    render(<Harness />)
    const node = screen.getByRole('button', { name: /AC1 body/i })
    fireEvent.click(node)
    expect(node).toHaveAttribute('aria-pressed', 'true')
    expect(node).toHaveClass('selected')
    expect(screen.getByTestId('count')).toHaveTextContent('1')
    fireEvent.click(node)
    expect(node).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('count')).toHaveTextContent('0')
  })

  it('supports multi-select across nodes', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /AC1 body/i }))
    fireEvent.click(screen.getByRole('button', { name: /hold body/i }))
    expect(screen.getByTestId('count')).toHaveTextContent('2')
  })

  it('Enter and Space toggle selection', () => {
    render(<Harness />)
    const node = screen.getByRole('button', { name: /AC1 body/i })
    fireEvent.keyDown(node, { key: 'Enter' })
    expect(node).toHaveAttribute('aria-pressed', 'true')
    fireEvent.keyDown(node, { key: ' ' })
    expect(node).toHaveAttribute('aria-pressed', 'false')
  })

  it('double-click fires onActivate without changing selection', () => {
    const onActivate = vi.fn()
    render(<Harness onActivate={onActivate} />)
    const node = screen.getByRole('button', { name: /AC1 body/i })
    fireEvent.doubleClick(node)
    expect(onActivate).toHaveBeenCalledOnce()
    expect(screen.getByTestId('count')).toHaveTextContent('0')
  })
})
