import { MessageSquare } from 'lucide-react'

// Jira-style frame: a full-width top bar, then nav (left) · active page
// (center) · persistent chat docked right, the way Jira docks Rovo chat. All
// state (theme, route, wiki data, chat enabled, width and open/closed) lives
// in App; this component only places the regions.
//
// The chat column width is driven by the --chat-w CSS variable so the
// responsive media query in index.css can still override it on narrow screens.
//
// chatEnabled is the Settings switch. When it is false the chat column and the
// reopen button are not rendered at all, and .app-body carries `no-chat` so
// index.css drops the third grid track and main takes the full remaining width.
export function AppShell({
  chat, topbar, nav, children,
  chatEnabled = true, chatOpen = true, chatWidth = 322, onReopen, onResizeStart,
}: {
  chat: React.ReactNode
  topbar: React.ReactNode
  nav: React.ReactNode
  children: React.ReactNode
  chatEnabled?: boolean
  chatOpen?: boolean
  chatWidth?: number
  onReopen?: () => void
  onResizeStart?: (e: React.MouseEvent) => void
}) {
  const chatShown = chatEnabled && chatOpen
  return (
    <div className="app" style={{ '--chat-w': `${chatShown ? chatWidth : 0}px` } as React.CSSProperties}>
      {topbar}
      <div className={`app-body${chatEnabled ? '' : ' no-chat'}`}>
        <aside className="navcol">{nav}</aside>
        <div className="main">
          {children}
        </div>
        {/* While chat is enabled, always render chatcol so it keeps occupying
            the last grid column -- collapsing it to zero width via CSS (not
            un-rendering it) keeps nav and main in their columns and preserves
            the chat session. Disabled is different on purpose: nothing is
            rendered, so ChatPanel never mounts and no chat request is made. */}
        {chatEnabled && (
          <aside className={`chatcol${chatOpen ? '' : ' collapsed'}`}>
            {chatOpen && <div className="chat-resize" title="Drag to resize" onMouseDown={onResizeStart} />}
            {chat}
          </aside>
        )}
      </div>
      {chatEnabled && !chatOpen && (
        <button className="chat-reopen" title="Show chat" onClick={onReopen}>
          <MessageSquare size={16} /> Chat
        </button>
      )}
    </div>
  )
}
