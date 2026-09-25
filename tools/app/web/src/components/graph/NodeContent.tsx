import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { useState, useRef, useCallback, useEffect } from 'react'
import ReactMarkdown, { defaultUrlTransform, type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Check, Copy } from 'lucide-react'
import 'highlight.js/styles/github.css'

/** Pull `language-xxx` off the child <code>'s className (added by markdown/highlight). */
function languageOf(children: ReactNode): string | null {
  if (children && typeof children === 'object' && 'props' in children) {
    const className = (children as { props?: { className?: string } }).props?.className ?? ''
    const m = /language-(\w+)/.exec(className)
    if (m) return m[1]
  }
  return null
}

/** A fenced code block: language label + copy button over the highlighted <pre>. */
function CodeBlock(preProps: ComponentPropsWithoutRef<'pre'> & { node?: unknown }): ReactNode {
  const { node: _node, children, className, ...rest } = preProps
  const preRef = useRef<HTMLPreElement>(null)
  const [copied, setCopied] = useState(false)
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const language = languageOf(children)

  useEffect(() => () => {
    if (resetTimer.current) clearTimeout(resetTimer.current)
  }, [])

  const copy = useCallback(async () => {
    const text = preRef.current?.textContent ?? ''
    setCopied(true)
    if (resetTimer.current) clearTimeout(resetTimer.current)
    resetTimer.current = setTimeout(() => setCopied(false), 1500)
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      try {
        document.execCommand('copy')
      } catch {
        /* clipboard unavailable — best effort */
      }
      document.body.removeChild(ta)
    }
  }, [])

  return (
    <div
      className="my-2 overflow-hidden rounded-md border border-zinc-200 bg-zinc-50"
      data-testid="code-block"
    >
      <div className="flex items-center justify-between border-b border-zinc-200 px-2 py-1">
        <span className="font-mono text-[10px] uppercase tracking-wide text-zinc-400">
          {language ?? 'code'}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label="Copy code"
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700"
        >
          {copied ? <Check className="size-3" aria-hidden="true" /> : <Copy className="size-3" aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre ref={preRef} className={`overflow-x-auto p-3 text-xs leading-relaxed ${className ?? ''}`} {...rest}>
        {children}
      </pre>
    </div>
  )
}

/** react-markdown's default urlTransform strips `data:` URIs entirely (they aren't in its
 * safe-protocol allowlist). Allow them through only for `img[src]` — the `img` renderer below
 * still only paints `data:` images, so this doesn't loosen anything else (links, etc. keep
 * the default sanitization). */
function urlTransform(url: string, key: string, node: { tagName?: string }): string {
  if (key === 'src' && node.tagName === 'img' && url.startsWith('data:')) return url
  return defaultUrlTransform(url)
}

const COMPONENTS: Components = {
  pre: CodeBlock,
  a({ node: _node, children, href }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
        {children}
      </a>
    )
  },
  img({ node: _node, src, alt }) {
    // Keep the viewer self-contained: only inline data-URI images render.
    // A remote URL would fetch at view time, so show it as an inert link instead.
    if (typeof src === 'string' && src.startsWith('data:')) {
      return <img src={src} alt={alt ?? ''} className="max-w-full rounded" />
    }
    return (
      <a href={src} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
        {alt || src}
      </a>
    )
  },
}

/** Render a node's markdown content: prose + GFM + syntax-highlighted fenced code.
 * Raw HTML is NOT rendered (no rehype-raw) so untrusted content cannot inject DOM. */
export function NodeContent({ markdown }: { markdown: string }): ReactNode {
  if (!markdown || markdown.trim() === '') return null
  return (
    <div
      data-testid="node-content"
      className="text-sm leading-relaxed text-zinc-800 [&_a]:break-words [&_code]:font-mono [&_h1]:mt-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-2 [&_h2]:text-sm [&_h2]:font-semibold [&_li]:ml-4 [&_li]:list-disc [&_ol]:my-1.5 [&_p]:my-1.5 [&_ul]:my-1.5"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { aliases: { typescript: ['tsx'], javascript: ['jsx'] }, ignoreMissing: true }]]}
        components={COMPONENTS}
        urlTransform={urlTransform}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
