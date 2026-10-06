import { describe, expect, it, vi } from 'vitest'
import { act, render, screen, fireEvent, within } from '@testing-library/react'
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
  return { ...actual, getExplorer: vi.fn(), getTestCases: vi.fn(), onChange: vi.fn(() => () => {}) }
})
import * as api from '../api'
import { PAYLOAD } from '../testcases/fixtures'

const STATE = {
  schema1: false, notice: null, project: 'DEMO', prds: [
    { id: 'rental-application', title: 'Rental application', adopted: 2, staged: null },
    { id: 'rental-payment', title: 'Rental payment', adopted: 1, staged: 2 },
  ], flows: [], cards: [],
  change_reports: [
    { id: 'CR-1', status: 'approved', prd: 'rental-application', from: 1, to: 2 },
    { id: 'CR-2', status: 'pending', prd: 'rental-payment', from: 1, to: 2 },
  ],
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
    expect(screen.getAllByText('CR-2').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'US-GAP' })).toBeInTheDocument()
    expect(screen.getByText('prd-section-changed')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'US-OK' })).toBeNull() // not stale
  })

  it('shows one staged card per PRD that has a staged version, naming it', () => {
    render(<ChangesPage state={STATE} />)
    const staged = screen.getByRole('region', { name: 'Staged PRD versions' })
    expect(within(staged).getByText('Rental payment')).toBeInTheDocument()
    expect(within(staged).getByText('CR-2')).toBeInTheDocument()
    expect(within(staged).getByText('py tools/wiki.py diff --prd rental-payment')).toBeInTheDocument()
    expect(within(staged).queryByText('Rental application')).toBeNull() // nothing staged
  })

  it('names the PRD of every report in the history table', () => {
    render(<ChangesPage state={STATE} />)
    const row = screen.getByRole('row', { name: /CR-1/ })
    expect(within(row).getByText('rental-application')).toBeInTheDocument()
    expect(within(row).getByText('v1 → v2')).toBeInTheDocument()
  })

  it('never prints vnull: a PRD with a staged version and nothing adopted says so', () => {
    const state = { ...STATE, prds: [{ id: 'later', title: 'Later PRD', adopted: null, staged: 1 }] }
    render(<ChangesPage state={state as typeof STATE} />)
    const staged = screen.getByRole('region', { name: 'Staged PRD versions' })
    expect(within(staged).getByText('nothing adopted')).toBeInTheDocument()
    expect(within(staged).getByText('v1 staged')).toBeInTheDocument()
    expect(staged.textContent).not.toMatch(/v\s*adopted|vnull|v adopted/)
  })

  it('says so when no PRD has a staged version', () => {
    render(<ChangesPage state={{ ...STATE, prds: [], change_reports: [] }} />)
    expect(screen.getByText('No PRD has a staged version.')).toBeInTheDocument()
  })

  it('does not say nothing is staged on a project that is not migrated yet', () => {
    render(<ChangesPage state={{ ...STATE, schema1: true, notice: 'manifest.json is schema 1', prds: [], change_reports: [] }} />)
    const staged = screen.getByRole('region', { name: 'Staged PRD versions' })
    expect(within(staged).getByText('PRD state is not shown until the project is migrated.')).toBeInTheDocument()
    expect(screen.queryByText('No PRD has a staged version.')).toBeNull()
  })
})

