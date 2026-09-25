export function Banner({
  tone, onDismiss, children,
}: { tone: 'attn' | 'blocked'; onDismiss?: () => void; children: React.ReactNode }) {
  return (
    <div className={`banner ${tone}`} role="status">
      <span>{children}</span>
      {onDismiss && <button className="x" onClick={onDismiss}>dismiss</button>}
    </div>
  )
}
