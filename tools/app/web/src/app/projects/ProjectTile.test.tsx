import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ProjectTile } from './ProjectTile'
import type { ProjectCard } from '../api'

const base: ProjectCard = {
  id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
  counts: { stories: 5, tcs: 12 },
  next: { label: 'Align US-VHLD', view: { kind: 'story', id: 'US-VHLD' } },
}

describe('ProjectTile', () => {
  it('shows product, branch, counts and a 4-step phase tracker', () => {
    render(<ProjectTile card={base} onOpen={vi.fn()} onNext={vi.fn()} />)
    expect(screen.getByText('DEMO')).toBeInTheDocument()
    expect(screen.getByText('main')).toBeInTheDocument()
    expect(screen.getByText('5 stories')).toBeInTheDocument()
    expect(screen.getByText('12 test cases')).toBeInTheDocument()
    expect(screen.getByLabelText('phase tracker').querySelectorAll('li')).toHaveLength(4)
  })

  it('fires onNext with the next-action view', () => {
    const onNext = vi.fn()
    render(<ProjectTile card={base} onOpen={vi.fn()} onNext={onNext} />)
    fireEvent.click(screen.getByRole('button', { name: /align us-vhld/i }))
    expect(onNext).toHaveBeenCalledWith({ kind: 'story', id: 'US-VHLD' })
  })

  it('opens the project when the card body is clicked', () => {
    const onOpen = vi.fn()
    render(<ProjectTile card={{ ...base, next: null }} onOpen={onOpen} onNext={vi.fn()} />)
    fireEvent.click(screen.getByText('DEMO'))
    expect(onOpen).toHaveBeenCalledWith('tc-copilot')
  })
})
