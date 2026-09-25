import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// The live ChatPanel calls useChat(), which hits chatHealth() (fetch) and
// potentially opens an EventSource -- neither behaves usefully in jsdom.
// Stub the hook so shell-level tests exercise layout/composition, not chat
// wiring (that's useChat.test.tsx and PermissionDialog.test.tsx's job).
vi.mock('../chat/useChat', () => ({
  useChat: () => ({
    health: { available: true, reason: 'ready', model: 'example-gateway' },
    messages: [],
    pending: [],
    busy: false,
    send: vi.fn(),
    abort: vi.fn(),
    respond: vi.fn(),
    newSession: vi.fn(),
  }),
}))

import { AppShell, TopBar, Sidebar, ChatPanel } from './index'
import type { ProjectCard } from '../api'

describe('AppShell', () => {
  it('renders all three regions and the center child', () => {
    const { container } = render(
      <AppShell chat={<div>CHAT</div>} topbar={<div>TOP</div>} nav={<div>NAV</div>}>
        <div>PAGE</div>
      </AppShell>,
    )
    expect(container.querySelector('.app')).not.toBeNull()
    expect(container.querySelector('.chatcol')).not.toBeNull()
    expect(container.querySelector('.navcol')).not.toBeNull()
    for (const t of ['CHAT', 'TOP', 'NAV', 'PAGE']) expect(screen.getByText(t)).toBeInTheDocument()
  })
})

describe('ChatPanel', () => {
  it('renders the live header and input once chat is available', () => {
    render(<ChatPanel />)
    expect(screen.getByText(/Agent/i)).toBeInTheDocument()
    expect(screen.getByText(/example-gateway/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument()
  })
})

describe('Sidebar', () => {
  it('renders phase groups, marks the active view and fires onNavigate', () => {
    const onNavigate = vi.fn()
    render(<Sidebar active={{ kind: 'dashboard' }} onNavigate={onNavigate} />)
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Generation')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dashboard/i })).toHaveAttribute('aria-current', 'page')
    fireEvent.click(screen.getByRole('button', { name: /documents/i }))
    expect(onNavigate).toHaveBeenCalledWith({ kind: 'documents' })
  })

  it('renders an Explore item and fires onNavigate with the explore view', () => {
    const onNavigate = vi.fn()
    render(<Sidebar active={{ kind: 'dashboard' }} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('button', { name: /explore/i }))
    expect(onNavigate).toHaveBeenCalledWith({ kind: 'explore' })
  })

  it('places Explore before Dashboard/Board/Stories as the primary nav item', () => {
    render(<Sidebar active={{ kind: 'dashboard' }} onNavigate={vi.fn()} />)
    const labels = screen.getAllByRole('button').map((b) => b.textContent)
    const exploreIx = labels.findIndex((l) => /explore/i.test(l ?? ''))
    const dashboardIx = labels.findIndex((l) => /dashboard/i.test(l ?? ''))
    expect(exploreIx).toBeGreaterThanOrEqual(0)
    expect(exploreIx).toBeLessThan(dashboardIx)
  })
})

describe('TopBar', () => {
  const projects: ProjectCard[] = [{
    id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
    counts: { stories: 1, tcs: 2 }, next: null,
  }]

  it('shows the Ctrl K search hint, the project switcher, and toggles theme', () => {
    const onToggleTheme = vi.fn(); const onSearch = vi.fn()
    const onCreate = vi.fn(); const onSwitchProject = vi.fn()
    render(<TopBar
      project="tc-copilot" projects={projects}
      onSwitchProject={onSwitchProject} onSearch={onSearch} onCreate={onCreate}
      theme="dark" onToggleTheme={onToggleTheme} />)
    expect(screen.getByText('Ctrl K')).toBeInTheDocument()
    expect(screen.getByText('DEMO')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create|ingest/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(onSearch).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: /theme|light|slate/i }))
    expect(onToggleTheme).toHaveBeenCalledOnce()
  })
})
