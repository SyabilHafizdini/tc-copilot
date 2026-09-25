import type { ExplorerSnapshot } from './explorer/types'
import type { InboxSnapshot } from './inbox/types'
import type { Message, Part, Event } from '@opencode-ai/sdk'
import type { View } from './shell/routes'

export type NextRow = {
  id: string
  state: string
  command: string | null
  skill: string
  scope: 'story' | 'flow'
  arg: string
}

export type PhaseRollup = {
  phase: 0 | 1 | 2 | 3
  label: string
  counts: {
    stories: Record<string, number>
    tcs: { active: number; stale: number; retired: number }
  }
}

export type InventoryItem = {
  file: string
  story: string | null
  kind: 'sit' | 'uat' | 'osat'
  mtime: string
}

export type State = {
  project: string
  prd: { adopted: string | null; staged: string | null }
  stories: Array<Record<string, unknown> & { id: string; status: string }>
  flows: Array<{ id: string; status: string }>
  cards: Array<{ file: string; type: string; story: string | null }>
  change_reports: Array<{ id: string; status: string }>
  totals: Record<string, number>
  next: { banners: NextRow[]; rows: NextRow[]; phase: PhaseRollup }
  inventory: InventoryItem[]
  suites: string[]
}

export type ProjectCard = {
  id: string
  product: string
  branch: string
  phase: 0 | 1 | 2 | 3
  counts: { stories: number; tcs: number }
  next: { label: string; view: View } | null
}

export type ActionResult = {
  argv: string[]
  rc: number
  stdout: string
  stderr: string
}

let token = ''

export async function bootstrap(): Promise<void> {
  const r = await fetch('/api/token')
  if (!r.ok) throw new Error(`GET /api/token -> ${r.status}`)
  token = (await r.json()).token
}

export async function getState(): Promise<State> {
  const r = await fetch('/api/state')
  if (!r.ok) throw new Error(`GET /api/state -> ${r.status}`)
  return r.json()
}

export async function getExplorer(): Promise<ExplorerSnapshot> {
  const r = await fetch('/api/explorer')
  if (!r.ok) throw new Error(`GET /api/explorer -> ${r.status}`)
  return r.json()
}

export type SuiteFilters = {
  kind?: string
  include_modules?: string[]
  exclude_modules?: string[]
  include_flows?: string[]
  exclude_flows?: string[]
  priorities?: string[]
}

export type SuitePreview = { count: number; ids: string[]; retired: number; stale: number }

// A pure read: POST carries the filter object, no side effects, no token.
export async function getSuitePreview(filters: SuiteFilters): Promise<SuitePreview> {
  const r = await fetch('/api/suite_preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filters }),
  })
  if (!r.ok) throw new Error(`POST /api/suite_preview -> ${r.status}`)
  return r.json()
}

export async function getInbox(): Promise<InboxSnapshot> {
  const r = await fetch('/api/inbox')
  if (!r.ok) throw new Error(`GET /api/inbox -> ${r.status}`)
  return r.json()
}

export async function getProjects(): Promise<ProjectCard[]> {
  const r = await fetch('/api/projects')
  if (!r.ok) throw new Error(`GET /api/projects -> ${r.status}`)
  return (await r.json()).projects
}

// Returns the CLI's own result. A non-zero rc is not an error here -- a
// refusal is the system working, and its text is rendered verbatim.
export async function runAction(
  name: string,
  params: Record<string, unknown> = {},
): Promise<ActionResult | { error: string }> {
  const r = await fetch(`/api/action/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-TC-Token': token },
    body: JSON.stringify({ params }),
  })
  return r.json()
}

// Triggers a browser download of build/inventory/<artifact>. When `params.name`
// is given, the export action is run first (writing the artifact) and only then
// is the download triggered; a refusal (rc != 0) throws so the UI can render it.
// With no params (or an empty `{}` — e.g. a suite's already-compiled workbook),
// an already-built artifact is downloaded as-is, no export run.
export async function runDownload(
  artifact: string,
  params?: { story?: string; flow?: string; name?: string },
): Promise<void> {
  if (params?.name) {
    const res = await runAction('export', params)
    if ('error' in res) throw new Error(res.error)
    if (res.rc !== 0) throw new Error(res.stdout + res.stderr)
  }
  const a = document.createElement('a')
  a.href = `/api/download/${artifact}`
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

// onDisconnect fires whenever the underlying EventSource errors -- including
// transient drops it auto-reconnects from -- so the caller can surface a
// "live updates disconnected" notice without this module deciding UI policy.
export function onChange(cb: () => void, onDisconnect?: () => void): () => void {
  const es = new EventSource('/api/events')
  es.onmessage = (e) => {
    if (JSON.parse(e.data).changed) cb()
  }
  es.onerror = () => onDisconnect?.()
  return () => es.close()
}

export type ChatHealth = { available: boolean; reason: string; model: string }

export async function chatHealth(): Promise<ChatHealth> {
  const r = await fetch('/api/chat/health')
  if (!r.ok) throw new Error(`GET /api/chat/health -> ${r.status}`)
  return r.json()
}

export async function createChatSession(): Promise<{ id: string }> {
  const r = await fetch('/api/chat/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-TC-Token': token },
    body: '{}',
  })
  if (!r.ok) throw new Error(`POST /api/chat/session -> ${r.status}`)
  return r.json()
}

export async function getChatMessages(sid: string): Promise<Array<{ info: Message; parts: Part[] }>> {
  const r = await fetch(`/api/chat/session/${sid}/message`)
  if (!r.ok) throw new Error(`GET messages -> ${r.status}`)
  return r.json()
}

export async function sendChatPrompt(session: string, text: string): Promise<void> {
  await fetch('/api/chat/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-TC-Token': token },
    body: JSON.stringify({ session, text }),
  })
}

export async function abortChat(session: string): Promise<void> {
  await fetch('/api/chat/abort', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-TC-Token': token },
    body: JSON.stringify({ session }),
  })
}

export async function respondPermission(
  session: string,
  permission: string,
  response: 'once' | 'always' | 'reject',
): Promise<void> {
  await fetch('/api/chat/permission', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-TC-Token': token },
    body: JSON.stringify({ session, permission, response }),
  })
}

export function onChatEvents(cb: (e: Event) => void): () => void {
  const es = new EventSource('/api/chat/event')
  es.onmessage = (m) => {
    try {
      cb(JSON.parse(m.data))
    } catch {
      /* ignore */
    }
  }
  return () => es.close()
}
