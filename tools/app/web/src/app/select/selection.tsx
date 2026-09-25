import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { buildAskSeed, buildCorrectSeed } from './composerSeed'

export type SelNode = { ref: string; label: string; type: string }
export type ChatMode = 'ask' | 'correct'
export type ComposerSeed = { text: string; mode: ChatMode; nonce: number }

export type SelectionStore = {
  items: SelNode[]
  toggle(n: SelNode): void
  clear(): void
  seed: ComposerSeed | null
  askInChat(): void
  correctInChat(): void
}

const INERT: SelectionStore = {
  items: [], toggle: () => {}, clear: () => {}, seed: null,
  askInChat: () => {}, correctInChat: () => {},
}

const Ctx = createContext<SelectionStore>(INERT)

export function useSelection(): SelectionStore {
  return useContext(Ctx)
}

export function SelectionProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<SelNode[]>([])
  const [seed, setSeed] = useState<ComposerSeed | null>(null)
  const nonce = useRef(0)

  const toggle = useCallback((n: SelNode) => {
    setItems((cur) =>
      cur.some((i) => i.ref === n.ref) ? cur.filter((i) => i.ref !== n.ref) : [...cur, n])
  }, [])
  const clear = useCallback(() => setItems([]), [])

  const publish = useCallback((mode: ChatMode) => {
    setItems((cur) => {
      if (cur.length === 0) return cur
      const text = mode === 'ask' ? buildAskSeed(cur) : buildCorrectSeed(cur)
      setSeed({ text, mode, nonce: (nonce.current += 1) })
      return cur
    })
  }, [])
  const askInChat = useCallback(() => publish('ask'), [publish])
  const correctInChat = useCallback(() => publish('correct'), [publish])

  const value = useMemo<SelectionStore>(
    () => ({ items, toggle, clear, seed, askInChat, correctInChat }),
    [items, toggle, clear, seed, askInChat, correctInChat])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
