import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { refToNodeId } from './FrontmatterFields'

const isWikiPath = (href: string) => /^\/[^)#\s]+\.md(#.+)?$/.test(href)

export function MarkdownBody({ body, onNavigate }: {
  body: string; onNavigate: (nodeId: string) => void
}) {
  return (
    <div className="markdown-body">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            if (href && isWikiPath(href)) {
              return (
                <a href={href} onClick={(e) => { e.preventDefault(); onNavigate(refToNodeId(href)) }}>
                  {children}
                </a>
              )
            }
            return <a href={href}>{children}</a>
          },
        }}
      >
        {body}
      </Markdown>
    </div>
  )
}
