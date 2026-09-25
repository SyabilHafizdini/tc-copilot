import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, createEvent } from '@testing-library/react'
import App from './App'

function graphJson(title: string): string {
  return JSON.stringify({
    meta: { title },
    nodes: [{ nodeId: 'n1', nodeType: 'T', displayLabel: 'A' }],
    edges: [],
  })
}

function pickFile(contents: string, name = 'g.json') {
  const input = screen.getByLabelText(/choose file/i)
  fireEvent.change(input, { target: { files: [new File([contents], name)] } })
}

afterEach(() => {
  delete (window as { __GRAPH_DATA__?: unknown }).__GRAPH_DATA__
})

describe('App tabs', () => {
  it('seeds tab 1 from baked data with meta.title', () => {
    ;(window as { __GRAPH_DATA__?: unknown }).__GRAPH_DATA__ = JSON.parse(graphJson('Baked'))
    render(<App />)
    expect(screen.getByTestId('graph-tab-bar')).toHaveTextContent('Baked')
    expect(screen.getByRole('tab', { name: 'Baked' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('heading', { level: 1, name: 'Baked' })).toBeInTheDocument()
  })

  it('still shows the baked error screen for invalid baked data', () => {
    ;(window as { __GRAPH_DATA__?: unknown }).__GRAPH_DATA__ = { nodes: 'nope' }
    render(<App />)
    expect(screen.getByText('Baked graph data is invalid')).toBeInTheDocument()
    expect(screen.queryByTestId('graph-tab-bar')).not.toBeInTheDocument()
  })

  it('starts on the drop screen without baked data; loading adds a tab', async () => {
    render(<App />)
    expect(screen.queryByTestId('graph-tab-bar')).not.toBeInTheDocument()
    pickFile(graphJson('First'), 'first.json')
    await waitFor(() => expect(screen.getByTestId('graph-tab-bar')).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: 'First' })).toHaveAttribute('aria-selected', 'true')
  })

  it('the + screen adds a second tab and activates it; Back returns without adding', async () => {
    render(<App />)
    pickFile(graphJson('First'))
    await screen.findByTestId('graph-tab-bar')
    fireEvent.click(screen.getByRole('button', { name: 'Open another graph' }))
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getAllByRole('tab')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Open another graph' }))
    pickFile(graphJson('Second'))
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(2))
    expect(screen.getByRole('tab', { name: 'Second' })).toHaveAttribute('aria-selected', 'true')
    // keep-alive: the first tab's Viewer stays mounted while hidden.
    // getByText (not getByRole) – role queries exclude display:none elements.
    expect(screen.getByText('First', { selector: 'h1' })).toBeInTheDocument()
  })

  it('closing the active of two tabs activates the left neighbor', async () => {
    render(<App />)
    pickFile(graphJson('First'))
    await screen.findByTestId('graph-tab-bar')
    fireEvent.click(screen.getByRole('button', { name: 'Open another graph' }))
    pickFile(graphJson('Second'))
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(2))
    fireEvent.click(screen.getByRole('button', { name: 'Close Second' }))
    expect(screen.getByRole('tab', { name: 'First' })).toHaveAttribute('aria-selected', 'true')
  })

  it('closing the last tab returns to the drop screen', async () => {
    render(<App />)
    pickFile(graphJson('Only'))
    await screen.findByTestId('graph-tab-bar')
    fireEvent.click(screen.getByRole('button', { name: 'Close Only' }))
    expect(screen.queryByTestId('graph-tab-bar')).not.toBeInTheDocument()
    expect(screen.getByText(/drag & drop a graph json/i)).toBeInTheDocument()
  })

  it('prevents browser navigation defaults for stray drags in every mode', async () => {
    render(<App />)
    // Drop screen mode (GlobalDropOverlay unmounted): window drags still cancelled.
    const over = createEvent.dragOver(window, { dataTransfer: { types: ['text/uri-list'], files: [] } })
    fireEvent(window, over)
    expect(over.defaultPrevented).toBe(true)
    const drop = createEvent.drop(window, { dataTransfer: { types: ['text/uri-list'], files: [] } })
    fireEvent(window, drop)
    expect(drop.defaultPrevented).toBe(true)
  })
})
