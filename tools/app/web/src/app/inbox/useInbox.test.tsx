import { describe, expect, it, vi } from 'vitest'
import { renderHook, act, waitFor as rtlWait } from '@testing-library/react'

const snap = { cards: [{ file: 'session-US-VHLD-001.json', card_type: 'alignment', story: 'stories/US-VHLD', emitted_at: '' }] }
vi.mock('../api', () => ({ getInbox: vi.fn(async () => snap), onChange: vi.fn(() => () => {}) }))
import { useInbox } from './useInbox'

describe('useInbox', () => {
  it('loads the inbox on mount and selects a card', async () => {
    const { result } = renderHook(() => useInbox())
    await rtlWait(() => expect(result.current.snapshot).toEqual(snap))
    act(() => result.current.select('session-US-VHLD-001.json'))
    expect(result.current.selected).toBe('session-US-VHLD-001.json')
  })
})
