import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const { runDownload } = vi.hoisted(() => ({ runDownload: vi.fn(async () => {}) }))
vi.mock('../api', () => ({ runDownload }))
import { ExportButton } from './ExportButton'

describe('ExportButton', () => {
  it('exports a story to its stable latest workbook on click', () => {
    render(<ExportButton story="US-VHLD" name="US-VHLD-sit" />)
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
    expect(runDownload).toHaveBeenCalledWith(
      'sit/US-VHLD-sit-latest.xlsx', { story: 'US-VHLD', name: 'US-VHLD-sit' })
  })

  it('passes a flow scope through when given a flow', () => {
    render(<ExportButton flow="vault-hold" name="vault-hold-sit" />)
    fireEvent.click(screen.getByRole('button', { name: /export/i }))
    expect(runDownload).toHaveBeenCalledWith(
      'sit/vault-hold-sit-latest.xlsx', { flow: 'vault-hold', name: 'vault-hold-sit' })
  })
})
