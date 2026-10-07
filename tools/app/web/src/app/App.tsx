import { useCallback, useEffect, useState } from 'react'
import { bootstrap, getState, onChange, runAction } from './api'
import type { ActionResult, State } from './api'
import { AppShell, TopBar, Sidebar, ChatPanel } from './shell'
import { useView, hrefFor, type View } from './shell/routes'
import { useProject } from './shell/useProject'
import { hasUnsavedDraft } from './shell/unsaved'
import { Banner, PageSkeleton } from './ui'
import { Dashboard } from './dashboard/Dashboard'
import { DocumentsPage } from './documents/DocumentsPage'
import { ExplorePage } from './explore/ExplorePage'
import { FlowBuilderPage } from './flowbuilder/FlowBuilderPage'
import { FlowOverviewPage } from './flowbuilder/FlowOverviewPage'
import { ActivityPage } from './pages/ActivityPage'
import { BoardPage } from './pages/BoardPage'
import { ChangesPage } from './pages/ChangesPage'
import { CoveragePage } from './pages/CoveragePage'
import { Inbox } from './pages/Inbox'
import { RtmPage } from './pages/RtmPage'
import { SettingsPage } from './pages/SettingsPage'
import { StoriesPage } from './pages/StoriesPage'
import { TestCasesPage } from './pages/TestCasesPage'
import { Projects } from './projects/Projects'
import { SelectionProvider, SelectionBar } from './select'
import { StoryPage } from './story/StoryPage'
import { SuitesPage } from './suites/SuitesPage'
import { WorkbookPage } from './workbook/WorkbookPage'

type Theme = 'light' | 'dark'

function initialTheme(): Theme {
  const saved = localStorage.getItem('tc-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export default function App() {
  const [state, setState] = useState<State | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [liveDisconnected, setLiveDisconnected] = useState(false)
  const [result, setResult] = useState<ActionResult | { error: string } | null>(null)
  const view = useView()
  const { id: projectId, switch: switchProject, all: projects } = useProject()
  const [theme, setTheme] = useState<Theme>(initialTheme)
  // Chat is Off unless this browser stored exactly '1' (absent means Off).
  const [chatEnabled, setChatEnabled] = useState(() => localStorage.getItem('tc-chat-enabled') === '1')
  const [chatOpen, setChatOpen] = useState(() => localStorage.getItem('tc-chat-open') !== '0')
  const [chatWidth, setChatWidth] = useState(() => {
    const w = Number(localStorage.getItem('tc-chat-width'))
    return w >= 280 && w <= 760 ? w : 322
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('tc-theme', theme)
  }, [theme])

  const refresh = useCallback(() => {
    getState().then(setState).catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    bootstrap().then(refresh).catch((e) => setError(String(e)))
    // SSE fires on every agent file write, so a transient drop is common: once
    // state has loaded, surface it as a dismissable banner, never a brick.
    return onChange(refresh, () => setLiveDisconnected(true))
  }, [refresh])

  const navigate = useCallback((v: View) => { window.location.hash = hrefFor(v) }, [])
  const onRun = useCallback((name: string, params?: Record<string, unknown>) => {
    runAction(name, params).then(setResult).catch((e) => setResult({ error: String(e) }))
  }, [])
  const toggleTheme = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])

  // A reload or a closed tab would drop text typed into an open editor: the
  // browser asks first. (In-app navigation is guarded in useView.)
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (!hasUnsavedDraft()) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [])

  useEffect(() => { localStorage.setItem('tc-chat-enabled', chatEnabled ? '1' : '0') }, [chatEnabled])
  useEffect(() => { localStorage.setItem('tc-chat-open', chatOpen ? '1' : '0') }, [chatOpen])
  useEffect(() => { localStorage.setItem('tc-chat-width', String(chatWidth)) }, [chatWidth])

  // Drag the chat column's left edge to resize; the chat is docked on the
  // right, so moving the handle left widens it. Bounds keep it usable.
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = chatWidth
    const onMove = (ev: MouseEvent) =>
      setChatWidth(Math.min(760, Math.max(280, startW - (ev.clientX - startX))))
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [chatWidth])

  const body = () => {
    if (view.kind === 'projects') return <Projects />
    if (view.kind === 'explore') return <ExplorePage />
    if (view.kind === 'inbox') return <Inbox />
    if (view.kind === 'testcases') return <TestCasesPage />
    if (view.kind === 'activity') return <ActivityPage />
    if (view.kind === 'rtm') return <RtmPage />
    if (view.kind === 'workbook') {
      return <WorkbookPage wbKind={view.wbKind} file={view.file} sheet={view.sheet} row={view.row} />
    }
    if (view.kind === 'flowbuilder') return <FlowBuilderPage theme={theme} />
    if (view.kind === 'flows') return <FlowOverviewPage theme={theme} />
    // Everything below reads from the state snapshot.
    if (!state) return <PageSkeleton />
    switch (view.kind) {
      case 'dashboard': return <Dashboard state={state} />
      case 'board': return <BoardPage state={state} />
      case 'stories': return <StoriesPage state={state} />
      case 'story': return <StoryPage id={view.id} state={state} result={result} onRun={onRun} />
      case 'documents': return <DocumentsPage state={state} />
      case 'suites': return <SuitesPage state={state} />
      case 'coverage': return <CoveragePage state={state} />
      case 'changes': return <ChangesPage state={state} />
      case 'settings':
        return <SettingsPage
          state={state} projects={projects} theme={theme} onToggleTheme={toggleTheme}
          chatEnabled={chatEnabled} onSetChatEnabled={setChatEnabled} />
    }
  }

  return (
    <SelectionProvider chatEnabled={chatEnabled}>
      <AppShell
        chat={chatEnabled ? <ChatPanel onCollapse={() => setChatOpen(false)} /> : null}
        chatEnabled={chatEnabled}
        chatOpen={chatOpen}
        chatWidth={chatWidth}
        onReopen={() => setChatOpen(true)}
        onResizeStart={startResize}
        nav={<Sidebar
          active={view} onNavigate={navigate}
          project={projects.find((p) => p.id === projectId)?.product} />}
        topbar={<TopBar
          project={projectId} projects={projects} onSwitchProject={switchProject}
          onSearch={() => { /* Ctrl K palette wiring lands with Explore (Plan 4) */ }}
          onCreate={() => navigate({ kind: 'documents' })}
          theme={theme} onToggleTheme={toggleTheme} />}
      >
        {(error || liveDisconnected) && (
          <div style={{ padding: '14px 20px 0' }}>
            {error && <Banner tone="blocked" onDismiss={() => setError(null)}>{error}</Banner>}
            {liveDisconnected && (
              <Banner tone="blocked" onDismiss={() => setLiveDisconnected(false)}>
                live updates disconnected — reload the page to reconnect
              </Banner>
            )}
          </div>
        )}
        {state?.schema1 && (
          // Persistent on every route and never dismissable: until the project
          // is migrated the PRD state shown is incomplete and every action but
          // status and lint is refused. The text is the refusals' own.
          <section aria-label="Migration needed" style={{ padding: '14px 20px 0' }}>
            <Banner tone="blocked">
              <span style={{ whiteSpace: 'pre-wrap' }}>{state.notice}</span>
            </Banner>
          </section>
        )}
        {body()}
      </AppShell>
      <SelectionBar />
    </SelectionProvider>
  )
}
