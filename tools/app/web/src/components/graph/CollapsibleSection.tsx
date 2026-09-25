import type { ReactNode } from 'react'
import { useState, useId } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

export interface CollapsibleSectionProps {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  /** Rendered beside the title while collapsed, so a closed section can still
   * carry a one-line digest of what it hides. */
  summary?: ReactNode
}

/** A titled section whose body collapses/expands on header click. Owns its
 * own open state. */
export function CollapsibleSection({
  title,
  children,
  defaultOpen = true,
  summary,
}: CollapsibleSectionProps): ReactNode {
  const [open, setOpen] = useState(defaultOpen)
  const bodyId = useId()
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={open ? bodyId : undefined}
        className="flex w-full items-center gap-1.5 rounded px-1 py-1 text-xs font-medium uppercase tracking-wide text-zinc-500 hover:bg-zinc-50"
      >
        {/* Leads the title rather than trailing at the far edge — on a
            full-width header the trailing position sits hundreds of pixels
            from the label and reads as if there were no control at all. */}
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        )}
        <span className="flex min-w-0 items-baseline gap-2">
          <span>{title}</span>
          {!open && summary && (
            <span className="truncate font-normal normal-case tracking-normal text-zinc-400">
              {summary}
            </span>
          )}
        </span>
      </button>
      {open && (
        <div id={bodyId} className="mt-2">
          {children}
        </div>
      )}
    </div>
  )
}
