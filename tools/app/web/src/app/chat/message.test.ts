import { describe, it, expect } from 'vitest'
import { messageText } from './message'

describe('messageText', () => {
  it('concatenates text parts and reads the role', () => {
    const entry = {
      info: { role: 'assistant' },
      parts: [
        { type: 'text', text: 'Reading ' },
        { type: 'tool', tool: 'read' },
        { type: 'text', text: 'sources.' },
      ],
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(messageText(entry as any)).toEqual({ role: 'assistant', text: 'Reading sources.' })
  })
})
