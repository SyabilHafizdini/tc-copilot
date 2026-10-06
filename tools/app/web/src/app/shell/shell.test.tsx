import { readFileSync } from 'node:fs'
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

  it('keeps the collapsed column and the reopen button when chat is enabled but closed', () => {
    const onReopen = vi.fn()
    const { container } = render(
      <AppShell chat={<div>CHAT</div>} topbar={<div>TOP</div>} nav={<div>NAV</div>}
        chatEnabled chatOpen={false} onReopen={onReopen}>
        <div>PAGE</div>
      </AppShell>,
    )
    expect(container.querySelector('.chatcol.collapsed')).not.toBeNull()
    expect(container.querySelector('.app-body')).not.toHaveClass('no-chat')
    fireEvent.click(screen.getByTitle('Show chat'))
    expect(onReopen).toHaveBeenCalledOnce()
  })

  it('renders no chat column, no reopen button and no chat track when chat is disabled', () => {
    const { container } = render(
      <AppShell chat={<div>CHAT</div>} topbar={<div>TOP</div>} nav={<div>NAV</div>}
        chatEnabled={false} chatOpen={false} chatWidth={400}>
        <div>PAGE</div>
      </AppShell>,
    )
    expect(container.querySelector('.chatcol')).toBeNull()
    expect(container.querySelector('.chat-resize')).toBeNull()
    expect(screen.queryByTitle('Show chat')).toBeNull()
    expect(screen.queryByText('CHAT')).toBeNull()
    expect(container.querySelector('.app-body')).toHaveClass('no-chat')
    expect(container.querySelector<HTMLElement>('.app')!.style.getPropertyValue('--chat-w')).toBe('0px')
    for (const t of ['TOP', 'NAV', 'PAGE']) expect(screen.getByText(t)).toBeInTheDocument()
  })

  it('renders no chat column when chat is disabled even if the open state says open', () => {
    const { container } = render(
      <AppShell chat={<div>CHAT</div>} topbar={<div>TOP</div>} nav={<div>NAV</div>}
        chatEnabled={false} chatOpen chatWidth={400}>
        <div>PAGE</div>
      </AppShell>,
    )
    expect(container.querySelector('.chatcol')).toBeNull()
    expect(container.querySelector<HTMLElement>('.app')!.style.getPropertyValue('--chat-w')).toBe('0px')
  })
})

// jsdom applies no stylesheet, so the grid rules are pinned as text. vitest
// runs with tools/app/web as the working directory.
describe('index.css chat track', () => {
  const css = readFileSync('src/index.css', 'utf8')

  it('drops the chat track when the shell is marked no-chat', () => {
    expect(css).toMatch(/\.app-body\.no-chat\s*\{\s*grid-template-columns:\s*240px minmax\(0, 1fr\);\s*\}/)
  })

  it('keeps the single-column narrow layout when chat is disabled', () => {
    const narrow = css.slice(css.indexOf('@media (max-width: 820px)'))
    expect(narrow).toMatch(/\.app-body,\s*\.app-body\.no-chat\s*\{\s*grid-template-columns:\s*1fr;\s*\}/)
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

  it('has a Workbook entry that opens the picker and lights up on any workbook', () => {
    const onNavigate = vi.fn()
    render(<Sidebar
      active={{ kind: 'workbook', wbKind: 'sit', file: 'demo-latest.xlsx' }}
      onNavigate={onNavigate} />)
    const item = screen.getByRole('button', { name: 'Workbook' })
    expect(item).toHaveAttribute('aria-current', 'page')
    fireEvent.click(item)
    expect(onNavigate).toHaveBeenCalledWith({ kind: 'workbook', wbKind: '', file: '' })
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
