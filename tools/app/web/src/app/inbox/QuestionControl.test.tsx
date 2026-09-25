import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QuestionControl } from './QuestionControl'

const q = { id: 'Q1', about: 'AC1', question: 'Which name?', proposed: 'View details' }

describe('QuestionControl', () => {
  it('shows the question and proposed answer', () => {
    render(<QuestionControl question={q} value="accept" onChange={vi.fn()} />)
    expect(screen.getByText(/Which name\?/)).toBeInTheDocument()
    expect(screen.getByText(/View details/)).toBeInTheDocument()
  })
  it('emits the typed correction when correcting', () => {
    const onChange = vi.fn()
    render(<QuestionControl question={q} value="accept" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /correct/i }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Vehicle name' } })
    expect(onChange).toHaveBeenLastCalledWith('Vehicle name')
  })
  it('emits the descope sentinel when de-scoped', () => {
    const onChange = vi.fn()
    render(<QuestionControl question={q} value="accept" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /de-scope/i }))
    expect(onChange).toHaveBeenCalledWith('descope')
  })
})
