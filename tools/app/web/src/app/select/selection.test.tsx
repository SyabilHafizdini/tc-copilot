import { describe, expect, it } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { SelectionProvider, useSelection } from './selection'
import type { SelNode } from './selection'

const a: SelNode = { ref: 'stories/US-VHLD#AC1', label: 'AC1', type: 'ac' }
const b: SelNode = { ref: 'glossary/hold', label: 'hold', type: 'glossary' }

const wrap = ({ children }: { children: React.ReactNode }) => (
  <SelectionProvider>{children}</SelectionProvider>
)

describe('useSelection', () => {
  it('toggle adds a node, toggling the same ref removes it', () => {
    const { result } = renderHook(() => useSelection(), { wrapper: wrap })
    act(() => result.current.toggle(a))
    expect(result.current.items).toEqual([a])
    act(() => result.current.toggle(a))
    expect(result.current.items).toEqual([])
  })

  it('multi-select keeps distinct refs and de-dupes by ref', () => {
    const { result } = renderHook(() => useSelection(), { wrapper: wrap })
    act(() => { result.current.toggle(a); result.current.toggle(b) })
    expect(result.current.items.map((i) => i.ref)).toEqual([a.ref, b.ref])
    // toggling a re-adds nothing new; it removes a
    act(() => result.current.toggle({ ...a, label: 'renamed' }))
    expect(result.current.items.map((i) => i.ref)).toEqual([b.ref])
  })

  it('clear empties the selection', () => {
    const { result } = renderHook(() => useSelection(), { wrapper: wrap })
    act(() => { result.current.toggle(a); result.current.toggle(b) })
    act(() => result.current.clear())
    expect(result.current.items).toEqual([])
  })

  it('askInChat publishes a read-only seed; correctInChat a correct-mode seed', () => {
    const { result } = renderHook(() => useSelection(), { wrapper: wrap })
    act(() => result.current.toggle(a))
    act(() => result.current.askInChat())
    expect(result.current.seed?.mode).toBe('ask')
    expect(result.current.seed?.text).toContain('AC1 (stories/US-VHLD#AC1)')
    const firstNonce = result.current.seed!.nonce
    act(() => result.current.correctInChat())
    expect(result.current.seed?.mode).toBe('correct')
    expect(result.current.seed?.text).toMatch(/verbatim/i)
    expect(result.current.seed!.nonce).not.toBe(firstNonce)
  })

  it('ask/correct no-op on an empty selection', () => {
    const { result } = renderHook(() => useSelection(), { wrapper: wrap })
    act(() => result.current.askInChat())
    expect(result.current.seed).toBeNull()
  })

  it('outside a provider useSelection returns an inert store', () => {
    const { result } = renderHook(() => useSelection())
    expect(result.current.items).toEqual([])
    act(() => result.current.toggle(a)) // must not throw
    expect(result.current.items).toEqual([])
  })
})
