import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { bootstrap, getState, runAction, getProjects, runDownload } from './api'

function mockFetch(impl: (url: string, init?: RequestInit) => unknown) {
  const spy = vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => impl(url, init),
  }))
  vi.stubGlobal('fetch', spy)
  return spy
}

beforeEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('sends the bootstrapped token on actions', async () => {
    const spy = mockFetch((url) =>
      url === '/api/token' ? { token: 'tok-123' } : { rc: 0, argv: [], stdout: '', stderr: '' },
    )
    await bootstrap()
    await runAction('lint')
    const init = spy.mock.calls[1][1] as RequestInit
    expect((init.headers as Record<string, string>)['X-TC-Token']).toBe('tok-123')
    expect(init.method).toBe('POST')
  })

  it('posts params as a JSON body', async () => {
    const spy = mockFetch(() => ({ token: 't', rc: 0, argv: [], stdout: '', stderr: '' }))
    await bootstrap()
    await runAction('gate', { story: 'US-VHLD' })
    const init = spy.mock.calls[1][1] as RequestInit
    expect(JSON.parse(init.body as string)).toEqual({ params: { story: 'US-VHLD' } })
  })

  it('returns a non-zero rc as data, not an exception', async () => {
    // A refusal is the system working -- it must reach the caller, not throw.
    mockFetch(() => ({ token: 't', rc: 1, argv: ['gate'], stdout: 'GATE BLOCKED', stderr: '' }))
    await bootstrap()
    const res = await runAction('gate', { story: 'US-81FRM' })
    expect(res).toMatchObject({ rc: 1, stdout: 'GATE BLOCKED' })
  })

  it('throws when the state endpoint fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 })))
    await expect(getState()).rejects.toThrow('500')
  })

  it('throws when the token endpoint fails', async () => {
    // Otherwise bootstrap() silently leaves the token empty and every later
    // action 403s with no indication why.
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 })))
    await expect(bootstrap()).rejects.toThrow('500')
  })
})

describe('getProjects', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('unwraps the projects array from the response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        projects: [{
          id: 'tc-copilot', product: 'DEMO', branch: 'main', phase: 2,
          counts: { stories: 1, tcs: 2 }, next: null,
        }],
      }),
    }))
    const ps = await getProjects()
    expect(ps).toHaveLength(1)
    expect(ps[0].product).toBe('DEMO')
    expect(ps[0].phase).toBe(2)
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    await expect(getProjects()).rejects.toThrow(/api\/projects/)
  })
})

describe('runDownload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('runs the export action then triggers a browser download of the artifact', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/token') {
        return new Response(JSON.stringify({ token: 'tok-123' }), { status: 200 })
      }
      return new Response(JSON.stringify({ argv: ['export'], rc: 0, stdout: 'ok', stderr: '' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await bootstrap()
    await runDownload('sit/US-VHLD-sit-latest.xlsx', { story: 'US-VHLD', name: 'US-VHLD-sit' })

    const url = fetchMock.mock.calls[1][0]
    expect(url).toBe('/api/action/export')
    const body = JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)
    expect(body).toEqual({ params: { story: 'US-VHLD', name: 'US-VHLD-sit' } })
    expect(click).toHaveBeenCalledTimes(1)
  })

  it('downloads an existing artifact without running an action when no params are given', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await runDownload('sit/US-VHLD-sit-latest.xlsx')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(click).toHaveBeenCalledTimes(1)
  })

  it('throws when the export refuses (rc != 0) so the UI can surface it', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/token') {
        return new Response(JSON.stringify({ token: 'tok-123' }), { status: 200 })
      }
      return new Response(JSON.stringify({ argv: ['export'], rc: 2, stdout: 'REFUSED', stderr: '' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await bootstrap()
    await expect(runDownload('sit/x-latest.xlsx', { story: 'US-VHLD', name: 'x' }))
      .rejects.toThrow(/REFUSED/)
  })
})
