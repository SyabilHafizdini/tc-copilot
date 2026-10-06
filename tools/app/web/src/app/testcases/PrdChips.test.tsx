import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { PrdChips } from './PrdChips'

describe('PrdChips', () => {
  it('renders one chip per PRD in a labelled group and reports the pressed one', () => {
    const onToggle = vi.fn()
    render(<PrdChips options={['rental-application', 'rental-payment']} selected={['rental-payment']} onToggle={onToggle} />)
    const group = screen.getByRole('group', { name: 'PRD' })
    expect(within(group).getByRole('button', { name: 'rental-payment' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: 'rental-application' })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(within(group).getByRole('button', { name: 'rental-application' }))
    expect(onToggle).toHaveBeenCalledWith('rental-application')
  })

  it('labels a chip with the PRD title when one is known, the id otherwise', () => {
    const onToggle = vi.fn()
    render(<PrdChips options={['rental-application', 'rental-payment']} selected={[]} onToggle={onToggle}
      titles={{ 'rental-application': 'Rental application' }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Rental application' }))
    expect(onToggle).toHaveBeenCalledWith('rental-application')
    expect(screen.getByRole('button', { name: 'rental-payment' })).toBeInTheDocument()
  })

  it('renders nothing when no test case draws on a PRD', () => {
    const { container } = render(<PrdChips options={[]} selected={[]} onToggle={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})
