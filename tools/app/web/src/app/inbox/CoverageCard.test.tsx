import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CoverageCard } from './CoverageCard'
import type { CoverageCard as CC } from './types'

const card: CC = {
  file: 'coverage-US-VDTL-001.json', card_type: 'coverage', story: 'US-VDTL', emitted_at: '',
  coverage_status: 'proposed',
  map_corrections: [{ ac: '1.1.3.1.2-AC3', removed: [], added: ['CMP-VDTL-03'], reason: 'exact match' }],
  note: 'first run',
}

describe('CoverageCard', () => {
  it('shows status, a correction, and asserts', () => {
    const onAssert = vi.fn()
    render(<CoverageCard card={card} onAssert={onAssert} onDiscard={vi.fn()} />)
    expect(screen.getByText(/proposed/)).toBeInTheDocument()
    expect(screen.getByText(/1\.1\.3\.1\.2-AC3/)).toBeInTheDocument()
    expect(screen.getByText(/CMP-VDTL-03/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^assert$/i }))
    expect(onAssert).toHaveBeenCalled()
  })
})
