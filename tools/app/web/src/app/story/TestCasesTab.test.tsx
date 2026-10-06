import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { TestCasesTab } from './TestCasesTab'
import { PAYLOAD } from '../testcases/fixtures'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getTestCases: vi.fn(), onChange: vi.fn(() => () => {}) }
})
import * as api from '../api'

describe('TestCasesTab', () => {
  beforeEach(() => { vi.mocked(api.getTestCases).mockReset() })

  it('renders the review grid locked to the story', async () => {
    vi.mocked(api.getTestCases).mockResolvedValue(PAYLOAD)
    render(<TestCasesTab storyId="US-DEMO-002" />)
    expect(await screen.findByText('1 of 1 test cases')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /Run: Variant flow/ })).toBeInTheDocument()
    expect(screen.queryByRole('cell', { name: /Run: Main flow/ })).toBeNull()
    expect(screen.queryByRole('combobox', { name: 'Story' })).toBeNull()
  })

  it('shows a skeleton while loading and the error when the read fails', async () => {
    vi.mocked(api.getTestCases).mockRejectedValue(new Error('GET /api/testcases -> 500'))
    render(<TestCasesTab storyId="US-DEMO-001" />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(await screen.findByText(/api\/testcases -> 500/)).toBeInTheDocument()
  })

  it('subscribes to change events so a saved edit reloads the grid', async () => {
    vi.mocked(api.getTestCases).mockResolvedValue(PAYLOAD)
    render(<TestCasesTab storyId="US-DEMO-001" />)
    await screen.findByText('4 of 4 test cases')
    const reload = vi.mocked(api.onChange).mock.calls.at(-1)![0]
    await act(async () => { reload() })
    expect(api.getTestCases).toHaveBeenCalledTimes(2)
  })
})