describe('SettingsPage', () => {
  it('lists both PRDs with their versions', () => {
    render(<SettingsPage state={STATE} projects={[]} theme="light" onToggleTheme={vi.fn()} />)
    expect(screen.getByRole('row', { name: /rental-application/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /rental-payment/ })).toBeInTheDocument()
    expect(screen.getByText('v2 staged')).toBeInTheDocument()
  })

  it('does not say "No PRD registered." on a project that is not migrated yet', () => {
    render(<SettingsPage state={{ ...STATE, schema1: true, notice: 'manifest.json is schema 1', prds: [] }}
      projects={[]} theme="light" onToggleTheme={vi.fn()} />)
    expect(screen.getByText('PRD state is not shown until the project is migrated.')).toBeInTheDocument()
    expect(screen.queryByText('No PRD registered.')).toBeNull()
  })

  it('shows project fields and fires the theme toggle', () => {
    const onToggleTheme = vi.fn()
    render(<SettingsPage state={STATE} projects={[]} theme="light" onToggleTheme={onToggleTheme} />)
    expect(screen.getByText('DEMO')).toBeInTheDocument()
    expect(screen.getByText('sit-all')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Slate' }))
    expect(onToggleTheme).toHaveBeenCalledOnce()
  })

  it('shows the chat row with Off active by default and On calls the setter', () => {
    const onSetChatEnabled = vi.fn()
    render(<SettingsPage state={STATE} projects={[]} theme="light" onToggleTheme={vi.fn()}
      onSetChatEnabled={onSetChatEnabled} />)
    expect(screen.getByText('chat')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Off' })).toHaveClass('active')
    expect(screen.getByRole('button', { name: 'On' })).not.toHaveClass('active')
    fireEvent.click(screen.getByRole('button', { name: 'Off' }))
    expect(onSetChatEnabled).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'On' }))
    expect(onSetChatEnabled).toHaveBeenCalledExactlyOnceWith(true)
  })

  it('marks On active when chat is enabled and Off calls the setter', () => {
    const onSetChatEnabled = vi.fn()
    render(<SettingsPage state={STATE} projects={[]} theme="light" onToggleTheme={vi.fn()}
      chatEnabled onSetChatEnabled={onSetChatEnabled} />)
    expect(screen.getByRole('button', { name: 'On' })).toHaveClass('active')
    expect(screen.getByRole('button', { name: 'Off' })).not.toHaveClass('active')
    fireEvent.click(screen.getByRole('button', { name: 'On' }))
    expect(onSetChatEnabled).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Off' }))
    expect(onSetChatEnabled).toHaveBeenCalledExactlyOnceWith(false)
  })
})

describe('TestCasesPage', () => {
  it('loads the review grid and reloads it on a change event', async () => {
    vi.mocked(api.getTestCases).mockResolvedValue(PAYLOAD)
    render(<TestCasesPage />)
    expect(await screen.findByText('5 of 5 test cases')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Test Cases' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /Run: Main flow/ })).toBeInTheDocument()
    const reload = vi.mocked(api.onChange).mock.calls.at(-1)![0]
    await act(async () => { reload() })
    expect(api.getTestCases).toHaveBeenCalledTimes(2)
  })

  it('shows the error instead of an empty page when the read fails', async () => {
    vi.mocked(api.getTestCases).mockRejectedValue(new Error('GET /api/testcases -> 500'))
    render(<TestCasesPage />)
    expect(await screen.findByText(/api\/testcases -> 500/)).toBeInTheDocument()
  })

  it('a reload keeps the grid mounted with an open editor and its draft', async () => {
    vi.mocked(api.getTestCases).mockResolvedValue(PAYLOAD)
    const { container } = render(<TestCasesPage />)
    await screen.findByText('5 of 5 test cases')
    const grid = container.querySelector('.tc-review')
    fireEvent.click(container.querySelector('[data-tc="1.1-AC01-01"]')!)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Test Steps' }))
    const box = screen.getByRole('textbox', { name: 'Test Steps' })
    fireEvent.change(box, { target: { value: 'half a sentence' } })
    // the wiki changed (someone sealed, an agent committed): the page re-reads
    const next = { ...PAYLOAD, rows: PAYLOAD.rows.map((r) => (r.id === '1.1-AC02-01' ? { ...r, title: 'Changed elsewhere' } : r)) }
    vi.mocked(api.getTestCases).mockResolvedValue(next)
    const reload = vi.mocked(api.onChange).mock.calls.at(-1)![0]
    await act(async () => { reload() })
    expect(container.querySelector('.tc-review')).toBe(grid)
    expect(screen.getByRole('textbox', { name: 'Test Steps' })).toBe(box)
    expect(box).toHaveValue('half a sentence')
    // a reload that FAILS keeps it too, and says so above the grid
    vi.mocked(api.getTestCases).mockRejectedValue(new Error('GET /api/testcases -> 500'))
    await act(async () => { reload() })
    expect(screen.getByRole('textbox', { name: 'Test Steps' })).toBe(box)
    expect(box).toHaveValue('half a sentence')
    expect(screen.getByText(/api\/testcases -> 500/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
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
