import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PhaseStepper } from './PhaseStepper'

describe('PhaseStepper', () => {
  it('renders the four phase labels', () => {
    render(<PhaseStepper phase={2} onSelect={vi.fn()} />)
    for (const label of ['Ingest', 'Alignment', 'Ready', 'Generated']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeInTheDocument()
    }
  })

  it('marks completed and current steps by class', () => {
    render(<PhaseStepper phase={2} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Ingest/ }).className).toContain('done')
    expect(screen.getByRole('button', { name: /Ready/ }).className).toContain('current')
    expect(screen.getByRole('button', { name: /Generated/ }).className).not.toContain('current')
  })

  it('is non-linear: clicking any step (even ahead) fires onSelect with its index', () => {
    const onSelect = vi.fn()
    render(<PhaseStepper phase={0} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /Generated/ }))
    expect(onSelect).toHaveBeenCalledWith(3)
  })
})
