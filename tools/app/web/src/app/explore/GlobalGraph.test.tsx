import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GlobalGraph } from './GlobalGraph'
import type { GraphModel } from '../explorer/types'

const graph: GraphModel = {
  nodes: [
    { id: 'stories/US-1', type: 'Story' },
    { id: 'stories/US-1#AC1', type: 'AC' },
  ],
  links: [{ source: 'stories/US-1#AC1', target: 'stories/US-1', type: 'belongs_to' }],
}

describe('GlobalGraph', () => {
  it('defaults to the force view', () => {
    const { container } = render(<GlobalGraph graph={graph} onNavigate={vi.fn()} />)
    expect(container.querySelector('svg.h-full')).toBeInTheDocument()
    expect(screen.queryByTestId('indented-tree')).not.toBeInTheDocument()
  })

  it('switches to the indented tree view and back to force', () => {
    const { container } = render(<GlobalGraph graph={graph} onNavigate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /indented tree/i }))
    expect(screen.getByTestId('indented-tree')).toBeInTheDocument()
    expect(container.querySelector('svg.h-full')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^force$/i }))
    expect(screen.queryByTestId('indented-tree')).not.toBeInTheDocument()
    expect(container.querySelector('svg.h-full')).toBeInTheDocument()
  })

  it('navigates when an indented tree row is clicked', () => {
    const onNavigate = vi.fn()
    render(<GlobalGraph graph={graph} onNavigate={onNavigate} />)

    fireEvent.click(screen.getByRole('button', { name: /indented tree/i }))
    fireEvent.click(screen.getByTestId('indented-row-stories/US-1'))
    expect(onNavigate).toHaveBeenCalledWith('stories/US-1')
  })
})
