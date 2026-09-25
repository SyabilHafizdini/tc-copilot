import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DirectoryTree } from './DirectoryTree'
import { buildFileTree } from './fileTree'
import { SelectionProvider, useSelection } from '../select'
import type { DocView } from '../explorer/types'

const doc = (over: Partial<DocView> & { ref: string }): DocView => ({
  kind: 'stories', title: null, status: null, version: 1, type: null,
  fields: [], body_md: '', facets: {
    kind: 'stories', status: null, origin_state: 'asserted',
    story: null, asserted_by: null, stale: false, staleness_causes: [],
  },
  ...over,
})

const refs = ['stories/US-VHLD', 'sources/prd/1', 'sources/prd/4-1-1-1', 'glossary/edo']
const docs: Record<string, DocView> = {
  'stories/US-VHLD': doc({ ref: 'stories/US-VHLD', title: 'Vehicle Holding', type: 'User Story', status: 'aligned' }),
  'sources/prd/1': doc({ ref: 'sources/prd/1', title: 'PRD §1', type: 'PRD Section' }),
  'sources/prd/4-1-1-1': doc({ ref: 'sources/prd/4-1-1-1', title: 'PRD §4.1.1.1', type: 'PRD Section' }),
  'glossary/edo': doc({ ref: 'glossary/edo', title: 'EDO', type: 'Glossary Term' }),
}

describe('DirectoryTree', () => {
  it('renders real top-level folders as rows, and files stay hidden until expanded', () => {
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('sources')).toBeInTheDocument()
    expect(screen.getByText('stories')).toBeInTheDocument()
    expect(screen.getByText('glossary')).toBeInTheDocument()
    // nested file under sources/prd is not shown until its ancestor folders are opened
    expect(screen.queryByText('PRD §1')).not.toBeInTheDocument()
  })

  it('reveals a nested file after expanding its ancestor folder', () => {
    // 'sources' is top-level, so it starts open (its child folder 'prd' is
    // already visible); 'prd' itself is one level deeper and starts closed.
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected={null} onSelect={vi.fn()} />)
    expect(screen.queryByText('PRD §1')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('prd'))
    expect(screen.getByText('PRD §1')).toBeInTheDocument()
    expect(screen.getByText('PRD §4.1.1.1')).toBeInTheDocument()
  })

  it('auto-expands the ancestors of the currently-selected file', () => {
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected="sources/prd/1" onSelect={vi.fn()} />)
    expect(screen.getByText('PRD §1')).toBeInTheDocument()
  })

  it('calls onSelect(ref) when a file row is clicked; clicking a folder does not', () => {
    const onSelect = vi.fn()
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected="stories/US-VHLD" onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Vehicle Holding'))
    expect(onSelect).toHaveBeenCalledWith('stories/US-VHLD')
    onSelect.mockClear()
    fireEvent.click(screen.getByText('glossary'))
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('falls back to the last path segment as the label when the doc has no title', () => {
    // 'modules' is top-level, so it is open by default — no click needed.
    const tree = buildFileTree(['modules/81-tasking'])
    render(<DirectoryTree tree={tree} docs={{}} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('81-tasking')).toBeInTheDocument()
  })

  it('renders row labels with a truncating class and a full-name title (VS Code-style long-name handling)', () => {
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected="stories/US-VHLD" onSelect={vi.fn()} />)
    const fileLabel = screen.getByText('Vehicle Holding')
    expect(fileLabel).toHaveClass('tree-label')
    expect(fileLabel).toHaveAttribute('title', 'Vehicle Holding')
    const folderLabel = screen.getByText('glossary')
    expect(folderLabel).toHaveClass('tree-label')
    expect(folderLabel).toHaveAttribute('title', 'glossary')
  })

  it('toggling a (default-open) top-level folder closed hides its children, and toggling again reopens it', () => {
    const tree = buildFileTree(refs)
    render(<DirectoryTree tree={tree} docs={docs} selected={null} onSelect={vi.fn()} />)
    const glossary = screen.getByText('glossary')
    expect(screen.getByText('EDO')).toBeInTheDocument() // open by default (top-level)
    fireEvent.click(glossary) // close
    expect(screen.queryByText('EDO')).not.toBeInTheDocument()
    fireEvent.click(glossary) // reopen
    expect(screen.getByText('EDO')).toBeInTheDocument()
  })
})

function SelCount() {
  const { items } = useSelection()
  return <div data-testid="sel-count">{items.length}</div>
}

describe('DirectoryTree selectable', () => {
  it('single click toggles selection on a file when selectable; double-click activates it', () => {
    const onSelect = vi.fn()
    const tree = buildFileTree(refs)
    render(
      <SelectionProvider>
        <DirectoryTree tree={tree} docs={docs} selected="stories/US-VHLD" onSelect={onSelect} selectable />
        <SelCount />
      </SelectionProvider>,
    )
    const node = screen.getByRole('button', { name: /Vehicle Holding/i })
    fireEvent.click(node)
    expect(screen.getByTestId('sel-count')).toHaveTextContent('1')
    expect(onSelect).not.toHaveBeenCalled()
    fireEvent.doubleClick(node)
    expect(onSelect).toHaveBeenCalledWith('stories/US-VHLD')
  })

  it('folders are never wrapped as selectable — clicking one only expands/collapses', () => {
    const tree = buildFileTree(refs)
    render(
      <SelectionProvider>
        <DirectoryTree tree={tree} docs={docs} selected={null} onSelect={vi.fn()} selectable />
        <SelCount />
      </SelectionProvider>,
    )
    expect(screen.getByText('EDO')).toBeInTheDocument() // glossary is top-level, open by default
    fireEvent.click(screen.getByText('glossary'))
    expect(screen.getByTestId('sel-count')).toHaveTextContent('0')
    expect(screen.queryByText('EDO')).not.toBeInTheDocument() // click collapsed it, not selected it
  })
})
