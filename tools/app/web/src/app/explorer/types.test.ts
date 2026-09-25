import { describe, expect, it, vi, afterEach } from 'vitest'
import { getExplorer } from '../api'

afterEach(() => vi.restoreAllMocks())

describe('getExplorer', () => {
  it('GETs /api/explorer and returns the snapshot', async () => {
    const snap = { tree: [], docs: {}, graph: { nodes: [], links: [] } }
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => snap })))
    expect(await getExplorer()).toEqual(snap)
    expect(fetch).toHaveBeenCalledWith('/api/explorer')
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 })))
    await expect(getExplorer()).rejects.toThrow(/api\/explorer/)
  })
})
