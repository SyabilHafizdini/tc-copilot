import { useCallback, useEffect, useRef, useState } from 'react'
import type { Event, Permission } from '@opencode-ai/sdk'
import {
  chatHealth, createChatSession, getChatMessages, sendChatPrompt,
  abortChat, respondPermission, onChatEvents,
} from '../api'
import type { ChatHealth } from '../api'
import { messageText } from './message'

type Msg = { role: string; text: string; status?: 'sending' | 'sent' }

// Streaming model: the /event stream is a trigger, not the payload. On any
// message/part update or session.idle for the active session, refetch
// getChatMessages and re-render -- the same "SSE invalidates, refetch the
// read model" pattern the rest of the app already uses for /api/events.
// True token-delta rendering is a future refinement.
//
// Lifecycle: the opencode sidecar spawns LAZILY, server-side, on the first
// write (createChatSession / sendChatPrompt). Subscribing to /api/chat/event
// before that spawn hits a down sidecar, which emits a single
// {type:'unavailable'} frame -- so we defer the subscription until AFTER a
// session exists (ensureSession), when base_url() is live and the stream
// carries real events. Health, and therefore the clipboard degradation, is
// driven ONLY by the initial chatHealth() probe; a runtime 'unavailable'
// blip tears down the source (to stop respin) but must NOT brick the panel.
export function useChat() {
  const [health, setHealth] = useState<ChatHealth | null>(null)
  const [messages, setMessages] = useState<Msg[]>([])
  const [pending, setPending] = useState<Permission[]>([])
  const [busy, setBusy] = useState(false)
  // The model opencode ACTUALLY used, read from the assistant message it
  // produces (providerID/modelID). config.yaml's model is the production
  // target, not what local opencode is provisioned with, so we surface the
  // real one rather than claim a model the operator may not be running.
  const [model, setModel] = useState<string | null>(null)
  const sid = useRef<string | null>(null)
  const unsubRef = useRef<(() => void) | null>(null)

  const refetch = useCallback(async () => {
    if (!sid.current) return
    const entries = await getChatMessages(sid.current)
    setMessages(entries.map((e) => {
      const m = messageText(e)
      // user messages that came back from the server are delivered ('sent').
      return e.info.role === 'user' ? { ...m, status: 'sent' as const } : m
    }))
    const asst = [...entries].reverse().find(
      (e) => e.info.role === 'assistant' && 'modelID' in e.info && e.info.modelID)
    if (asst && 'modelID' in asst.info) {
      setModel(`${asst.info.providerID}/${asst.info.modelID}`)
    }
  }, [])

  const handleEvent = useCallback((e: Event) => {
    const type = (e as { type?: string }).type ?? ''
    if (type === 'unavailable') {
      // A runtime blip: the sidecar answered 'unavailable' on this stream.
      // Close the source so a raw EventSource doesn't respin against a down
      // sidecar, but do NOT flip health or drop the input -- the user can
      // retry, which re-ensures the session and re-subscribes.
      unsubRef.current?.()
      unsubRef.current = null
      return
    }
    if (type === 'message.updated' || type === 'message.part.updated') {
      void refetch()
    } else if (type === 'session.idle') {
      setBusy(false)
      void refetch()
    } else if (type === 'permission.updated') {
      const p = (e as { properties?: Permission }).properties
      if (p) setPending((cur) => [...cur.filter((x) => x.id !== p.id), p])
    } else if (type === 'permission.replied') {
      const id = (e as { properties?: { permissionID?: string } }).properties?.permissionID
      setPending((cur) => cur.filter((x) => x.id !== id))
    }
  }, [refetch])

  // Mount: probe health ONLY. Do not open the event source here -- the
  // sidecar isn't running yet, so it would only stream 'unavailable'.
  useEffect(() => {
    let cancelled = false
    chatHealth()
      .then((h) => { if (!cancelled) setHealth(h) })
      .catch(() => {
        if (!cancelled) setHealth({ available: false, reason: 'server error', model: '' })
      })
    return () => {
      cancelled = true
      unsubRef.current?.()
      unsubRef.current = null
    }
  }, [])

  const ensureSession = useCallback(async () => {
    // createChatSession triggers the server-side lazy sidecar spawn; only
    // once the session exists is base_url() live, so subscribe AFTER it.
    if (!sid.current) sid.current = (await createChatSession()).id
    if (!unsubRef.current) unsubRef.current = onChatEvents(handleEvent)
    return sid.current
  }, [handleEvent])

  const send = useCallback(async (text: string) => {
    if (!health?.available || busy || !text.trim()) return
    const id = await ensureSession()
    setMessages((m) => [...m, { role: 'user', text, status: 'sending' }])
    setBusy(true)
    await sendChatPrompt(id, text)
    // The 204 acceptance may arrive before any event-driven refetch; promote
    // the optimistic bubble from 'sending' to 'sent' so the check shows at once.
    setMessages((m) => m.map((msg) =>
      msg.role === 'user' && msg.status === 'sending' ? { ...msg, status: 'sent' } : msg))
  }, [health, busy, ensureSession])

  const abort = useCallback(async () => {
    if (sid.current) await abortChat(sid.current)
    setBusy(false)
  }, [])

  const respond = useCallback(async (permission: string, response: 'once' | 'always' | 'reject') => {
    if (sid.current) await respondPermission(sid.current, permission, response)
    setPending((cur) => cur.filter((p) => p.id !== permission))
  }, [])

  const newSession = useCallback(() => {
    unsubRef.current?.()
    unsubRef.current = null
    sid.current = null
    setMessages([])
    setPending([])
    setBusy(false)
    setModel(null)
  }, [])

  return { health, messages, pending, busy, model, send, abort, respond, newSession }
}
