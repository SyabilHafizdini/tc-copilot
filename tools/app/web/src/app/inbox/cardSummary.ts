import type { AlignmentCard } from './types'

export type CardSummary = {
  acs: number
  rules: number
  components: number
  contradictions: number
  openQuestions: number
}

const count = (re: RegExp, s: string): number => {
  const m = re.exec(s)
  return m ? Number(m[1]) : 0
}

export function cardSummary(card: AlignmentCard): CardSummary {
  const u = card.zones.what_i_understood ?? ''
  return {
    acs: count(/(\d+)\s+ACs?\b/i, u),
    rules: count(/(\d+)\s+business rules?\b/i, u),
    components: count(/(\d+)\s+components?\b/i, u),
    contradictions: card.zones.open_questions.filter((q) => /contradict/i.test(q.question)).length,
    openQuestions: card.zones.open_questions.length,
  }
}

export function canAssert(card: AlignmentCard): boolean {
  return card.zones.open_questions.length === 0
}

const humanize = (k: string): string => {
  const words = k.replace(/_/g, ' ').replace(/\btcs\b/i, 'test cases').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function formatAffects(affects: Record<string, unknown>): string[] {
  return Object.entries(affects).map(([k, v]) => {
    const label = humanize(k)
    if (Array.isArray(v)) return `${label}: ${v.length === 0 ? 'none' : v.map(String).join('; ')}`
    if (typeof v === 'string') return `${label}: ${v}`
    return `${label}: ${JSON.stringify(v)}`
  })
}
