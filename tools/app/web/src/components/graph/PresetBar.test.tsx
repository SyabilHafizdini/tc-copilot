import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PresetBar } from './PresetBar'
import type { GraphPreset } from '../../lib/types'

const presets: GraphPreset[] = [
  { name: 'Login flow', description: 'Pages to API' },
  { name: 'Fields only' },
]

describe('PresetBar', () => {
  it('renders nothing when there are no presets', () => {
    const { container } = render(
      <PresetBar presets={[]} activeName={null} onApply={vi.fn()} onClear={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders a chip per preset with the description as tooltip', () => {
    render(<PresetBar presets={presets} activeName={null} onApply={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Login flow' })).toHaveAttribute('title', 'Pages to API')
    expect(screen.getByRole('button', { name: 'Fields only' })).toBeInTheDocument()
  })

  it('marks the active chip pressed and calls onClear when it is clicked', () => {
    const onApply = vi.fn()
    const onClear = vi.fn()
    render(<PresetBar presets={presets} activeName="Login flow" onApply={onApply} onClear={onClear} />)
    const active = screen.getByRole('button', { name: 'Login flow' })
    expect(active).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(active)
    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onApply).not.toHaveBeenCalled()
  })

  it('calls onApply with the preset when an inactive chip is clicked', () => {
    const onApply = vi.fn()
    render(<PresetBar presets={presets} activeName={null} onApply={onApply} onClear={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Fields only' }))
    expect(onApply).toHaveBeenCalledWith(presets[1])
  })
})
