import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { OntologyTree } from './OntologyTree'
import type { OntologyNode } from './ontology'

const tree: OntologyNode[] = [
  {
    id: 'grp::modules', label: 'Modules', nodeType: 'group', ref: null, status: null, count: 1,
    children: [
      {
        id: 'modules/prod', label: 'Production', nodeType: 'Module', ref: 'modules/prod', status: 'aligned', count: 1,
        children: [
          {
            id: 'stories/US-A', label: 'Story A', nodeType: 'Story', ref: 'stories/US-A', status: 'aligned', count: 1,
            children: [
              {
                id: 'stories/US-A::ac', label: 'Acceptance Criteria', nodeType: 'group', ref: null, status: null, count: 1,
                children: [
                  {
                    id: 'stories/US-A#AC1', label: 'AC1', nodeType: 'AC', ref: 'stories/US-A#AC1', status: 'aligned', count: null,
                    children: [
                      { id: 'testcases/sit/tc-1', label: 'tc-1', nodeType: 'TC', ref: 'testcases/sit/tc-1', status: 'active', count: null, children: [] },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
]

describe('OntologyTree', () => {
  it('opens the Modules branch and its modules by default; deeper starts closed', () => {
    render(<OntologyTree tree={tree} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('Modules')).toBeInTheDocument()
    expect(screen.getByText('Production')).toBeInTheDocument()
    expect(screen.getByText('Story A')).toBeInTheDocument()
    // Story A is closed by default, so its AC branch is hidden until expanded.
    expect(screen.queryByText('Acceptance Criteria')).not.toBeInTheDocument()
  })

  it('clicking a document row selects it; clicking its twisty only expands', () => {
    const onSelect = vi.fn()
    render(<OntologyTree tree={tree} selected={null} onSelect={onSelect} />)
    const story = screen.getByText('Story A')
    // Twisty is the first sibling in the row; expand without selecting.
    const twisty = story.closest('.tree-item')!.querySelector('.tree-twisty')!
    fireEvent.click(twisty)
    expect(onSelect).not.toHaveBeenCalled()
    expect(screen.getByText('Acceptance Criteria')).toBeInTheDocument()
    // Clicking the label selects the story doc.
    fireEvent.click(story)
    expect(onSelect).toHaveBeenCalledWith('stories/US-A')
  })

  it('auto-expands the path to the selected nested node', () => {
    render(<OntologyTree tree={tree} selected="testcases/sit/tc-1" onSelect={vi.fn()} />)
    expect(screen.getByText('tc-1')).toBeInTheDocument()
    expect(screen.getByText('AC1')).toBeInTheDocument()
  })
})
