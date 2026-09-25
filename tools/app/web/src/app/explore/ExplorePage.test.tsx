import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import type { ExplorerSnapshot } from '../explorer/types'
import { SelectionProvider, useSelection } from '../select'

const snapshot: ExplorerSnapshot = {
  tree: [{
    kind: 'stories', label: 'Stories', count: 1,
    items: [{ ref: 'stories/US-VHLD', title: 'Vault hold', status: 'aligned' }],
  }],
  docs: {
    'stories/US-VHLD': {
      ref: 'stories/US-VHLD', kind: 'stories', type: 'User Story',
      title: 'Vault hold', status: 'aligned', version: 3,
      fields: [{ key: 'priority', kind: 'value', value: 'P1' }],
      body_md: 'See [US-OTHER](/stories/US-OTHER.md) for the linked story.',
      facets: {
        kind: 'stories', status: 'aligned', origin_state: 'asserted',
        story: 'stories/US-VHLD', asserted_by: 'syabz', stale: false, staleness_causes: [],
      },
    },
  },
  // Graph node type is the model's own vocabulary ('Story'), distinct from the
  // frontmatter `type` ('User Story') that drives the doc badge. The ontology
  // tree (now the default) groups by this graph type.
  graph: { nodes: [{ id: 'stories/US-VHLD', type: 'Story', label: 'Vault hold' }], links: [] },
}

// Same snapshot, plus a doc whose frontmatter `type` isn't in docType.ts's registry
// (exercises the docTypeMeta fallback / ds-default branch).
const snapshotWithUnknownType: ExplorerSnapshot = {
  ...snapshot,
  docs: {
    ...snapshot.docs,
    'stories/US-UNKNOWN': {
      ref: 'stories/US-UNKNOWN', kind: 'stories', type: 'Mystery Type',
      title: 'Mystery Doc', status: null, version: 1,
      fields: [], body_md: 'Mystery body.',
      facets: {
        kind: 'stories', status: null, origin_state: 'asserted',
        story: null, asserted_by: null, stale: false, staleness_causes: [],
      },
    },
  },
}

// Route model (Plan 1). A mutable holder lets individual tests set the view.
const mockView = { current: { kind: 'explore', path: 'stories/US-VHLD' } as { kind: string; path?: string } }
vi.mock('../shell/routes', () => ({
  useView: () => mockView.current,
  hrefFor: (v: { kind: string; path?: string }) => (v.path ? `#/explore/${v.path}` : '#/explore'),
}))

// getExplorer is mutable per-test so loading/error/no-selection states are reachable.
const mockGetExplorer = vi.fn(() => Promise.resolve(snapshot))
vi.mock('../api', () => ({
  getExplorer: () => mockGetExplorer(),
  onChange: () => () => {},
}))

import { ExplorePage } from './ExplorePage'

beforeEach(() => {
  mockView.current = { kind: 'explore', path: 'stories/US-VHLD' }
  window.location.hash = ''
  mockGetExplorer.mockReset()
  mockGetExplorer.mockReturnValue(Promise.resolve(snapshot))
})

