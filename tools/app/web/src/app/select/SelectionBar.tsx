import { ArrowUpRight, X } from 'lucide-react'
import { useSelection } from './selection'

export function SelectionBar() {
  const { items, askInChat, clear } = useSelection()
  if (items.length === 0) return null
  return (
    <div className="selbar" role="region" aria-label="Selection">
      <span className="selbar-count">{items.length} selected</span>
      <button className="selbar-ask" onClick={askInChat}>
        <ArrowUpRight size={14} /> Ask in chat
      </button>
      <button className="selbar-clear" onClick={clear}>
        <X size={13} /> Clear
      </button>
    </div>
  )
}
