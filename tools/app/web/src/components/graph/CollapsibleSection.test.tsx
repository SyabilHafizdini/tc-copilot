import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CollapsibleSection } from './CollapsibleSection'

describe('CollapsibleSection', () => {
  it('renders the title and shows children by default', () => {
    render(
      <CollapsibleSection title="Props">
        <p>body text</p>
      </CollapsibleSection>,
    )
    expect(screen.getByRole('button', { name: /props/i })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('body text')).toBeInTheDocument()
  })

  it('collapses and re-expands on header click', () => {
    render(
      <CollapsibleSection title="Props">
        <p>body text</p>
      </CollapsibleSection>,
    )
    const header = screen.getByRole('button', { name: /props/i })
    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('body text')).not.toBeInTheDocument()
    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('body text')).toBeInTheDocument()
  })

  it('starts collapsed when defaultOpen is false', () => {
    render(
      <CollapsibleSection title="Props" defaultOpen={false}>
        <p>body text</p>
      </CollapsibleSection>,
    )
    expect(screen.getByRole('button', { name: /props/i })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('body text')).not.toBeInTheDocument()
  })
})
