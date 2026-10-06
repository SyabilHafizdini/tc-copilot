import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SelectionProvider, useSelection } from './selection'
import { SelectionBar } from './SelectionBar'

// Seeds the bus, then renders the bar under test.
function Seed({ n }: { n: number }) {
  const { toggle } = useSelection()
  return (
    <button onClick={() => {
      for (let i = 0; i < n; i++) toggle({ ref: `r${i}`, label: `L${i}`, type: 't' })
    }}>seed</button>
  )
}

function Harness({ n, chatEnabled }: { n: number; chatEnabled?: boolean }) {
  return <SelectionProvider chatEnabled={chatEnabled}><Seed n={n} /><SelectionBar /></SelectionProvider>
}

describe('SelectionBar', () => {
  it('is hidden while nothing is selected', () => {
    render(<Harness n={0} />)
    expect(screen.queryByRole('button', { name: /ask in chat/i })).toBeNull()
  })

  it('shows a live count and the Ask/Clear actions once items exist', () => {
    render(<Harness n={2} />)
    fireEvent.click(screen.getByText('seed'))
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ask in chat/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument()
  })

  it('Clear empties the selection and hides the bar again', () => {
    render(<Harness n={2} />)
    fireEvent.click(screen.getByText('seed'))
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(screen.queryByRole('button', { name: /ask in chat/i })).toBeNull()
  })

  it('renders nothing when chat is disabled, even with items selected', () => {
    render(<Harness n={2} chatEnabled={false} />)
    fireEvent.click(screen.getByText('seed'))
    expect(screen.queryByRole('region', { name: 'Selection' })).toBeNull()
    expect(screen.queryByText(/selected/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /ask in chat/i })).toBeNull()
  })
})
