import type { ExplorerSnapshot, DocView, Field } from '../explorer/types'

export type TcLevel = 'sit' | 'uat' | 'osat'
export type StepRow = { n: number; action: string; data: string; expected: string }
export type TcRow = { id: string; title: string | null; level: TcLevel; status: string | null; ac: string | null; steps: StepRow[] }

export function levelOf(ref: string): TcLevel | null {
  if (ref.includes('testcases/sit/')) return 'sit'
  if (ref.includes('testcases/uat/')) return 'uat'
  if (ref.includes('testcases/osat/')) return 'osat'
  return null
}

// Pull the lines that follow a `# Heading` up to the next `# ` heading.
function section(bodyMd: string, heading: string): string[] {
  const lines = bodyMd.split('\n')
  const out: string[] = []
  let inSec = false
  for (const ln of lines) {
    if (/^#\s+/.test(ln)) {
      inSec = ln.replace(/^#\s+/, '').trim() === heading
      continue
    }
    if (inSec && ln.trim()) out.push(ln.trim())
  }
  return out
}

// Ordered-list items ("1. foo") with the marker stripped.
function orderedItems(lines: string[]): string[] {
  return lines.filter((l) => /^\d+\.\s+/.test(l)).map((l) => l.replace(/^\d+\.\s+/, '').trim())
}

export function parseTcSteps(bodyMd: string): StepRow[] {
  const actions = orderedItems(section(bodyMd, 'Steps'))
  const expected = orderedItems(section(bodyMd, 'Expected Results'))
  const data = section(bodyMd, 'Test Data').join(' ').trim()
  const n = Math.max(actions.length, expected.length)
  const rows: StepRow[] = []
  for (let i = 0; i < n; i++) {
    rows.push({ n: i + 1, action: actions[i] ?? '', data: i === 0 ? data : '', expected: expected[i] ?? '' })
  }
  return rows
}

// Every ref a doc's `covers` field points at (handles both 'link' and 'links').
function coversRefs(doc: DocView): string[] {
  const out: string[] = []
  for (const f of doc.fields as Field[]) {
    if (f.key !== 'covers') continue
    if (f.kind === 'link') out.push(f.ref)
    else if (f.kind === 'links') out.push(...f.refs)
  }
  return out
}

// Normalise "/stories/US-VHLD.md#AC8" -> { story: 'stories/US-VHLD', ac: 'AC8' }
function splitCover(ref: string): { story: string; ac: string | null } {
  const [path, frag] = ref.replace(/^\//, '').split('#')
  return { story: path.replace(/\.md$/, ''), ac: frag ?? null }
}

export function storyTestCases(explorer: ExplorerSnapshot, storyId: string): TcRow[] {
  const target = `stories/${storyId}`
  const rows: TcRow[] = []
  for (const doc of Object.values(explorer.docs)) {
    const level = levelOf(doc.ref)
    if (!level) continue
    const match = coversRefs(doc).map(splitCover).find((c) => c.story === target)
    if (!match) continue
    rows.push({
      id: doc.ref.split('/').pop() as string,
      title: doc.title,
      level,
      status: doc.status,
      ac: match.ac,
      steps: parseTcSteps(doc.body_md),
    })
  }
  return rows.sort((a, b) => a.id.localeCompare(b.id))
}
