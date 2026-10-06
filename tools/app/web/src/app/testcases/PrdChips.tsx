/* One chip per PRD the listed test cases draw on, labelled with the PRD's
 * title when one is known and its id otherwise. Hidden when there is none, so
 * a project with no PRD (or one whose test cases predate prd_versions) shows
 * no empty filter. */
export function PrdChips({ options, selected, onToggle, titles }: {
  options: string[]
  selected: string[]
  onToggle: (id: string) => void
  titles?: Record<string, string>
}) {
  if (options.length === 0) return null
  return (
    <div className="level-filter" role="group" aria-label="PRD">
      {options.map((id) => (
        <button key={id} type="button"
          className={`chip${selected.includes(id) ? ' on' : ''}`}
          aria-pressed={selected.includes(id)}
          onClick={() => onToggle(id)}>
          {titles?.[id] || id}
        </button>
      ))}
    </div>
  )
}
