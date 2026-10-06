import type { ReactNode } from 'react'

// Test-case text as the workbook shows it: `**x**` is bold, em / en dashes
// are hyphens (tc-style), and line breaks and leading indentation are kept
// (.rich-text is white-space: pre-wrap). MarkdownBody is not reused: it
// would turn "1." lines into a list and reflow the lettered element block.
export function RichText({ text }: { text: string }) {
  const nodes: ReactNode[] = text
    .replace(/[–—]/g, '-')
    .split(/\*\*([\s\S]+?)\*\*/g)
    .map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))
  return <span className="rich-text">{nodes}</span>
}
