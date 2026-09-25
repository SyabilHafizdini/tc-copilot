export type Crumb = { label: string; onClick?: () => void }

/* Jira-style breadcrumb trail: muted link crumbs separated by " / "; a crumb
 * without onClick (usually the terminal one) renders as plain current-location
 * text. Styling lives on .explore-breadcrumb, shared with the Explore page. */
export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav className="explore-breadcrumb" aria-label="Breadcrumb">
      {items.map((c, i) => (
        <span key={`${i}-${c.label}`}>
          {i > 0 && <span className="sep" aria-hidden="true"> / </span>}
          {c.onClick
            ? <button type="button" className="crumb" onClick={c.onClick}>{c.label}</button>
            : <span className="crumb current" aria-current="page">{c.label}</span>}
        </span>
      ))}
    </nav>
  )
}
