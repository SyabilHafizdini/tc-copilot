import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat } from './useChat'
import * as api from '../api'

vi.mock('../api')

beforeEach(() => vi.resetAllMocks())

describe('useChat', () => {
  it('degrades when opencode is unavailable and never opens the event source', async () => {
    vi.mocked(api.chatHealth).mockResolvedValue({ available: false, reason: 'no binary', model: 'm' })
    const onChatEvents = vi.mocked(api.onChatEvents).mockReturnValue(() => {})
    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.health?.available).toBe(false))
    expect(onChatEvents).not.toHaveBeenCalled()
  })

  it('does NOT open the event source on mount even when healthy (deferred to first send)', async () => {
    // The deadlock guard: subscribing on mount hits a not-yet-spawned sidecar
    // which streams a single {type:'unavailable'} frame. So the mount effect
    // must probe health only -- the input stays usable, the source stays shut
    // until a session exists.
    vi.mocked(api.chatHealth).mockResolvedValue({ available: true, reason: 'ready', model: 'm' })
    const onChatEvents = vi.mocked(api.onChatEvents).mockReturnValue(() => {})
    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.health?.available).toBe(true))
    expect(onChatEvents).not.toHaveBeenCalled()
    // input is usable: send is a function and health gates it open
    expect(typeof result.current.send).toBe('function')
    expect(result.current.health?.available).toBe(true)
  })

  it('creates a session, subscribes AFTER it, then prompts on send', async () => {
    const order: string[] = []
    vi.mocked(api.chatHealth).mockResolvedValue({ available: true, reason: 'ready', model: 'm' })
    vi.mocked(api.createChatSession).mockImplementation(async () => {
      order.push('createChatSession')
      return { id: 's1' }
    })
    vi.mocked(api.onChatEvents).mockImplementation(() => {
      order.push('onChatEvents')
      return () => {}
    })
    vi.mocked(api.getChatMessages).mockResolvedValue([])
    vi.mocked(api.sendChatPrompt).mockResolvedValue()
    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.health?.available).toBe(true))
    // not subscribed until send
    expect(api.onChatEvents).not.toHaveBeenCalled()
    await act(async () => { await result.current.send('align US-VHLD') })
    expect(api.createChatSession).toHaveBeenCalled()
    expect(api.onChatEvents).toHaveBeenCalled()
    // subscription happens AFTER the session is created (base_url() is live)
    expect(order).toEqual(['createChatSession', 'onChatEvents'])
    expect(api.sendChatPrompt).toHaveBeenCalledWith('s1', 'align US-VHLD')
  })

  it('does not double-send while busy', async () => {
    vi.mocked(api.chatHealth).mockResolvedValue({ available: true, reason: 'ready', model: 'm' })
    vi.mocked(api.onChatEvents).mockReturnValue(() => {})
    vi.mocked(api.createChatSession).mockResolvedValue({ id: 's1' })
    vi.mocked(api.getChatMessages).mockResolvedValue([])
    vi.mocked(api.sendChatPrompt).mockResolvedValue()
    const { result } = renderHook(() => useChat())
    await waitFor(() => expect(result.current.health?.available).toBe(true))
    await act(async () => { await result.current.send('first') })
    expect(result.current.busy).toBe(true)
    // a second send while busy is a no-op -- no session.idle has arrived
    await act(async () => { await result.current.send('second') })
    expect(api.sendChatPrompt).toHaveBeenCalledTimes(1)
    expect(api.sendChatPrompt).toHaveBeenCalledWith('s1', 'first')
  })
})
