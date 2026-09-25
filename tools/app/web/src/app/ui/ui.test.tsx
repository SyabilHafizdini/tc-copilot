import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pill, Button, StatTile, Banner, Breadcrumb, Console, Skeleton, Spinner, PageSkeleton } from './index'

describe('loading states', () => {
  it('Skeleton renders the requested shimmer lines and announces politely', () => {
    const { container } = render(<Skeleton lines={3} header />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(container.querySelectorAll('.skel-line')).toHaveLength(3)
    expect(container.querySelector('.skel-header')).not.toBeNull()
  })
  it('Spinner is a sized status element', () => {
    render(<Spinner size={14} label="Resolving" />)
    expect(screen.getByRole('status', { name: 'Resolving' })).toBeInTheDocument()
  })
  it('PageSkeleton wraps a skeleton in the page frame', () => {
    const { container } = render(<PageSkeleton />)
    expect(container.querySelector('.page .skeleton-block')).not.toBeNull()
  })
})

describe('Breadcrumb', () => {
  it('renders link crumbs with separators and a plain terminal crumb', () => {
    const onClick = vi.fn()
    const { container } = render(
      <Breadcrumb items={[{ label: 'Projects', onClick }, { label: 'US-VHLD' }]} />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Projects' }))
    expect(onClick).toHaveBeenCalledOnce()
    // the terminal crumb is current-location text, not a button
    expect(screen.queryByRole('button', { name: 'US-VHLD' })).toBeNull()
    expect(container.querySelector('.crumb.current')?.textContent).toBe('US-VHLD')
    expect(container.querySelector('.explore-breadcrumb')?.textContent).toContain(' / ')
  })
})

describe('Pill', () => {
  it('maps state to the semantic class', () => {
    const { container } = render(<Pill state="ready">ready</Pill>)
    expect(container.querySelector('.pill.ready')).not.toBeNull()
    expect(screen.getByText('ready')).toBeInTheDocument()
  })
})

describe('Button', () => {
  it('adds the variant class and fires onClick', () => {
    const onClick = vi.fn()
    const { container } = render(<Button variant="primary" onClick={onClick}>gate</Button>)
    const btn = screen.getByRole('button', { name: 'gate' })
    expect(container.querySelector('.btn.primary')).not.toBeNull()
    fireEvent.click(btn)
    expect(onClick).toHaveBeenCalledOnce()
  })
  it('is never disabled', () => {
    render(<Button>lint</Button>)
    expect(screen.getByRole('button', { name: 'lint' })).not.toBeDisabled()
  })
})

describe('StatTile', () => {
  it('renders number, label and sub', () => {
    render(<StatTile n={91} label="test cases" sub="0 stale" />)
    expect(screen.getByText('91')).toBeInTheDocument()
    expect(screen.getByText('test cases')).toBeInTheDocument()
    expect(screen.getByText('0 stale')).toBeInTheDocument()
  })
})

describe('Banner', () => {
  it('shows a dismiss control when onDismiss is given', () => {
    const onDismiss = vi.fn()
    render(<Banner tone="blocked" onDismiss={onDismiss}>boom</Banner>)
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})

describe('Console', () => {
  it('shows the argv, output, and a green exit badge on rc 0', () => {
    render(<Console result={{ argv: ['status'], rc: 0, stdout: 'ok', stderr: '' }} />)
    expect(screen.getByText(/status/)).toBeInTheDocument()
    expect(screen.getByText('ok')).toBeInTheDocument()
    expect(screen.getByText(/exit 0/)).toHaveClass('exit', 'ok')
  })
  it('renders a refusal verbatim with a red exit badge on non-zero rc', () => {
    render(<Console result={{
      argv: ['gate', '--story', 'US-81FRM'], rc: 1,
      stdout: "GATE BLOCKED:\n - story stories/US-81FRM is 'draft', not aligned (spec §7.1)", stderr: '',
    }} />)
    expect(screen.getByText(/GATE BLOCKED/)).toBeInTheDocument()
    expect(screen.getByText(/exit 1/)).toHaveClass('exit', 'bad')
  })
})
