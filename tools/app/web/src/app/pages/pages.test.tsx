import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { State } from '../api'
import { BoardPage } from './BoardPage'
import { StoriesPage } from './StoriesPage'
import { CoveragePage } from './CoveragePage'
import { ChangesPage } from './ChangesPage'
import { SettingsPage } from './SettingsPage'
import { TestCasesPage } from './TestCasesPage'
import { ActivityPage } from './ActivityPage'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getExplorer: vi.fn(), onChange: () => () => {} }
})
import * as api from '../api'

const STATE = {
  project: 'DEMO', prd: { adopted: '1', staged: null }, flows: [], cards: [],
  change_reports: [{ id: 'CR-2', status: 'pending' }],
  totals: { tcs: 72 }, next: { banners: [], rows: [] }, inventory: [], suites: ['sit-all'],
  stories: [
    {
      id: 'US-OK', title: 'Covered story', status: 'aligned', acs: 5, open_questions: 0,
      asserted_by: 'syabz', stale_causes: [], tc: { active: 10, stale: 0, retired: 0 },
      components: { total: 4, covered: 4, acs_without_tcs: 0, out_of_scope: 0, gaps: 0 },
    },
    {
      id: 'US-GAP', title: 'Gappy story', status: 'aligned', acs: 3, open_questions: 0,
      asserted_by: null, stale_causes: ['prd-section-changed'], tc: { active: 2, stale: 1, retired: 0 },
      components: { total: 5, covered: 2, acs_without_tcs: 1, out_of_scope: 0, gaps: 2 },
    },
  ],
} as unknown as State

const SNAP = {
  tree: [],
  graph: { nodes: [], links: [] },
  docs: {
    'testcases/sit/mod/AC01-01': {
      ref: 'testcases/sit/mod/AC01-01', kind: 'testcases', title: 'Verify the thing', status: 'active',
      version: 1, fields: [], body_md: '',
      facets: { kind: 'testcases', status: 'active', origin_state: 'proposed', story: 'stories/US-OK', asserted_by: null, stale: false, staleness_causes: [] },
    },
    'resolutions/R-OK-01': {
      ref: 'resolutions/R-OK-01', kind: 'resolutions', title: 'R-OK-01: decided the thing', status: 'asserted',
      version: 1, body_md: '',
      fields: [
        { key: 'asserted_by', kind: 'value', value: 'syabz' },
        { key: 'asserted_at', kind: 'value', value: '2026-07-23T16:12:52+08:00' },
      ],
      facets: { kind: 'resolutions', status: 'asserted', origin_state: 'asserted', story: null, asserted_by: 'syabz', stale: false, staleness_causes: [] },
    },
  },
}

describe('StoriesPage', () => {
  it('renders a Jira-style table row per story with status lozenge and counts', () => {
    render(<StoriesPage state={STATE} />)
    expect(screen.getByRole('link', { name: 'US-OK' })).toHaveAttribute('href', '#/story/US-OK')
    expect(screen.getByText('Covered story')).toBeInTheDocument()
    expect(screen.getAllByText('aligned').length).toBe(2)
    expect(screen.getByText('1 stale')).toBeInTheDocument()
  })
})

describe('BoardPage', () => {
  it('renders the four computed phase columns and metric filters', () => {
    render(<BoardPage state={STATE} />)
    expect(screen.getByText('① Ingested')).toBeInTheDocument()
    expect(screen.getByText('④ Generated')).toBeInTheDocument()
    expect(screen.getByText('Open questions')).toBeInTheDocument()
  })
})

describe('CoveragePage', () => {
  it('aggregates tiles and marks gap rows with a blocked verdict', () => {
    render(<CoveragePage state={STATE} />)
    expect(screen.getByText('6/9')).toBeInTheDocument() // covered/total across stories
    expect(screen.getByText('covered')).toBeInTheDocument()
    expect(screen.getByText('incomplete')).toBeInTheDocument()
  })
})

describe('ChangesPage', () => {
  it('lists change reports and stale downstream stories with causes', () => {
    render(<ChangesPage state={STATE} />)
    expect(screen.getByText('CR-2')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'US-GAP' })).toBeInTheDocument()
    expect(screen.getByText('prd-section-changed')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'US-OK' })).toBeNull() // not stale
  })
})

describe('SettingsPage', () => {
  it('shows project fields and fires the theme toggle', () => {
    const onToggleTheme = vi.fn()
    render(<SettingsPage state={STATE} projects={[]} theme="light" onToggleTheme={onToggleTheme} />)
    expect(screen.getByText('DEMO')).toBeInTheDocument()
    expect(screen.getByText('sit-all')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Slate' }))
    expect(onToggleTheme).toHaveBeenCalledOnce()
  })
})

describe('TestCasesPage', () => {
  it('lists TCs with level tag and filters by level', async () => {
    vi.mocked(api.getExplorer).mockResolvedValue(SNAP as never)
    render(<TestCasesPage />)
    expect(await screen.findByText('Verify the thing')).toBeInTheDocument()
    expect(screen.getAllByText('SIT').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /UAT/ }))
    expect(screen.getByText('No test cases at this level yet.')).toBeInTheDocument()
  })
})

describe('ActivityPage', () => {
  it('renders the asserted-resolution feed newest first', async () => {
    vi.mocked(api.getExplorer).mockResolvedValue(SNAP as never)
    render(<ActivityPage />)
    expect(await screen.findByRole('link', { name: 'R-OK-01' })).toBeInTheDocument()
    expect(screen.getByText('syabz')).toBeInTheDocument()
    expect(screen.getByText('decided the thing')).toBeInTheDocument()
  })
})
