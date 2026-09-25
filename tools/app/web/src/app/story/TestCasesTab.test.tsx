import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { TestCasesTab } from './TestCasesTab'
import type { TcRow } from './testcases'

const ROWS: TcRow[] = [
  { id: 'SIT-1', title: 'Change filter', level: 'sit', status: 'active', ac: 'AC8',
    steps: [{ n: 1, action: 'Add Workshop Y', data: 'Workshop=Y', expected: 'Widgets refresh' }] },
  { id: 'UAT-1', title: 'Access dashboard', level: 'uat', status: 'active', ac: 'AC1',
    steps: [{ n: 1, action: 'Log in', data: '', expected: 'Dashboard shown' }] },
]

describe('TestCasesTab', () => {
  it('renders the step table columns and step content', () => {
    const { container } = render(<TestCasesTab rows={ROWS} />)
    const firstCard = container.querySelector('.card') as HTMLElement
    expect(within(firstCard).getByText('Action')).toBeInTheDocument()
    expect(within(firstCard).getByText('Test data')).toBeInTheDocument()
    expect(within(firstCard).getByText('Expected result')).toBeInTheDocument()
    expect(screen.getByText('Add Workshop Y')).toBeInTheDocument()
  })

  it('the level sub-filter narrows to a single level', () => {
    render(<TestCasesTab rows={ROWS} />)
    fireEvent.click(screen.getByRole('button', { name: 'UAT' }))
    expect(screen.getByText('Access dashboard')).toBeInTheDocument()
    expect(screen.queryByText('Change filter')).not.toBeInTheDocument()
  })

  it('shows an empty state for a level with no test cases', () => {
    render(<TestCasesTab rows={ROWS} />)
    fireEvent.click(screen.getByRole('button', { name: 'OSAT' }))
    expect(screen.getByText(/No test cases at this level/)).toBeInTheDocument()
  })
})
