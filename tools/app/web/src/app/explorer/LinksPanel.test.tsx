import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LinksPanel } from './LinksPanel'
import type { GraphModel, DocView } from './types'

const graph: GraphModel = {
  nodes: [{ id: 'stories/US-VHLD#AC1', type: 'AC' }, { id: 'testcases/T-1', type: 'TC' }],
  links: [{ source: 'testcases/T-1', target: 'stories/US-VHLD#AC1', type: 'covers' }],
}
const docs = { 'testcases/T-1': { ref: 'testcases/T-1', title: 'Access', status: 'active' } } as unknown as Record<string, DocView>

describe('LinksPanel', () => {
  it('shows a relation group and navigates on entry click', () => {
    const onNavigate = vi.fn()
    render(<LinksPanel graph={graph} docs={docs} selected="stories/US-VHLD#AC1" onNavigate={onNavigate} />)
    expect(screen.getByText('covered by')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Access'))
    expect(onNavigate).toHaveBeenCalledWith('testcases/T-1')
  })

  it('defaults to the force graph and switches to indented', () => {
    const { container } = render(
      <LinksPanel graph={graph} docs={docs} selected="testcases/T-1" onNavigate={vi.fn()} />,
    )
    expect(container.querySelector('svg.h-full')).toBeInTheDocument()
    expect(screen.queryByTestId('indented-tree')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^indented$/i }))
    expect(screen.getByTestId('indented-tree')).toBeInTheDocument()
    expect(container.querySelector('svg.h-full')).not.toBeInTheDocument()
  })

  it('navigates when an indented row is clicked, with Local/Global still working', () => {
    const onNavigate = vi.fn()
    render(<LinksPanel graph={graph} docs={docs} selected="testcases/T-1" onNavigate={onNavigate} />)

    fireEvent.click(screen.getByRole('button', { name: /^indented$/i }))
    fireEvent.click(screen.getByTestId('indented-row-testcases/T-1'))
    expect(onNavigate).toHaveBeenCalledWith('testcases/T-1')

    fireEvent.click(screen.getByRole('button', { name: /^global$/i }))
    expect(screen.getByTestId('indented-tree')).toBeInTheDocument()
  })
})
