export function StatTile({ n, label, sub }: { n: React.ReactNode; label: string; sub?: React.ReactNode }) {
  return (
    <div className="stat">
      <span className="n">{n}</span>
      <span className="l">{label}</span>
      {sub != null && <span className="sub">{sub}</span>}
    </div>
  )
}
