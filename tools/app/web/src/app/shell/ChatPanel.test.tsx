import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// Same stub strategy as shell.test.tsx: useChat touches fetch/EventSource.
const send = vi.fn()
vi.mock('../chat/useChat', () => ({
  useChat: () => ({
    health: { available: true, reason: 'ready', model: 'example-gateway' },
    messages: [], pending: [], busy: false, model: null,
    send, abort: vi.fn(), respond: vi.fn(), newSession: vi.fn(),
  }),
}))

import { ChatPanel } from './ChatPanel'
import { SelectionProvider, useSelection } from '../select'

// Seeds the bus so the panel has selected items to render as chips.
function Seed() {
  const { toggle } = useSelection()
  return (
    <button onClick={() => {
      toggle({ ref: 'stories/US-VHLD#AC1', label: 'AC1', type: 'ac' })
      toggle({ ref: 'glossary/hold', label: 'hold', type: 'glossary' })
    }}>seed</button>
  )
}

function Harness() {
  return <SelectionProvider><Seed /><ChatPanel /></SelectionProvider>
}

describe('ChatPanel select-to-chat', () => {
  it('renders selected items as removable bullet chips', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('seed'))
    expect(screen.getByText(/AC1/)).toBeInTheDocument()
    expect(screen.getByText(/hold/)).toBeInTheDocument()
    // remove one chip
    fireEvent.click(screen.getByRole('button', { name: /remove AC1/i }))
    expect(screen.queryByText(/AC1/)).toBeNull()
    expect(screen.getByText(/hold/)).toBeInTheDocument()
  })

  it('askInChat seeds the composer with the bullets and a question prompt', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('seed'))
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }))
    const input = screen.getByPlaceholderText(/type a message/i) as HTMLInputElement
    expect(input.value).toContain('AC1 (stories/US-VHLD#AC1)')
    expect(input.value).toMatch(/Question:/i)
  })

  it('correctInChat shows the gated-card note and seeds a correction prompt', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('seed'))
    fireEvent.click(screen.getByRole('button', { name: /^correct$/i }))
    const input = screen.getByPlaceholderText(/type a message/i) as HTMLInputElement
    expect(input.value).toMatch(/verbatim/i)
    expect(input.value).toMatch(/do not edit directly/i)
    expect(screen.getByText(/produces a gated card/i)).toBeInTheDocument()
  })
})
