import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, waitFor, fireEvent } from '@testing-library/react'

vi.mock('./chat/useChat', () => ({
  useChat: () => ({
    health: { available: true, reason: 'ready', model: 'example-gateway' },
    messages: [], pending: [], busy: false,
    send: vi.fn(), abort: vi.fn(), respond: vi.fn(), newSession: vi.fn(),
  }),
}))

vi.mock('./api', () => ({
  bootstrap: vi.fn().mockResolvedValue(undefined),
  onChange: vi.fn().mockReturnValue(() => {}),
  runAction: vi.fn(),
  getState: vi.fn().mockResolvedValue({
    project: 'P', prd: { adopted: '1', staged: null }, stories: [], flows: [],
    cards: [], change_reports: [], totals: { tcs: 0 }, next: { banners: [], rows: [] },
  }),
  getProjects: vi.fn().mockResolvedValue([{
    id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
    counts: { stories: 1, tcs: 2 }, next: null,
  }]),
}))

vi.mock('./inbox/InboxPage', () => ({
  InboxPage: () => <div>Inbox page stub</div>,
}))

vi.mock('./explore/ExplorePage', () => ({
  ExplorePage: () => <div>Explore page stub</div>,
}))

vi.mock('./story/StoryPage', () => ({
  StoryPage: ({ id }: { id: string }) => <div>Story page stub: {id}</div>,
}))

vi.mock('./documents/DocumentsPage', () => ({
  DocumentsPage: () => <div>Documents page stub</div>,
}))

vi.mock('./suites/SuitesPage', () => ({
  SuitesPage: () => <div>Suites page stub</div>,
}))

import App from './App'

afterEach(() => { window.location.hash = '' })

describe('App view routing', () => {
  it('renders the Projects portfolio at the projects hash', async () => {
    window.location.hash = '#/projects'
    const { container } = render(<App />)
    // 'DEMO' also appears in the always-present TopBar project switcher, so
    // scope the assertion to the portfolio grid itself.
    const grid = await waitFor(() => {
      const el = container.querySelector<HTMLElement>('.proj-grid')
      if (!el) throw new Error('portfolio grid not rendered yet')
      return el
    })
    expect(within(grid).getByText('DEMO')).toBeInTheDocument()
  })

  it('opening a project from the Projects portfolio lands on Explore, not Dashboard', async () => {
    window.location.hash = '#/projects'
    const { container } = render(<App />)
    const grid = await waitFor(() => {
      const el = container.querySelector<HTMLElement>('.proj-grid')
      if (!el) throw new Error('portfolio grid not rendered yet')
      return el
    })
    fireEvent.click(within(grid).getByText('DEMO'))
    expect(await screen.findByText('Explore page stub')).toBeInTheDocument()
    expect(window.location.hash).toBe('#/explore')
  })

  it('mounts the Dashboard (metric row + phase board) at #/dashboard', async () => {
    window.location.hash = '#/dashboard'
    render(<App />)
    expect(await screen.findByText('Open questions')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '① Ingested' })).toBeInTheDocument()
  })

  it('mounts the Coverage rollup at #/coverage', async () => {
    window.location.hash = '#/coverage'
    render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
  })

  it('mounts the Inbox page at #/inbox', async () => {
    window.location.hash = '#/inbox'
    render(<App />)
    expect(await screen.findByText('Inbox page stub')).toBeInTheDocument()
  })

  it('mounts the ExplorePage (not the old Explorer) at #/explore', async () => {
    window.location.hash = '#/explore'
    render(<App />)
    expect(await screen.findByText('Explore page stub')).toBeInTheDocument()
  })

  it('mounts Changes & Impact at #/changes', async () => {
    window.location.hash = '#/changes'
    render(<App />)
    expect(await screen.findByText(/No change reports/)).toBeInTheDocument()
  })

  it('mounts the StoryPage with the id from the hash at #/story/<id>', async () => {
    window.location.hash = '#/story/US-VHLD'
    render(<App />)
    expect(await screen.findByText('Story page stub: US-VHLD')).toBeInTheDocument()
  })

  it('mounts the DocumentsPage at #/documents', async () => {
    window.location.hash = '#/documents'
    render(<App />)
    expect(await screen.findByText('Documents page stub')).toBeInTheDocument()
  })

  it('mounts the SuitesPage at #/suites', async () => {
    window.location.hash = '#/suites'
    render(<App />)
    expect(await screen.findByText('Suites page stub')).toBeInTheDocument()
  })
})
