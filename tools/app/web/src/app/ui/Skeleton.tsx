// Jira-style loading states. Content that is on its way renders a shimmering
// skeleton (the Jira issue-view pattern), inline waits get the small spinner.
// Both are announced politely to screen readers via role="status".
// (.skel/.skeleton-block are distinct from the legacy .skeleton placeholder class.)

export function Spinner({ size = 16, label = 'Loading' }: { size?: number; label?: string }) {
  return <span className="spinner" role="status" aria-label={label} style={{ width: size, height: size }} />
}

export function Skeleton({ lines = 4, header = false }: { lines?: number; header?: boolean }) {
  return (
    <div className="skeleton-block" role="status" aria-label="Loading">
      {header && <div className="skel skel-header" />}
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skel skel-line" />)}
    </div>
  )
}

// Full-page variant for routes whose data hasn't arrived yet: a heading bar
// plus a paragraph block, in the normal page frame.
export function PageSkeleton() {
  return (
    <div className="page">
      <Skeleton header lines={4} />
    </div>
  )
}
