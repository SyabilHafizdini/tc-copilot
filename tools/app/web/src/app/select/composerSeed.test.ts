import { describe, expect, it } from 'vitest'
import { bulletList, buildAskSeed, buildCorrectSeed } from './composerSeed'

const items = [
  { ref: 'stories/US-VHLD#AC1', label: 'AC1', type: 'ac' },
  { ref: 'glossary/hold', label: 'hold', type: 'glossary' },
]

describe('composerSeed', () => {
  it('renders one bullet per selected node with label and ref', () => {
    expect(bulletList(items)).toBe(
      '• AC1 (stories/US-VHLD#AC1)\n• hold (glossary/hold)',
    )
  })

  it('askInChat seed is read-only: lists the bullets and prompts a question', () => {
    const seed = buildAskSeed(items)
    expect(seed).toContain('• AC1 (stories/US-VHLD#AC1)')
    expect(seed).toContain('• hold (glossary/hold)')
    expect(seed).toMatch(/Question:/i)
    // read-only: never instructs an edit
    expect(seed).not.toMatch(/Resolution|gated|assert/i)
  })

  it('correctInChat seed names the fence: verbatim Resolution -> cascade -> gated card, no direct edit', () => {
    const seed = buildCorrectSeed(items)
    expect(seed).toContain('• AC1 (stories/US-VHLD#AC1)')
    expect(seed).toMatch(/verbatim/i)
    expect(seed).toMatch(/Resolution/i)
    expect(seed).toMatch(/cascade/i)
    expect(seed).toMatch(/gated card/i)
    expect(seed).toMatch(/assert/i)
    expect(seed).toMatch(/do not edit directly/i)
  })
})
