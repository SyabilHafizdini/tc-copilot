import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TabBar } from './TabBar'

const TABS = [
  { id: 'tab-1', title: 'Alpha' },
  { id: 'tab-2', title: 'Beta' },
]

function renderBar(over: Partial<Parameters<typeof TabBar>[0]> = {}) {
  const props = {
    tabs: TABS,
    activeTabId: 'tab-1',
    onSelect: vi.fn(),
    onClose: vi.fn(),
    onAdd: vi.fn(),
    ...over,
  }
  render(<TabBar {...props} />)
  return props
}

describe('TabBar', () => {
  it('renders one tab per graph with the active one selected', () => {
    renderBar()
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('aria-selected', 'false')
  })

  it('clicking a tab selects it', () => {
    const p = renderBar()
    fireEvent.click(screen.getByRole('tab', { name: 'Beta' }))
    expect(p.onSelect).toHaveBeenCalledWith('tab-2')
  })

  it('clicking × closes that tab', () => {
    const p = renderBar()
    fireEvent.click(screen.getByRole('button', { name: 'Close Beta' }))
    expect(p.onClose).toHaveBeenCalledWith('tab-2')
    expect(p.onSelect).not.toHaveBeenCalled()
  })

  it('clicking + fires onAdd', () => {
    const p = renderBar()
    fireEvent.click(screen.getByRole('button', { name: 'Open another graph' }))
    expect(p.onAdd).toHaveBeenCalledTimes(1)
  })
})
