import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { State } from '../api'
import * as api from '../api'
import { StoryPage } from './StoryPage'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getExplorer: vi.fn(), runDownload: vi.fn() }
})

const STATE = {
  project: 'p', prd: { adopted: '1', staged: null }, flows: [], cards: [], change_reports: [],
  totals: {}, next: { banners: [], rows: [] },
  stories: [{
    id: 'US-VHLD', title: 'Vehicle Holding', status: 'aligned', module: 'production-monitoring.md',
    acs: 25, open_questions: 0, asserted_by: 'syabz', stale_causes: [],
    tc: { active: 39, stale: 0, retired: 0 },
    components: { total: 15, covered: 13, acs_without_tcs: 0, out_of_scope: 2, gaps: 0 },
  }],
} as unknown as State

const SNAP = {
  tree: [], graph: { nodes: [], links: [] },
  docs: {
    'stories/US-VHLD': {
      ref: 'stories/US-VHLD', kind: 'stories', title: 'Vehicle Holding', status: 'aligned', version: 2,
      body_md: '# Summary\n\nThe Vehicle Holding dashboard.\n\n# Resolutions\n\n- R-VHLD-01 fixed the typo.\n',
      facets: { kind: 'stories', status: 'aligned', origin_state: 'asserted', story: 'stories/US-VHLD',
        asserted_by: 'syabz', stale: false, staleness_causes: [] },
      fields: [
        { key: 'acceptance_criteria', kind: 'itemized', items: [{ id: 'AC1', text: 'Access the dashboard', status: 'active' }] },
        { key: 'derived_from', kind: 'links', refs: ['/sources/prd/4-1-1-1.md'] },
      ],
    },
    'testcases/sit/production-monitoring/1.1.3.1.1-AC08-01': {
      ref: 'testcases/sit/production-monitoring/1.1.3.1.1-AC08-01', kind: 'testcases',
      title: 'Change filter', status: 'active', version: 1, body_md: '# Steps\n\n1. Add Workshop Y.\n',
      facets: { kind: 'testcases', status: 'active', origin_state: 'proposed', story: null,
        asserted_by: null, stale: false, staleness_causes: [] },
      fields: [{ key: 'covers', kind: 'links', refs: ['/stories/US-VHLD.md#1.1.3.1.1-AC8'] }],
    },
  },
}

describe('StoryPage', () => {
  beforeEach(() => {
    vi.mocked(api.getExplorer).mockResolvedValue(SNAP as never)
    vi.mocked(api.runDownload).mockResolvedValue()
  })

  it('renders the title, phase stepper (Generated current) and the sealed readiness verdict', async () => {
    render(<StoryPage id="US-VHLD" state={STATE} result={null} onRun={vi.fn()} />)
    expect(await screen.findByText('Vehicle Holding')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generated' }).className).toContain('current')
    expect(screen.getByText(/ready to export/i)).toBeInTheDocument()
  })

  it('the Export button calls runDownload with the sit/<name>-latest.xlsx artifact path', async () => {
    render(<StoryPage id="US-VHLD" state={STATE} result={null} onRun={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: /Export/ }))
    await waitFor(() => expect(api.runDownload).toHaveBeenCalledWith(
      'sit/US-VHLD-sit-latest.xlsx', { story: 'US-VHLD', name: 'US-VHLD-sit' },
    ))
  })

  it('switches to the Test Cases tab and shows the parsed TC', async () => {
    render(<StoryPage id="US-VHLD" state={STATE} result={null} onRun={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Test Cases' }))
    expect(await screen.findByText('Add Workshop Y.')).toBeInTheDocument()
  })

  it('shows a loading skeleton in the tab body while the explorer snapshot is pending', async () => {
    // Never resolves within the test: the AC tab must show a skeleton, never
    // sit silently empty (the original bug), until the snapshot lands.
    vi.mocked(api.getExplorer).mockReturnValue(new Promise(() => {}) as never)
    render(<StoryPage id="US-VHLD" state={STATE} result={null} onRun={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Acceptance Criteria' }))
    expect(screen.getAllByRole('status', { name: 'Loading' }).length).toBeGreaterThan(0)
  })

  it('a status transition from the rail fires onRun and the result renders verbatim', async () => {
    const result = { argv: ['gate', '--story', 'US-VHLD'], rc: 0, stdout: 'GATE OK', stderr: '' }
    render(<StoryPage id="US-VHLD" state={STATE} result={result} onRun={vi.fn()} />)
    expect(await screen.findByText(/GATE OK/)).toBeInTheDocument()
    expect(screen.getByText(/exit 0/)).toBeInTheDocument()
  })

  it('a refusal (non-zero rc) renders its stdout/stderr verbatim via Console', async () => {
    const result = {
      argv: ['gate', '--story', 'US-VHLD'], rc: 1,
      stdout: "GATE BLOCKED:\n - story stories/US-VHLD is 'draft', not aligned (spec §7.1)", stderr: '',
    }
    render(<StoryPage id="US-VHLD" state={STATE} result={result} onRun={vi.fn()} />)
    expect(await screen.findByText(/GATE BLOCKED/)).toBeInTheDocument()
    expect(screen.getByText(/exit 1/)).toBeInTheDocument()
  })

  it('renders an { error } result as a blocked banner, not through Console', async () => {
    render(<StoryPage id="US-VHLD" state={STATE} result={{ error: 'network unreachable' }} onRun={vi.fn()} />)
    expect(await screen.findByText(/network unreachable/)).toBeInTheDocument()
  })

  it('shows a not-found banner when the id is unknown', async () => {
    render(<StoryPage id="US-NOPE" state={STATE} result={null} onRun={vi.fn()} />)
    expect(await screen.findByText(/Story US-NOPE not found/)).toBeInTheDocument()
  })
})
