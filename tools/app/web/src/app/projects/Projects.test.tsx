import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../shell/useProject', () => ({
  useProject: () => ({
    id: 'tc-copilot', switch: vi.fn(),
    all: [{
      id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 1,
      counts: { stories: 3, tcs: 0 }, next: null,
    }],
  }),
}))

import { Projects } from './Projects'

describe('Projects portfolio', () => {
  it('renders the heading, a New project affordance and a grid of tiles', () => {
    render(<Projects />)
    expect(screen.getByRole('heading', { name: /projects/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new project/i })).toBeInTheDocument()
    expect(screen.getByText('DEMO')).toBeInTheDocument()
    expect(screen.getByText('3 stories')).toBeInTheDocument()
  })
})
