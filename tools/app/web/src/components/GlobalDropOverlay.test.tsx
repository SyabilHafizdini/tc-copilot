import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { GlobalDropOverlay } from './GlobalDropOverlay'

const VALID = JSON.stringify({
  meta: { title: 'Dropped' },
  nodes: [{ nodeId: 'n1', nodeType: 'T', displayLabel: 'A' }],
  edges: [],
})

function fireWindowDrop(contents: string, name = 'g.json') {
  const file = new File([contents], name, { type: 'application/json' })
  fireEvent.drop(window, {
    dataTransfer: { types: ['Files'], files: [file] },
  })
}

describe('GlobalDropOverlay', () => {
  it('shows the highlight during a file drag and hides it on drop', async () => {
    render(<GlobalDropOverlay onGraphLoaded={vi.fn()} />)
    fireEvent.dragOver(window, { dataTransfer: { types: ['Files'], files: [] } })
    expect(screen.getByTestId('global-drop-highlight')).toBeInTheDocument()
    fireWindowDrop(VALID)
    await waitFor(() =>
      expect(screen.queryByTestId('global-drop-highlight')).not.toBeInTheDocument(),
    )
  })

  it('calls onGraphLoaded with graph and title for a valid drop', async () => {
    const onGraphLoaded = vi.fn()
    render(<GlobalDropOverlay onGraphLoaded={onGraphLoaded} />)
    fireWindowDrop(VALID)
    await waitFor(() => expect(onGraphLoaded).toHaveBeenCalledTimes(1))
    expect(onGraphLoaded.mock.calls[0][1]).toBe('Dropped')
  })

  it('shows a dismissible error panel for an invalid drop', async () => {
    render(<GlobalDropOverlay onGraphLoaded={vi.fn()} />)
    fireWindowDrop('{broken', 'bad.json')
    const panel = await screen.findByTestId('global-drop-errors')
    expect(panel).toHaveTextContent('bad.json')
    expect(panel).toHaveTextContent(/Invalid JSON/)
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss errors' }))
    expect(screen.queryByTestId('global-drop-errors')).not.toBeInTheDocument()
  })

  it('ignores drags without files', () => {
    render(<GlobalDropOverlay onGraphLoaded={vi.fn()} />)
    fireEvent.dragOver(window, { dataTransfer: { types: ['text/plain'], files: [] } })
    expect(screen.queryByTestId('global-drop-highlight')).not.toBeInTheDocument()
  })

  it('hides the highlight when the drag leaves the window', () => {
    render(<GlobalDropOverlay onGraphLoaded={vi.fn()} />)
    fireEvent.dragOver(window, { dataTransfer: { types: ['Files'], files: [] } })
    expect(screen.getByTestId('global-drop-highlight')).toBeInTheDocument()
    fireEvent.dragLeave(window, { relatedTarget: null })
    expect(screen.queryByTestId('global-drop-highlight')).not.toBeInTheDocument()
  })

  it('removes window listeners on unmount', async () => {
    const onGraphLoaded = vi.fn()
    const { unmount } = render(<GlobalDropOverlay onGraphLoaded={onGraphLoaded} />)
    unmount()
    fireWindowDrop(VALID)
    await new Promise((r) => setTimeout(r, 20))
    expect(onGraphLoaded).not.toHaveBeenCalled()
    fireEvent.dragOver(window, { dataTransfer: { types: ['Files'], files: [] } })
    expect(screen.queryByTestId('global-drop-highlight')).not.toBeInTheDocument()
  })
})
