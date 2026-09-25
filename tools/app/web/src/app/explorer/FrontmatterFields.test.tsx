import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FrontmatterFields } from './FrontmatterFields'
import type { Field } from './types'

const fields: Field[] = [
  { key: 'module', kind: 'link', ref: '/modules/pm.md', label: 'pm.md' },
  { key: 'acceptance_criteria', kind: 'itemized', items: [{ id: 'AC1', text: 'do a thing', status: 'active' }] },
]

describe('FrontmatterFields', () => {
  it('navigates on a link click with a normalised node id', () => {
    const onNavigate = vi.fn()
    render(<FrontmatterFields fields={fields} onNavigate={onNavigate} onFocusItem={vi.fn()} />)
    fireEvent.click(screen.getByText('pm.md'))
    expect(onNavigate).toHaveBeenCalledWith('modules/pm')
  })
  it('focuses an AC item on click and shows its status', () => {
    const onFocusItem = vi.fn()
    render(<FrontmatterFields fields={fields} onNavigate={vi.fn()} onFocusItem={onFocusItem} />)
    expect(screen.getByText('active')).toBeInTheDocument()
    fireEvent.click(screen.getByText('AC1'))
    expect(onFocusItem).toHaveBeenCalledWith('AC1')
  })

  it('renders an itemized field as a compact table (ID · Status · Criterion), not stacked blocks', () => {
    const { container } = render(<FrontmatterFields fields={fields} onNavigate={vi.fn()} onFocusItem={vi.fn()} />)
    const table = container.querySelector('.itemized-table')
    expect(table).not.toBeNull()
    expect([...table!.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['Key', 'Status', 'Criterion'])
    const row = table!.querySelector('tbody tr')!
    expect(row.querySelector('td.crit')?.textContent).toBe('do a thing')
    expect(container.querySelector('.fm-item')).toBeNull()
  })
})

describe('FrontmatterFields itemized keys drill down', () => {
  const fields = [{
    key: 'acceptance_criteria', kind: 'itemized' as const,
    items: [{ id: '1.1.3.1.1-AC1', text: 'do a thing', status: 'active' }],
  }]

  it('single click on a Key focuses the item (Jira link behavior, no chat toggle)', () => {
    const onFocusItem = vi.fn()
    render(<FrontmatterFields fields={fields} onNavigate={() => {}} onFocusItem={onFocusItem} />)
    // display shows the short id; full id stays in the tooltip + callback
    fireEvent.click(screen.getByRole('button', { name: 'AC1' }))
    expect(onFocusItem).toHaveBeenCalledWith('1.1.3.1.1-AC1')
  })
})
