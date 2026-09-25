import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ItemView } from './ItemView'
import { SelectionProvider, useSelection } from '../select'
import type { DocView, GraphModel } from '../explorer/types'

const story: DocView = {
  ref: 'stories/US-VHLD', kind: 'stories', type: 'User Story',
  title: 'Vault hold', status: 'aligned', version: 3,
  fields: [{
    key: 'acceptance_criteria', kind: 'itemized',
    items: [{ id: 'AC1', text: 'Given a vault, verify the hold.', status: 'active' }],
  }],
  body_md: '',
  facets: {
    kind: 'stories', status: 'aligned', origin_state: 'asserted',
    story: 'stories/US-VHLD', asserted_by: 'syabz', stale: false, staleness_causes: [],
  },
}

const tcRef = 'testcases/sit/vault/AC01-01.md'
const graph: GraphModel = {
  nodes: [
    { id: 'stories/US-VHLD', type: 'Story', label: 'Vault hold' },
    { id: 'stories/US-VHLD#AC1', type: 'AC', label: 'AC1' },
    { id: 'stories/US-VHLD#CMP-1', type: 'Component', label: 'AMB filter' },
    { id: tcRef, type: 'TC', label: 'Verify the hold' },
  ],
  links: [
    { source: 'stories/US-VHLD', target: 'stories/US-VHLD#AC1', type: 'has_ac' },
    { source: tcRef, target: 'stories/US-VHLD#AC1', type: 'covers' },
    { source: 'stories/US-VHLD#AC1', target: 'stories/US-VHLD#CMP-1', type: 'maps_to' },
  ],
}

const docs: Record<string, DocView> = {
  'stories/US-VHLD': story,
  [tcRef]: { ...story, ref: tcRef, kind: 'testcases', type: 'Test Case', title: 'Verify the hold', status: 'active' },
}

describe('ItemView (AC/BR/component drill-down)', () => {
  it('renders the item header, criterion text, and parent link', () => {
    render(<ItemView doc={story} frag="AC1" graph={graph} docs={docs} onNavigate={() => {}} />)
    expect(screen.getByText('Acceptance Criterion')).toBeInTheDocument()
    expect(screen.getByText('AC1')).toBeInTheDocument()
    expect(screen.getByText('Given a vault, verify the hold.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Vault hold' })).toBeInTheDocument()
  })

  it('lists typed links (covered by TC, maps to component) and navigates on click', () => {
    const onNavigate = vi.fn()
    render(<ItemView doc={story} frag="AC1" graph={graph} docs={docs} onNavigate={onNavigate} />)
    expect(screen.getByText('covered by')).toBeInTheDocument()
    expect(screen.getByText('maps to')).toBeInTheDocument()
    // the "part of <story>" edge is folded into the parent line, not a group
    expect(screen.queryByText('part of')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /AC01-01/ }))
    expect(onNavigate).toHaveBeenCalledWith(tcRef)
    fireEvent.click(screen.getByRole('button', { name: /CMP-1/ }))
    expect(onNavigate).toHaveBeenCalledWith('stories/US-VHLD#CMP-1')
  })

  it('adds the item to the chat selection from its own view', () => {
    function Count() {
      const { items } = useSelection()
      return <div data-testid="sel">{items.map((i) => i.ref).join(',')}</div>
    }
    render(
      <SelectionProvider>
        <ItemView doc={story} frag="AC1" graph={graph} docs={docs} onNavigate={() => {}} />
        <Count />
      </SelectionProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Add to chat' }))
    expect(screen.getByTestId('sel')).toHaveTextContent('stories/US-VHLD#AC1')
    expect(screen.getByRole('button', { name: /In chat selection/ })).toBeInTheDocument()
  })

  it('falls back to the graph label for components (no text field)', () => {
    const compDoc: DocView = {
      ...story,
      fields: [{ key: 'components', kind: 'itemized', items: [{ id: 'CMP-1', text: null, status: null }] }],
    }
    render(<ItemView doc={compDoc} frag="CMP-1" graph={graph} docs={docs} onNavigate={() => {}} />)
    expect(screen.getByText('Component')).toBeInTheDocument()
    expect(screen.getByText('AMB filter')).toBeInTheDocument()
  })
})
