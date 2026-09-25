export type OpenQuestion = { id: string; about: string; question: string; proposed: string }
export type AlignmentZones = {
  what_you_said: string[]; what_i_understood: string; what_i_changed: string[]
  what_this_affects: Record<string, unknown>; open_questions: OpenQuestion[]; actions: string[]
}
export type AlignmentCard = {
  file: string; card_type: 'alignment'; story: string | null; session?: string | null; emitted_at: string | null
  zones: AlignmentZones
}
export type MapCorrection = { ac: string; removed: string[]; added: string[]; reason: string }
export type CoverageCard = {
  file: string; card_type: 'coverage'; story: string | null; session?: string | null; emitted_at: string | null
  coverage_status: string | null; map_corrections: MapCorrection[]; note: string | null
}
export type InboxCard = AlignmentCard | CoverageCard
export type InboxSnapshot = { cards: InboxCard[] }
