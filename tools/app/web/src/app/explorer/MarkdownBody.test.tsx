import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MarkdownBody } from './MarkdownBody'

describe('MarkdownBody', () => {
  it('renders markdown headings', () => {
    render(<MarkdownBody body={'# Summary\n\nHello'} onNavigate={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
  })
  it('intercepts a wiki-path link and navigates in-app', () => {
    const onNavigate = vi.fn()
    render(<MarkdownBody body={'See [MO](/glossary/mo.md).'} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByText('MO'))
    expect(onNavigate).toHaveBeenCalledWith('glossary/mo')
  })
})
