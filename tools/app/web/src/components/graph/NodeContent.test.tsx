import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NodeContent } from './NodeContent'

describe('NodeContent', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('renders nothing for empty or whitespace markdown', () => {
    const { container } = render(<NodeContent markdown="   " />)
    expect(container.firstChild).toBeNull()
  })

  it('renders markdown structure (heading, bold, list)', () => {
    render(<NodeContent markdown={'# Title\n\n**bold**\n\n- item one'} />)
    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument()
    expect(screen.getByText('bold').tagName).toBe('STRONG')
    expect(screen.getByText('item one').closest('li')).not.toBeNull()
  })

  it('renders a fenced code block with a language label, copy button, and highlight classes', () => {
    render(<NodeContent markdown={'```tsx\nconst x = 1\n```'} />)
    const block = screen.getByTestId('code-block')
    expect(block).toBeInTheDocument()
    expect(block).toHaveTextContent('tsx')
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument()
    // rehype-highlight tags the <code> with the hljs class
    expect(block.querySelector('code.hljs')).not.toBeNull()
  })

  it('copies the code text when the copy button is clicked', () => {
    render(<NodeContent markdown={'```\nhello world\n```'} />)
    fireEvent.click(screen.getByRole('button', { name: /copy code/i }))
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('hello world'))
  })

  it('does not execute raw HTML embedded in the markdown', () => {
    const { container } = render(
      <NodeContent markdown={'<script>window.__pwned = 1</script>\n\nafter'} />,
    )
    expect(container.querySelector('script')).toBeNull()
    // the surrounding markdown still renders
    expect(screen.getByText('after')).toBeInTheDocument()
  })

  it('opens external links in a new tab safely', () => {
    render(<NodeContent markdown={'[site](https://example.com)'} />)
    const link = screen.getByRole('link', { name: 'site' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('renders a data-URI image but not a remote one (self-contained)', () => {
    const { container, rerender } = render(
      <NodeContent markdown={'![pixel](data:image/gif;base64,R0lGODlhAQABAAAAACw=)'} />,
    )
    expect(container.querySelector('img')).not.toBeNull()

    rerender(<NodeContent markdown={'![remote](https://evil.example/x.png)'} />)
    // no <img> pointing at the remote host — it renders as a link instead
    expect(container.querySelector('img[src^="https://evil"]')).toBeNull()
    expect(screen.getByRole('link', { name: 'remote' })).toHaveAttribute('href', 'https://evil.example/x.png')
  })
})
