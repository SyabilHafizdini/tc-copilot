import { describe, it, expect } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { TypeColorProvider, useNodeColor } from './TypeColorContext'
import { resolveTypeColors, DEFAULT_NODE_COLOR } from './nodeStyle'

function Probe({ type }: { type: string }): ReactNode {
  const nodeColor = useNodeColor()
  return <span data-testid="probe">{nodeColor(type)}</span>
}

function StatefulProbe({ type }: { type: string }): ReactNode {
  const [tick, setTick] = useState(0)
  const nodeColor = useNodeColor()
  return (
    <button type="button" onClick={() => setTick((t) => t + 1)} data-testid="probe">
      {nodeColor(type)}#{tick}
    </button>
  )
}

describe('useNodeColor', () => {
  it('falls back to the built-in palette when there is no provider', () => {
    render(<Probe type="Page" />)
    expect(screen.getByTestId('probe')).toHaveTextContent('#3B82F6')
  })

  it('returns the default gray for a type in no palette', () => {
    render(<Probe type="MYSTERY" />)
    expect(screen.getByTestId('probe')).toHaveTextContent(DEFAULT_NODE_COLOR)
  })

  it('reads the provider palette when one is present', () => {
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <Probe type="VALIDATION_RULE" />
      </TypeColorProvider>,
    )
    expect(screen.getByTestId('probe')).toHaveTextContent('#EF4444')
  })

  it('keeps sibling providers independent, including after one of them changes', () => {
    function Tree({ rightColor }: { rightColor: string }): ReactNode {
      return (
        <>
          <div data-testid="left">
            <TypeColorProvider colors={resolveTypeColors({ T: '#111111' })}>
              <Probe type="T" />
            </TypeColorProvider>
          </div>
          <div data-testid="right">
            <TypeColorProvider colors={resolveTypeColors({ T: rightColor })}>
              <Probe type="T" />
            </TypeColorProvider>
          </div>
        </>
      )
    }
    const { rerender } = render(<Tree rightColor="#222222" />)
    expect(within(screen.getByTestId('left')).getByTestId('probe')).toHaveTextContent('#111111')
    expect(within(screen.getByTestId('right')).getByTestId('probe')).toHaveTextContent('#222222')

    rerender(<Tree rightColor="#333333" />)
    expect(within(screen.getByTestId('left')).getByTestId('probe')).toHaveTextContent('#111111')
    expect(within(screen.getByTestId('right')).getByTestId('probe')).toHaveTextContent('#333333')
  })

  it('keeps the resolver identity stable across re-renders with the same palette', () => {
    const seen: Array<(nodeType: string) => string> = []
    function Capture(): ReactNode {
      seen.push(useNodeColor())
      return null
    }
    const colors = resolveTypeColors({ T: '#111111' })
    const { rerender } = render(
      <TypeColorProvider colors={colors}><Capture /></TypeColorProvider>,
    )
    rerender(<TypeColorProvider colors={colors}><Capture /></TypeColorProvider>)
    expect(seen.length).toBeGreaterThanOrEqual(2)
    expect(seen[0]).toBe(seen[seen.length - 1])
  })

  it('changes the resolver identity when the palette reference changes', () => {
    const seen: Array<(nodeType: string) => string> = []
    function Capture(): ReactNode {
      seen.push(useNodeColor())
      return null
    }
    const { rerender } = render(
      <TypeColorProvider colors={resolveTypeColors({ T: '#111111' })}><Capture /></TypeColorProvider>,
    )
    rerender(
      <TypeColorProvider colors={resolveTypeColors({ T: '#222222' })}><Capture /></TypeColorProvider>,
    )
    expect(seen[0]).not.toBe(seen[seen.length - 1])
  })

  it('a subtree re-rendering alone still reads its own provider, not the last one mounted', () => {
    render(
      <>
        <div data-testid="left">
          <TypeColorProvider colors={resolveTypeColors({ T: '#111111' })}>
            <StatefulProbe type="T" />
          </TypeColorProvider>
        </div>
        <div data-testid="right">
          <TypeColorProvider colors={resolveTypeColors({ T: '#222222' })}>
            <StatefulProbe type="T" />
          </TypeColorProvider>
        </div>
      </>,
    )
    const leftProbe = within(screen.getByTestId('left')).getByTestId('probe')
    // Re-render ONLY the left subtree's leaf. Its provider does not re-run, so a
    // module-global palette would still hold the right subtree's value here.
    fireEvent.click(leftProbe)
    expect(leftProbe.textContent).toBe('#111111#1')
    expect(within(screen.getByTestId('right')).getByTestId('probe')).toHaveTextContent('#222222')
  })
})
