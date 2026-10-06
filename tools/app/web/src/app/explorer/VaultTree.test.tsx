import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VaultTree, bucketByPrd } from './VaultTree'
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

describe('VaultTree PRD grouping', () => {
  const sources = [{
    kind: 'sources', label: 'Sources', count: 4,
    items: [
      { ref: 'sources/figma/login', title: 'Login page', status: null, prd: null },
      { ref: 'sources/prd/rental-application/1-1', title: '1.1 Eligibility', status: null, prd: 'rental-application' },
      { ref: 'sources/prd/rental-payment/1-1', title: '1.1 Fees', status: null, prd: 'rental-payment' },
      { ref: 'sources/prd/rental-payment/1-2', title: '1.2 Refunds', status: null, prd: 'rental-payment' },
    ],
  }]

  it('buckets items by PRD, items with no PRD first', () => {
    const b = bucketByPrd(sources[0].items)
    expect(b.map(([prd, items]) => [prd, items.length])).toEqual([
      [null, 1], ['rental-application', 1], ['rental-payment', 2],
    ])
  })

  it('renders one sub-heading per PRD, using its title when given', () => {
    render(<VaultTree tree={sources} selected={null} onSelect={vi.fn()}
      subLabels={{ 'rental-payment': 'Rental payment' }} />)
    expect(screen.getByText('Rental payment')).toBeInTheDocument()   // title from subLabels
    expect(screen.getByText('rental-application')).toBeInTheDocument() // falls back to the id
    expect(screen.getByText('1.2 Refunds')).toBeInTheDocument()
    expect(screen.getByText('Login page')).toBeInTheDocument()
  })

  it('renders no sub-heading for a group with no PRD items', () => {
    const { container } = render(<VaultTree tree={tree} selected={null} onSelect={vi.fn()} />)
    expect(container.querySelector('.tree-sub')).toBeNull()
  })
})
