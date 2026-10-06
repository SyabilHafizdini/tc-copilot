import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, waitFor, fireEvent } from '@testing-library/react'

// useChat is the only caller of the /api/chat/* client functions, so "the hook
// never ran" is how these tests prove that no chat request was issued.
const { useChatSpy } = vi.hoisted(() => ({ useChatSpy: vi.fn() }))

vi.mock('./chat/useChat', () => ({
  useChat: () => {
    useChatSpy()
    return {
      health: { available: true, reason: 'ready', model: 'example-gateway' },
      messages: [], pending: [], busy: false,
      send: vi.fn(), abort: vi.fn(), respond: vi.fn(), newSession: vi.fn(),
    }
  },
}))

vi.mock('./api', () => ({
  bootstrap: vi.fn().mockResolvedValue(undefined),
  onChange: vi.fn().mockReturnValue(() => {}),
  runAction: vi.fn(),
  getState: vi.fn().mockResolvedValue({
    schema1: false, notice: null, project: 'P', prds: [], stories: [], flows: [],
    cards: [], change_reports: [], totals: { tcs: 0 }, next: { banners: [], rows: [] },
    suites: [],
  }),
  getProjects: vi.fn().mockResolvedValue([{
    id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
    counts: { stories: 1, tcs: 2 }, next: null,
  }]),
}))

vi.mock('./inbox/InboxPage', () => ({
  InboxPage: () => <div>Inbox page stub</div>,
}))

// The stub also exposes a button that puts one node on the selection bus
// directly (bypassing every hand-off control), so the chat-toggle tests can
// check what the real SelectionBar does with a selection.
vi.mock('./explore/ExplorePage', async () => {
  const { useSelection } = await import('./select')
  return {
    ExplorePage: () => {
      const { toggle, chatEnabled } = useSelection()
      return (
        <>
          <div>Explore page stub</div>
          <div data-testid="ctx-chat">{chatEnabled ? 'chat on' : 'chat off'}</div>
          <button onClick={() => toggle({ ref: 'stories/US-1', label: 'US-1', type: 'story' })}>
            seed selection
          </button>
        </>
      )
    },
  }
})

vi.mock('./story/StoryPage', () => ({
  StoryPage: ({ id }: { id: string }) => <div>Story page stub: {id}</div>,
}))

vi.mock('./documents/DocumentsPage', () => ({
  DocumentsPage: () => <div>Documents page stub</div>,
}))

vi.mock('./suites/SuitesPage', () => ({
  SuitesPage: () => <div>Suites page stub</div>,
}))
vi.mock('./workbook/WorkbookPage', () => ({
  WorkbookPage: (p: { wbKind: string; file: string; sheet?: string; row?: number }) => (
    <div>Workbook page stub: {p.wbKind}/{p.file}/{p.sheet ?? '-'}/{p.row ?? '-'}</div>
  ),
}))

import App from './App'
import { getState } from './api'
import { setUnsavedDraft } from './shell/unsaved'

afterEach(() => {
  window.location.hash = ''
  localStorage.clear()
  useChatSpy.mockClear()
})

describe('unsaved text in an editor', () => {
  afterEach(() => { setUnsavedDraft('test-draft', false) })

  it('makes the browser ask before a reload or a closed tab, and only then', async () => {
    window.location.hash = '#/coverage'
    render(<App />)
    await screen.findByText('Components covered')
    const leave = () => {
      const e = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(e)
      return e.defaultPrevented
    }
    expect(leave()).toBe(false)
    setUnsavedDraft('test-draft', true)
    expect(leave()).toBe(true)
    setUnsavedDraft('test-draft', false)
    expect(leave()).toBe(false)
  })

  it('asks before a route change, and a "no" keeps the page', async () => {
    window.location.hash = '#/coverage'
    render(<App />)
    await screen.findByText('Components covered')
    setUnsavedDraft('test-draft', true)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    window.location.hash = '#/suites'
    fireEvent(window, new HashChangeEvent('hashchange'))
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Components covered')).toBeInTheDocument()
    expect(screen.queryByText('Suites page stub')).toBeNull()
    expect(window.location.hash).toBe('#/coverage')
    confirm.mockRestore()
  })
})

