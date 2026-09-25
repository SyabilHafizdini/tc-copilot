import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { State } from '../api'

const snap = {
  tree: [
    { kind: 'sources', label: 'Sources', count: 1,
      items: [{ ref: 'sources/prd/example-prd', title: 'Example PRD', status: null }] },
    { kind: 'stories', label: 'Stories', count: 1,
      items: [{ ref: 'stories/US-VHLD', title: 'Vehicle Holding', status: 'draft' }] },
  ],
  docs: {
    'sources/prd/example-prd': {
      ref: 'sources/prd/example-prd', kind: 'sources',
      title: 'Example PRD', status: null, version: 1, fields: [],
      body_md: '## Section 4\nVerbatim PRD text here.',
      facets: { kind: 'sources', status: null, origin_state: 'asserted', story: null,
        asserted_by: null, stale: false, staleness_causes: [] },
    },
  },
  graph: { nodes: [], links: [] },
}
vi.mock('../api', () => ({ getExplorer: vi.fn(async () => snap) }))
vi.mock('../shell/routes', () => ({ hrefFor: (v: { kind: string }) => `#/${v.kind}` }))
import { DocumentsPage } from './DocumentsPage'

const state = {
  project: 'p', prd: { adopted: '0.3', staged: '0.4' },
  stories: [
    { id: 'US-VHLD', status: 'draft' },
    { id: 'US-ALGN', status: 'aligned' },
    { id: 'US-NEW', status: 'draft' },
  ],
  flows: [], cards: [], change_reports: [], totals: {}, suites: [],
  next: { banners: [], rows: [] },
} as unknown as State

beforeEach(() => { vi.clearAllMocks() })

describe('DocumentsPage', () => {
  it('shows the adopted + staged PRD chips and the stage-not-overwrite rule', () => {
    render(<DocumentsPage state={state} />)
    expect(screen.getByText(/v0\.3 adopted/)).toBeInTheDocument()
    expect(screen.getByText(/v0\.4 staged/)).toBeInTheDocument()
    expect(screen.getByText(/never overwrite/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Maintain . Changes/i }))
      .toHaveAttribute('href', '#/changes')
  })

  it('renders only the sources tree and previews the selected source verbatim', async () => {
    render(<DocumentsPage state={state} />)
    await waitFor(() => expect(screen.getByText('Sources')).toBeInTheDocument())
    expect(screen.queryByText('Stories')).not.toBeInTheDocument()  // scoped to sources/
    fireEvent.click(screen.getByText('Example PRD'))
    await waitFor(() =>
      expect(screen.getByText(/Verbatim PRD text here/)).toBeInTheDocument())
  })

  it('shows the skeleton-story ingest strip with a Go to Alignment hand-off', () => {
    render(<DocumentsPage state={state} />)
    expect(screen.getByText(/produced 2 skeleton stories/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to Alignment/i }))
      .toHaveAttribute('href', '#/board')
  })
})
