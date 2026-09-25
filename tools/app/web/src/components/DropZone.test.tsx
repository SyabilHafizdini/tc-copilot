import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DropZone } from './DropZone'

function makeFile(contents: string, name = 'graph.json'): File {
  return new File([contents], name, { type: 'application/json' })
}

const validDoc = JSON.stringify({
  nodes: [{ nodeId: 'n1', nodeType: 'Page', displayLabel: 'A' }],
  edges: [],
})

describe('DropZone', () => {
  it('renders the prompt and a file input', () => {
    render(<DropZone onGraphLoaded={vi.fn()} />)
    expect(screen.getByText(/drag & drop a graph json/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/choose file/i)).toBeInTheDocument()
  })

  it('loads a valid file via the input', async () => {
    const onGraphLoaded = vi.fn()
    render(<DropZone onGraphLoaded={onGraphLoaded} />)
    const input = screen.getByLabelText(/choose file/i)
    fireEvent.change(input, { target: { files: [makeFile(validDoc)] } })
    await waitFor(() => expect(onGraphLoaded).toHaveBeenCalledTimes(1))
    const graph = onGraphLoaded.mock.calls[0][0]
    expect(graph.nodes[0].properties).toEqual({})
  })

  it('shows parse errors for invalid JSON', async () => {
    render(<DropZone onGraphLoaded={vi.fn()} />)
    const input = screen.getByLabelText(/choose file/i)
    fireEvent.change(input, { target: { files: [makeFile('{not json')] } })
    await waitFor(() =>
      expect(screen.getByTestId('dropzone-errors')).toHaveTextContent(/invalid json/i),
    )
  })

  it('shows validation errors for schema violations', async () => {
    const bad = JSON.stringify({ nodes: [{ nodeId: 'n1' }], edges: [] })
    render(<DropZone onGraphLoaded={vi.fn()} />)
    const input = screen.getByLabelText(/choose file/i)
    fireEvent.change(input, { target: { files: [makeFile(bad)] } })
    await waitFor(() =>
      expect(screen.getByTestId('dropzone-errors')).toHaveTextContent(
        'nodes[0].nodeType: required non-empty string',
      ),
    )
  })
})
