import { MessageSquare } from 'lucide-react'

// Jira-style frame: a full-width top bar, then nav (left) · active page
// (center) · persistent chat docked right, the way Jira docks Rovo chat. All
// state (theme, route, wiki data, chat width and open/closed) lives in App;
// this component only places the regions.
//
// The chat column width is driven by the --chat-w CSS variable so the
// responsive media query in index.css can still override it on narrow screens.
export function AppShell({
  chat, topbar, nav, children,
  chatOpen = true, chatWidth = 322, onReopen, onResizeStart,
}: {
  chat: React.ReactNode
  topbar: React.ReactNode
  nav: React.ReactNode
  children: React.ReactNode
  chatOpen?: boolean
  chatWidth?: number
  onReopen?: () => void
  onResizeStart?: (e: React.MouseEvent) => void
}) {
  return (
    <div className="app" style={{ '--chat-w': `${chatOpen ? chatWidth : 0}px` } as React.CSSProperties}>
      {topbar}
      <div className="app-body">
        <aside className="navcol">{nav}</aside>
        <div className="main">
          {children}
        </div>
        {/* Always render chatcol so it keeps occupying the last grid column --
            collapsing it to zero width via CSS (not un-rendering it) keeps nav
            and main in their columns and preserves the chat session. */}
        <aside className={`chatcol${chatOpen ? '' : ' collapsed'}`}>
          {chatOpen && <div className="chat-resize" title="Drag to resize" onMouseDown={onResizeStart} />}
          {chat}
        </aside>
      </div>
      {!chatOpen && (
        <button className="chat-reopen" title="Show chat" onClick={onReopen}>
          <MessageSquare size={16} /> Chat
        </button>
      )}
    </div>
  )
}
