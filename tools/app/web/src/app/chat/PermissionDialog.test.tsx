import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PermissionDialog } from './PermissionDialog'

describe('PermissionDialog', () => {
  it('renders the title and reports the chosen response', () => {
    const onRespond = vi.fn()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const perm = { id: 'p1', title: 'Run: git status', sessionID: 's1' } as any
    render(<PermissionDialog permission={perm} onRespond={onRespond} />)
    expect(screen.getByText(/Run: git status/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /allow once/i }))
    expect(onRespond).toHaveBeenCalledWith('p1', 'once')
  })
})
