// Shapes served by GET /api/testcases (tools/app/testcase_models.py).

export type PartKey = 'scenario' | 'steps' | 'data' | 'expected'

// The fields `wiki tc edit` accepts (tools/wiki_tcedit.py SIT_FIELDS / UAT_FIELDS).
export type EditableField =
  | 'title' | 'objective' | 'steps' | 'data' | 'expected' | 'post' | 'pre_extra' | 'priority'

export type TcLevel = 'sit' | 'uat'
export type ConfidenceLevel = 'High' | 'Medium' | 'Low'

export type TcPart = {
  level: ConfidenceLevel | null
  // Only on a part a human confirmation lifted to High: the level the spec
  // authored, which the part returns to when its text is reworded.
  authored?: ConfidenceLevel | null
  remark: string
  // Doubt state of a Medium / Low part: 'open' | 'answered' | 'rewritten' |
  // 'closed' (confirmed). null for a High part.
  state: string | null
  question: string | null
  resolution: string | null
}

export type TcRow = {
  ref: string                 // testcases/sit/<module>/<id> - the markdown file
  id: string
  display_id: string          // TC-... as the workbook prints it
  level: TcLevel
  story: string | null
  flow: string | null
  module: string | null
  run: string | null
  section: string | null
  order: number | null
  group: string               // TcGroup.key
  status: string | null
  priority: string | null
  technique: string | null
  covers: string[]
  prds: string[]              // PRD ids the case draws on (generated_from.prd_versions); [] when none
  title: string
  objective: string
  scenario: string            // Given / When / Then, derived from the story AC
  chain: string               // "Continue from TC-..." / "Start of run: ..."
  steps: string
  data: string
  expected: string            // the case's own items
  element_block: string       // the lettered element list, derived
  pre_extra: string
  post: string
  confidence: ConfidenceLevel | ''
  parts: Record<PartKey, TcPart>
  // Which editable fields make up each confidence part (wiki_doubts.PART_TEXT).
  part_fields: Record<PartKey, string[]>
  // The workbook's own cells, text with **bold** markers.
  cells: { scenario: string; steps: string; data: string; expected: string; remarks: string }
  editable: EditableField[]
  spec: string | null
}

export type TcGroup = {
  key: string
  label: string
  kind: 'run' | 'module' | 'flow'
  level: TcLevel
  sections: string[]
  common: string[]            // the sheet's shared pre-condition lines (may be empty)
}

export type TestCasesPayload = { rows: TcRow[]; groups: TcGroup[] }