describe('ExplorePage layout', () => {
  it('renders tree, content, metadata, the (secondary) graph, and the type badge', async () => {
    const { container } = render(<ExplorePage />)

    // tree (primary nav) — the selected story item
    expect(await screen.findByText('Vault hold')).toBeInTheDocument()
    // content pane rendered the markdown body (wiki-link text present)
    expect(screen.getByText(/linked story/)).toBeInTheDocument()
    // document-type badge from docTypeMeta
    const badge = container.querySelector('.doc-type-badge')
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toContain('User Story')
    // Metadata section (FrontmatterFields) — the frontmatter value renders
    expect(screen.getByText('Metadata')).toBeInTheDocument()
    expect(screen.getByText('P1')).toBeInTheDocument()
    // secondary graph kept: LinksPanel's Local/Global toggle + graph holder
    expect(screen.getByRole('button', { name: 'Local' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Global' })).toBeInTheDocument()
    expect(container.querySelector('.graph-holder')).not.toBeNull()
  })

  it('renders the loading skeleton while the snapshot has not resolved yet', () => {
    // A never-resolving promise keeps ExplorePage in its `!snapshot` branch.
    mockGetExplorer.mockReturnValue(new Promise(() => {}))
    render(<ExplorePage />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('renders the blocked banner when loading the snapshot fails', async () => {
    mockGetExplorer.mockReturnValue(Promise.reject(new Error('explorer offline')))
    const { container } = render(<ExplorePage />)
    expect(await screen.findByText(/explorer offline/)).toBeInTheDocument()
    expect(container.querySelector('.banner.blocked')).not.toBeNull()
  })

  it('renders the empty state when nothing is selected', async () => {
    mockView.current = { kind: 'explore', path: undefined }
    render(<ExplorePage />)
    // tree still loads and renders
    expect(await screen.findByText('Vault hold')).toBeInTheDocument()
    // content pane and metadata panel both fall back to their empty states
    expect(screen.getByText('Select a document')).toBeInTheDocument()
    expect(screen.getByText('No document selected')).toBeInTheDocument()
    // no badge, since there is no selected doc to derive one from
    expect(document.querySelector('.doc-type-badge')).toBeNull()
  })

  it('renders the empty state when the selected path has no matching doc', async () => {
    mockView.current = { kind: 'explore', path: 'stories/US-MISSING' }
    render(<ExplorePage />)
    expect(await screen.findByText('Vault hold')).toBeInTheDocument()
    expect(screen.getByText('Select a document')).toBeInTheDocument()
    expect(screen.getByText('No document selected')).toBeInTheDocument()
  })

  it('falls back to the ds-default badge for an unregistered document type', async () => {
    mockGetExplorer.mockReturnValue(Promise.resolve(snapshotWithUnknownType))
    mockView.current = { kind: 'explore', path: 'stories/US-UNKNOWN' }
    const { container } = render(<ExplorePage />)
    expect(await screen.findByText(/Mystery body/)).toBeInTheDocument()
    const badge = container.querySelector('.doc-type-badge')
    expect(badge).not.toBeNull()
    expect(badge?.classList.contains('ds-default')).toBe(true)
    expect(badge?.textContent).toContain('Mystery Type')
  })
})

describe('ExplorePage breadcrumb', () => {
  it('shows the file path segments in a breadcrumb', async () => {
    const { container } = render(<ExplorePage />)
    await screen.findByText('Vault hold')
    const crumb = container.querySelector('.explore-breadcrumb')
    expect(crumb).not.toBeNull()
    expect(crumb?.textContent).toContain('stories')
    expect(crumb?.textContent).toContain('US-VHLD')
  })

  it('navigates via the route model when a breadcrumb segment is clicked', async () => {
    render(<ExplorePage />)
    await screen.findByText('Vault hold')
    fireEvent.click(screen.getByRole('button', { name: 'stories' }))
    expect(window.location.hash).toBe('#/explore/stories')
  })
})

describe('ExplorePage navigation', () => {
  it('navigates to #/explore/<path> when a wiki-link in the content is clicked', async () => {
    render(<ExplorePage />)
    const link = await screen.findByText('US-OTHER') // rendered from [US-OTHER](/stories/US-OTHER.md)
    fireEvent.click(link)
    expect(window.location.hash).toBe('#/explore/stories/US-OTHER')
  })

  it('navigates when a tree file is clicked', async () => {
    render(<ExplorePage />)
    fireEvent.click(await screen.findByText('Vault hold'))
    expect(window.location.hash).toBe('#/explore/stories/US-VHLD')
  })
})

function SelCount() {
  const { items } = useSelection()
  return <div data-testid="sel-count">{items.length}</div>
}

describe('ExplorePage select-to-chat opt-in', () => {
  it('clicking an AC key drills down to the item view (no selection toggle)', async () => {
    const snapshotWithAC: ExplorerSnapshot = {
      ...snapshot,
      docs: {
        ...snapshot.docs,
        'stories/US-VHLD': {
          ...snapshot.docs['stories/US-VHLD'],
          fields: [
            ...snapshot.docs['stories/US-VHLD'].fields,
            { key: 'acceptance_criteria', kind: 'itemized', items: [{ id: 'AC1', text: 'do a thing', status: 'active' }] },
          ],
        },
      },
    }
    mockGetExplorer.mockReturnValue(Promise.resolve(snapshotWithAC))
    render(
      <SelectionProvider>
        <ExplorePage />
        <SelCount />
      </SelectionProvider>,
    )
    await screen.findByText('Vault hold')
    fireEvent.click(screen.getByRole('button', { name: 'AC1' }))
    expect(window.location.hash).toBe('#/explore/stories/US-VHLD#AC1')
    expect(screen.getByTestId('sel-count')).toHaveTextContent('0')
  })

  it('still navigates a tree file on click (VaultTree stays non-selectable)', async () => {
    render(
      <SelectionProvider>
        <ExplorePage />
        <SelCount />
      </SelectionProvider>,
    )
    fireEvent.click(await screen.findByText('Vault hold'))
    expect(window.location.hash).toBe('#/explore/stories/US-VHLD')
    expect(screen.getByTestId('sel-count')).toHaveTextContent('0')
  })
})

describe('ExplorePage directory tree', () => {
  const nestedSnapshot: ExplorerSnapshot = {
    ...snapshot,
    docs: {
      ...snapshot.docs,
      'sources/prd/4-1-1-1': {
        ref: 'sources/prd/4-1-1-1', kind: 'sources', type: 'PRD Section',
        title: 'PRD §4.1.1.1', status: null, version: 1,
        fields: [], body_md: 'PRD body.',
        facets: {
          kind: 'sources', status: null, origin_state: 'asserted',
          story: null, asserted_by: null, stale: false, staleness_causes: [],
        },
      },
    },
  }

  it('renders real top-level folders (from doc refs, not a kind-grouped list) and reveals a nested file on expand', async () => {
    mockGetExplorer.mockReturnValue(Promise.resolve(nestedSnapshot))
    const { container } = render(<ExplorePage />)
    await screen.findByText('Vault hold') // wait for the snapshot to load
    // the filesystem view is the "By type" tab, now secondary to Ontology
    fireEvent.click(screen.getByRole('button', { name: 'By type' }))
    // scope to the tree pane — "stories" also appears in the breadcrumb for the selected doc
    const tree = within(container.querySelector('.dir-tree') as HTMLElement)
    // real directory names, not "Stories"/"Sources" kind labels
    expect(tree.getByText('stories')).toBeInTheDocument()
    expect(tree.getByText('sources')).toBeInTheDocument()
    // 'sources' is top-level (open by default); 'prd' is nested one level
    // deeper and starts closed, so the file underneath isn't shown yet
    expect(tree.queryByText('PRD §4.1.1.1')).not.toBeInTheDocument()
    fireEvent.click(tree.getByText('prd'))
    const file = tree.getByText('PRD §4.1.1.1')
    expect(file).toBeInTheDocument()
    fireEvent.click(file)
    expect(window.location.hash).toBe('#/explore/sources/prd/4-1-1-1')
  })
})

describe('ExplorePage Files/Graph toggle', () => {
  it('opens the full-screen global graph and returns to Files', async () => {
    const { container } = render(<ExplorePage />)
    await screen.findByText('Vault hold')
    // starts in Files mode
    expect(container.querySelector('.explore-body')).not.toBeNull()
    expect(container.querySelector('.explore-graph-full')).toBeNull()
    // switch to Graph
    fireEvent.click(screen.getByRole('button', { name: 'Graph' }))
    expect(container.querySelector('.explore-graph-full')).not.toBeNull()
    expect(container.querySelector('.explore-body')).toBeNull()
    // back to Files
    fireEvent.click(screen.getByRole('button', { name: 'Files' }))
    expect(container.querySelector('.explore-body')).not.toBeNull()
    expect(container.querySelector('.explore-graph-full')).toBeNull()
  })
})