describe('migration notice', () => {
  const NOTICE = 'manifest.json is schema 1 (one unnamed PRD).\n'
    + '  Convert the project once:\n    py tools/wiki.py migrate-prds'
  const SCHEMA1 = {
    schema1: true, notice: NOTICE, project: 'P', prds: [], stories: [], flows: [],
    cards: [], change_reports: [], totals: { tcs: 0 }, next: { banners: [], rows: [] },
    suites: [],
  }
  const notice = () => screen.queryByRole('region', { name: 'Migration needed' })

  it('is absent on a migrated project', async () => {
    window.location.hash = '#/coverage'
    render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
    expect(notice()).toBeNull()
  })

  it('shows the notice text above the page, and cannot be dismissed', async () => {
    vi.mocked(getState).mockResolvedValueOnce(SCHEMA1 as never)
    window.location.hash = '#/coverage'
    render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
    const banner = notice()!
    expect(banner).toHaveTextContent('manifest.json is schema 1 (one unnamed PRD).')
    expect(banner).toHaveTextContent('py tools/wiki.py migrate-prds')
    expect(within(banner).queryByRole('button')).toBeNull()
    expect(banner.compareDocumentPosition(screen.getByText('Components covered'))
      & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('stays visible on a route that does not read the state, and navigation still works', async () => {
    vi.mocked(getState).mockResolvedValueOnce(SCHEMA1 as never)
    window.location.hash = '#/explore'
    render(<App />)
    expect(await screen.findByText('Explore page stub')).toBeInTheDocument()
    await waitFor(() => expect(notice()).not.toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByText('PRD state is not shown until the project is migrated.')).toBeInTheDocument()
    expect(notice()).not.toBeNull()
  })
})

describe('chat toggle', () => {
  it('is Off when tc-chat-enabled is absent: no chat column, no reopen button, no chat hook', async () => {
    window.location.hash = '#/coverage'
    const { container } = render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
    expect(container.querySelector('.chatcol')).toBeNull()
    expect(screen.queryByTitle('Show chat')).toBeNull()
    expect(screen.queryByPlaceholderText(/type a message/i)).toBeNull()
    expect(useChatSpy).not.toHaveBeenCalled()
  })

  it('treats any stored value other than 1 as Off', async () => {
    localStorage.setItem('tc-chat-enabled', 'true')
    window.location.hash = '#/coverage'
    const { container } = render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
    expect(container.querySelector('.chatcol')).toBeNull()
    expect(useChatSpy).not.toHaveBeenCalled()
  })

  it('mounts the chat panel when tc-chat-enabled is 1', async () => {
    localStorage.setItem('tc-chat-enabled', '1')
    window.location.hash = '#/coverage'
    const { container } = render(<App />)
    expect(await screen.findByText('Components covered')).toBeInTheDocument()
    expect(container.querySelector('.chatcol')).not.toBeNull()
    expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument()
    expect(useChatSpy).toHaveBeenCalled()
  })

  it('Settings shows Off active by default; On mounts the panel and stores 1; Off unmounts it and stores 0', async () => {
    window.location.hash = '#/settings'
    const { container } = render(<App />)
    const on = await screen.findByRole('button', { name: 'On' })
    expect(screen.getByRole('button', { name: 'Off' })).toHaveClass('active')
    fireEvent.click(on)
    expect(screen.getByRole('button', { name: 'On' })).toHaveClass('active')
    expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument()
    expect(localStorage.getItem('tc-chat-enabled')).toBe('1')
    fireEvent.click(screen.getByRole('button', { name: 'Off' }))
    expect(container.querySelector('.chatcol')).toBeNull()
    expect(localStorage.getItem('tc-chat-enabled')).toBe('0')
  })

  it('switching Off then On restores the collapsed state that was left', async () => {
    localStorage.setItem('tc-chat-enabled', '1')
    localStorage.setItem('tc-chat-open', '0')
    window.location.hash = '#/settings'
    render(<App />)
    await screen.findByRole('button', { name: 'On' })
    expect(screen.getByTitle('Show chat')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Off' }))
    expect(screen.queryByTitle('Show chat')).toBeNull()
    expect(localStorage.getItem('tc-chat-open')).toBe('0')
    fireEvent.click(screen.getByRole('button', { name: 'On' }))
    expect(screen.getByTitle('Show chat')).toBeInTheDocument()
  })

  it('tells the selection context chat is Off, and the selection bar stays hidden', async () => {
    window.location.hash = '#/explore'
    render(<App />)
    fireEvent.click(await screen.findByText('seed selection'))
    expect(screen.getByTestId('ctx-chat')).toHaveTextContent('chat off')
    expect(screen.queryByRole('region', { name: 'Selection' })).toBeNull()
  })

  it('tells the selection context chat is On when tc-chat-enabled is 1, and the bar offers Ask in chat', async () => {
    localStorage.setItem('tc-chat-enabled', '1')
    window.location.hash = '#/explore'
    render(<App />)
    fireEvent.click(await screen.findByText('seed selection'))
    expect(screen.getByTestId('ctx-chat')).toHaveTextContent('chat on')
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ask in chat/i })).toBeInTheDocument()
  })
})

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

  it('mounts the WorkbookPage with kind, file, sheet and row from the hash', async () => {
    window.location.hash = '#/workbook/sit/demo-latest.xlsx?sheet=AI+Doubts&row=4'
    render(<App />)
    expect(await screen.findByText('Workbook page stub: sit/demo-latest.xlsx/AI Doubts/4'))
      .toBeInTheDocument()
  })
})
