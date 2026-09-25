import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

vi.mock('../api', () => ({
  getProjects: vi.fn().mockResolvedValue([{
    id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
    counts: { stories: 1, tcs: 2 }, next: null,
  }]),
}))

import { useProject } from './useProject'

afterEach(() => { window.location.hash = '' })

describe('useProject', () => {
  it('loads projects and defaults id to the first', async () => {
    const { result } = renderHook(() => useProject())
    await waitFor(() => expect(result.current.all).toHaveLength(1))
    expect(result.current.id).toBe('tc-copilot')
  })

  it('switch selects the project and navigates to Explore (the file directory)', () => {
    const { result } = renderHook(() => useProject())
    act(() => { result.current.switch('tc-copilot') })
    expect(result.current.id).toBe('tc-copilot')
    expect(window.location.hash).toBe('#/explore')
  })
})
