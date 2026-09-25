export type PillState = 'ready' | 'draft' | 'blocked' | 'attn' | 'neutral'

export function Pill({ state, children }: { state: PillState; children: React.ReactNode }) {
  return <span className={`pill ${state}`}>{children}</span>
}
