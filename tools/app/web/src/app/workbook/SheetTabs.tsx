// Sheet tabs along the bottom, in file order, as Excel shows them.
export function SheetTabs({ names, active, onSelect }: {
  names: string[]
  active: string
  onSelect: (name: string) => void
}) {
  return (
    <div className="wb-tabs" role="tablist" aria-label="Sheets">
      {names.map((name) => (
        <button key={name} role="tab" className="wb-tab"
          aria-selected={name === active} onClick={() => onSelect(name)}>
          {name}
        </button>
      ))}
    </div>
  )
}
