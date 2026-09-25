import { useEffect, useRef, useState } from 'react'
import { MessageSquare, ArrowRight, Square, Plus, Check, Clock, PanelRightClose, X } from 'lucide-react'
import { useChat } from '../chat/useChat'
import { PermissionDialog } from '../chat/PermissionDialog'
import { ClipboardHandoff } from '../chat/ClipboardHandoff'
import { useSelection } from '../select'

// Persistent, first-class -- always present regardless of the active page.
// Live @opencode-ai/sdk client wired via useChat: streaming (event-triggered
// refetch), permission dialogs, and clipboard degradation when the sidecar
// is unavailable. onCollapse (optional) hides the whole chat column.
export function ChatPanel({ onCollapse }: { onCollapse?: () => void }) {
  const { health, messages, pending, busy, model, send, abort, respond, newSession } = useChat()
  const { items, toggle, seed, askInChat, correctInChat } = useSelection()
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState<'ask' | 'correct'>('ask')
  const streamRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // A new seed (ask/correct, from a bullet-chip selection elsewhere in the
  // app) populates and focuses the composer. It never sends on its own --
  // the human reviews/edits and submits, same as any other message.
  useEffect(() => {
    if (!seed) return
    setDraft(seed.text)
    setMode(seed.mode)
    inputRef.current?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  // Keep the newest message (and the typing indicator) in view. scrollTo is
  // absent in jsdom, so fall back to scrollTop there.
  useEffect(() => {
    const el = streamRef.current
    if (!el) return
    if (typeof el.scrollTo === 'function') el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    else el.scrollTop = el.scrollHeight
  }, [messages, busy, pending])

  // Show the model opencode actually used once it's known; before the first
  // reply fall back to just the provider (health.model is "provider/model",
  // and its model half is only the config target, not the live model).
  const label = model ?? health?.model?.split('/')[0] ?? 'model'

  const submit = () => {
    const text = draft
    if (!text.trim()) return
    setDraft('')
    void send(text)
  }

  return (
    <>
      <div className="chead">
        <span className="cico"><MessageSquare size={15} /></span>
        <b>Agent<span>OpenCode · {label}</span></b>
        <div className="chead-actions">
          <button className="cbtn" title="New session" onClick={newSession}><Plus size={14} /></button>
          {onCollapse && (
            <button className="cbtn" title="Hide chat" onClick={onCollapse}><PanelRightClose size={14} /></button>
          )}
        </div>
      </div>
      {health && !health.available ? (
        <ClipboardHandoff reason={health.reason} />
      ) : (
        <>
          <div className="stream" ref={streamRef}>
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <span className="msg-body">{m.text}</span>
                {m.role === 'user' && m.status && (
                  <span className={`msg-status ${m.status}`} title={m.status === 'sending' ? 'Sending…' : 'Sent'}>
                    {m.status === 'sending' ? <Clock size={11} /> : <Check size={11} />}
                  </span>
                )}
              </div>
            ))}
            {busy && (
              <div className="msg assistant typing" aria-label="Agent is generating a reply">
                <span /><span /><span />
              </div>
            )}
            {pending.map((p) => (
              <PermissionDialog key={p.id} permission={p} onRespond={respond} />
            ))}
          </div>
          {items.length > 0 && (
            <div className="sel-chips">
              <div className="sel-chip-row">
                {items.map((it) => (
                  <span className="chip sel-chip" key={it.ref}>
                    {'•'} {it.label}
                    <button className="chip-x" aria-label={`remove ${it.label}`} onClick={() => toggle(it)}>
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
              <div className="sel-mode-row">
                <button className={mode === 'ask' ? 'active' : ''} onClick={askInChat}>Ask</button>
                <button className={mode === 'correct' ? 'active' : ''} onClick={correctInChat}>Correct</button>
                {mode === 'correct' && (
                  <span className="sel-fence-note">
                    Correct — produces a gated card to assert; nothing changes until you assert.
                  </span>
                )}
              </div>
            </div>
          )}
          <div className="cinput">
            <input
              ref={inputRef}
              className="box"
              value={draft}
              placeholder="Type a message…"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
            />
            {busy
              ? <span className="send stop" title="Stop" onClick={() => void abort()}><Square size={15} /></span>
              : <span className="send" title="Send" onClick={submit}><ArrowRight size={15} /></span>}
          </div>
        </>
      )}
    </>
  )
}
