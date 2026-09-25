import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VaultTree } from './VaultTree'
import { SelectionProvider, useSelection } from '../select'

const tree = [{ kind: 'stories', label: 'Stories', count: 1,
  items: [{ ref: 'stories/US-VHLD', title: 'Vehicle Holding', status: 'aligned' }] }]

describe('VaultTree', () => {
  it('shows the group label, count, and item title', () => {
    render(<VaultTree tree={tree} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('Stories')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('Vehicle Holding')).toBeInTheDocument()
  })
  it('calls onSelect with the item ref when clicked', () => {
    const onSelect = vi.fn()
    render(<VaultTree tree={tree} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Vehicle Holding'))
    expect(onSelect).toHaveBeenCalledWith('stories/US-VHLD')
  })
})

function TreeCount() {
  const { items } = useSelection()
  return <div data-testid="tree-count">{items.length}</div>
}

describe('VaultTree selectable', () => {
  const tree = [{
    kind: 'stories', label: 'Stories', count: 1,
    items: [{ ref: 'stories/US-VHLD', title: 'Hold', status: 'aligned' }],
  }]

  it('single click toggles selection when selectable; double-click opens', () => {
    const onSelect = vi.fn()
    render(
      <SelectionProvider>
        <VaultTree tree={tree} selected={null} onSelect={onSelect} selectable />
        <TreeCount />
      </SelectionProvider>,
    )
    const node = screen.getByRole('button', { name: /Hold/i })
    fireEvent.click(node)
    expect(screen.getByTestId('tree-count')).toHaveTextContent('1')
    expect(onSelect).not.toHaveBeenCalled()
    fireEvent.doubleClick(node)
    expect(onSelect).toHaveBeenCalledWith('stories/US-VHLD')
  })
})
