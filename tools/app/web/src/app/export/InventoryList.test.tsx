import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { InventoryItem } from '../api'

const { runDownload } = vi.hoisted(() => ({ runDownload: vi.fn(async () => {}) }))
vi.mock('../api', () => ({ runDownload }))
import { InventoryList } from './InventoryList'

const items: InventoryItem[] = [
  { file: 'sit/US-VHLD-sit-latest.xlsx', story: 'US-VHLD', kind: 'sit', mtime: '2026-08-10T12:00:00+00:00' },
  { file: 'uat/regression-latest.xlsx', story: null, kind: 'uat', mtime: '2026-08-10T13:00:00+00:00' },
]

describe('InventoryList', () => {
  it('shows an empty-state hint when there are no workbooks', () => {
    render(<InventoryList items={[]} />)
    expect(screen.getByText(/no workbooks/i)).toBeInTheDocument()
  })

  it('lists workbooks and downloads the existing artifact on click', () => {
    render(<InventoryList items={items} />)
    expect(screen.getByText('US-VHLD')).toBeInTheDocument()
    expect(screen.getByText('SIT')).toBeInTheDocument()
    expect(screen.getByText('UAT')).toBeInTheDocument()
    const downloads = screen.getAllByRole('button', { name: /download/i })
    fireEvent.click(downloads[0])
    expect(runDownload).toHaveBeenCalledWith('sit/US-VHLD-sit-latest.xlsx')
  })
})
