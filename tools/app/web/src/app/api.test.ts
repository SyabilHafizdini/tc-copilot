import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { bootstrap, getState, runAction, getProjects, runDownload, getTestCases, editTestCase, getWorkbook, getWorkbooks, getWorkbookInventory, getSuitePreview } from './api'

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

describe('getSuitePreview', () => {
  it('posts the PRD filters as given and throws the server message on a 400', async () => {
    const spy = vi.fn(async () => ({
      ok: false, status: 400, json: async () => ({ error: "unknown PRD id 'nope'" }),
    }))
    vi.stubGlobal('fetch', spy)
    await expect(getSuitePreview({ kind: 'sit', include_prds: ['nope'] }))
      .rejects.toThrow("unknown PRD id 'nope'")
    const init = (spy.mock.calls[0] as unknown as [string, RequestInit])[1]
    expect(JSON.parse(init.body as string))
      .toEqual({ filters: { kind: 'sit', include_prds: ['nope'] } })
  })
})

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

describe('workbook reads', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('requests one workbook by kind and file, both path-encoded', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ name: 'a b' }) })
    vi.stubGlobal('fetch', spy)
    const book = await getWorkbook('sit', 'a b-latest.xlsx')
    expect(spy).toHaveBeenCalledWith('/api/workbook/sit/a%20b-latest.xlsx')
    expect(book.name).toBe('a b')
  })

  it("throws the server's own error text for an unreadable workbook", async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 422, json: async () => ({ error: 'cannot read x-latest.xlsx: BadZipFile' }),
    }))
    await expect(getWorkbook('sit', 'x-latest.xlsx')).rejects.toThrow('cannot read x-latest.xlsx')
  })

  it('falls back to the status when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 500, json: async () => { throw new Error('not json') },
    }))
    await expect(getWorkbook('sit', 'x-latest.xlsx')).rejects.toThrow('500')
  })

  it('unwraps the workbooks array', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ workbooks: [{ name: 'demo' }] }),
    }))
    expect((await getWorkbooks())[0].name).toBe('demo')
  })

  it('reads the inventory with the files the server skipped', async () => {
    const skipped = [{ kind: 'sit', file: 'x-latest.xlsx', error: 'cannot read x-latest.xlsx: BadZipFile' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ workbooks: [{ name: 'demo' }], skipped }),
    }))
    expect(await getWorkbookInventory()).toEqual({ workbooks: [{ name: 'demo' }], skipped })
    // a server that sends no `skipped` (older) reads as none skipped
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ workbooks: [] }) }))
    expect(await getWorkbookInventory()).toEqual({ workbooks: [], skipped: [] })
  })

  it("throws the server's own words when the inventory cannot be listed", async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 500, json: async () => ({ error: 'manifest.json has schema_version "two"' }),
    }))
    await expect(getWorkbooks()).rejects.toThrow('manifest.json has schema_version "two"')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 502, json: async () => { throw new Error('not json') },
    }))
    await expect(getWorkbookInventory()).rejects.toThrow('GET /api/workbooks -> 502')
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

  it('encodes each path segment of the artifact, keeping the slash between them', async () => {
    vi.stubGlobal('fetch', vi.fn())
    let href = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      href = this.getAttribute('href') ?? ''
    })
    await runDownload('sit/a b#1?x%_20261003-090000.xlsx')
    expect(href).toBe('/api/download/sit/a%20b%231%3Fx%25_20261003-090000.xlsx')
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

describe('getTestCases', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads the grid payload from /api/testcases', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ rows: [], groups: [] }) })
    vi.stubGlobal('fetch', spy)
    expect(await getTestCases()).toEqual({ rows: [], groups: [] })
    expect(spy.mock.calls[0][0]).toBe('/api/testcases')
  })

  it('throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    await expect(getTestCases()).rejects.toThrow(/api\/testcases -> 500/)
  })
})

describe('editTestCase', () => {
  it('posts id, field and text to the tc_edit action with the token', async () => {
    const spy = mockFetch((url) =>
      url === '/api/token' ? { token: 'tok-9' } : { rc: 0, argv: ['tc', 'edit'], stdout: 'saved', stderr: '' })
    await bootstrap()
    const res = await editTestCase('1.1-AC02-01', 'steps', '1. Click **Go**.\n2. Wait.')
    expect(spy.mock.calls[1][0]).toBe('/api/action/tc_edit')
    const init = spy.mock.calls[1][1] as RequestInit
    expect((init.headers as Record<string, string>)['X-TC-Token']).toBe('tok-9')
    expect(JSON.parse(init.body as string)).toEqual(
      { params: { id: '1.1-AC02-01', field: 'steps', text: '1. Click **Go**.\n2. Wait.' } })
    expect(res.rc).toBe(0)
  })

  it('returns a refusal (non-zero rc) as data', async () => {
    mockFetch(() => ({ token: 't', rc: 1, argv: ['tc', 'edit'], stdout: '', stderr: 'tc edit refused: x' }))
    await bootstrap()
    expect(await editTestCase('1.1-AC02-01', 'steps', 'x')).toMatchObject({ rc: 1, stderr: 'tc edit refused: x' })
  })

  it('throws when the server rejects the request outright', async () => {
    mockFetch(() => ({ token: 't', error: "field not editable: 'confidence'" }))
    await bootstrap()
    await expect(editTestCase('1.1-AC02-01', 'steps', 'x')).rejects.toThrow(/field not editable/)
  })
})