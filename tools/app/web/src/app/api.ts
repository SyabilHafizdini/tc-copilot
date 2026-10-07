import type { ExplorerSnapshot } from './explorer/types'
import type { InboxSnapshot } from './inbox/types'
import type { Message, Part, Event } from '@opencode-ai/sdk'
import type { View } from './shell/routes'
import type { EditableField, TestCasesPayload } from './testcases/types'
import type { WorkbookEntry, WorkbookInventory, WorkbookPayload } from './workbook/types'

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

export type Prd = { id: string; title: string; adopted: number | null; staged: number | null }

export type ChangeReport = {
  id: string
  status: string
  prd?: string | null
  from?: number | null
  to?: number | null
}

export type State = {
  // A project written before the PRD registry (manifest schema 1). Its PRD
  // list is empty whatever was adopted or staged, and every action except
  // status and lint is refused until it is migrated; `notice` is the text the
  // refusals print, and null on a migrated project.
  schema1: boolean
  notice: string | null
  project: string
  prds: Prd[]
  stories: Array<Record<string, unknown> & { id: string; status: string }>
  flows: Array<{ id: string; status: string }>
  cards: Array<{ file: string; type: string; story: string | null }>
  change_reports: ChangeReport[]
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

// The review grid: every test case as the workbook's C-TC sheet shows it.
export async function getTestCases(): Promise<TestCasesPayload> {
  const r = await fetch('/api/testcases')
  if (!r.ok) throw new Error(`GET /api/testcases -> ${r.status}`)
  return r.json()
}

export type SuiteFilters = {
  kind?: string
  include_modules?: string[]
  exclude_modules?: string[]
  include_flows?: string[]
  exclude_flows?: string[]
  priorities?: string[]
  include_prds?: string[]
  exclude_prds?: string[]
}

export type SuitePreview = { count: number; ids: string[]; retired: number; stale: number }

// A pure read: POST carries the filter object, no side effects, no token.
export async function getSuitePreview(filters: SuiteFilters): Promise<SuitePreview> {
  const r = await fetch('/api/suite_preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filters }),
  })
  if (!r.ok) {
    // A refused filter (an unknown PRD id) carries the server's own words.
    const body = await r.json().catch(() => null) as { error?: string } | null
    throw new Error(body?.error ?? `POST /api/suite_preview -> ${r.status}`)
  }
  return r.json()
}

// The Flow Builder's read model (tools/wiki_flowdraft.py builder_model): story
// criteria with their SIT test cases, and the existing flows' journeys.
export type BuilderModel = {
  project: string
  code: string | null
  stories: Array<{
    id: string; title: string | null; status: string
    // title: the criterion's short name, where the story gives one
    acs: Array<{ id: string; title?: string | null; text: string; status: string | null; tcs: string[] }>
  }>
  flows: Array<{
    id: string; title: string | null; status: string; entry_condition: string | null
    journey: Array<{
      id: string; end_state: string | null; note: string | null; ac_ref: string | null
      source_tc: string | null
      branch: { id: string; title: string | null } | null
    }>
  }>
  // acs: the "<story id>#<criterion id>" refs the test case covers
  tcs: Record<string, { id: string; title: string | null; acs: string[]; sections: Record<string, string> }>
  // the Flow Overview's own: the page title a project may set, and the test
  // case row behind each journey entry, keyed "<flow id>#<entry id>"
  overview_title?: string | null
  journey_tcs?: Record<string, JourneyTc>
}

// One test case as its workbook row prints it; text keeps its **bold** markers.
export type JourneyTc = {
  id: string; section: string | null; confidence: string
  scenario: string; steps: string; data: string; expected: string; remarks: string
}

export async function getFlowBuilder(): Promise<BuilderModel> {
  const r = await fetch('/api/flow_builder')
  if (!r.ok) throw new Error(`GET /api/flow_builder -> ${r.status}`)
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

// Rewords one field of one test case through the `tc_edit` action. The CLI's
// own result comes back: rc 0 is saved, a non-zero rc is a refusal whose text
// the caller shows verbatim. A request the server rejected outright (bad
// params, lost token) throws, so it can never be mistaken for a save.
export async function editTestCase(id: string, field: EditableField, text: string): Promise<ActionResult> {
  const res = await runAction('tc_edit', { id, field, text })
  if ('error' in res) throw new Error(res.error)
  return res
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
  // Each segment is encoded on its own: a workbook name may hold a character
  // (#, ?, %, a space) that would otherwise cut or change the path.
  a.href = `/api/download/${artifact.split('/').map(encodeURIComponent).join('/')}`
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

// One compiled workbook, drawn from the file. A 404 (no such file) or a 422
// (unreadable file) carries the server's own words in `error`; they are thrown
// so the page can show them.
export async function getWorkbook(kind: string, file: string): Promise<WorkbookPayload> {
  const r = await fetch(
    `/api/workbook/${encodeURIComponent(kind)}/${encodeURIComponent(file)}`)
  if (!r.ok) throw await serverError(r, 'GET /api/workbook')
  return r.json()
}

// A failed read as an Error carrying the server's own words (`error` in the
// body) when it sent any, else the request and its status.
async function serverError(r: Response, what: string): Promise<Error> {
  const body = await r.json().catch(() => null) as { error?: string } | null
  return new Error(typeof body?.error === 'string' && body.error ? body.error : `${what} -> ${r.status}`)
}

// The inventory, newest compile first, one entry per workbook name, and the
// files the server could not read (it names them instead of dropping them).
export async function getWorkbookInventory(): Promise<WorkbookInventory> {
  const r = await fetch('/api/workbooks')
  if (!r.ok) throw await serverError(r, 'GET /api/workbooks')
  const body = await r.json() as Partial<WorkbookInventory>
  return { workbooks: body.workbooks ?? [], skipped: body.skipped ?? [] }
}

export async function getWorkbooks(): Promise<WorkbookEntry[]> {
  return (await getWorkbookInventory()).workbooks
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
