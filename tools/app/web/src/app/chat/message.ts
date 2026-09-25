import type { Message, Part } from '@opencode-ai/sdk'

export type ChatEntry = { info: Message; parts: Part[] }

export function messageText(entry: ChatEntry): { role: string; text: string } {
  const text = entry.parts
    .filter((p): p is Extract<Part, { type: 'text' }> => p.type === 'text')
    .map((p) => p.text)
    .join('')
  return { role: entry.info.role, text }
}
