import { useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'

const DEFAULT_WIDTH = 360
const MIN_WIDTH = 280
const MAX_WIDTH = 720

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v))
}

/** Width state + a mousedown handler that drags the left edge of a right-docked
 * panel to resize its width. Dragging left widens it; clamped to [min, max]. */
export function useResizableWidth(
  initial: number = DEFAULT_WIDTH,
  min: number = MIN_WIDTH,
  max: number = MAX_WIDTH,
): { width: number; startResize: (e: ReactMouseEvent) => void } {
  const [width, setWidth] = useState(initial)

  const startResize = (e: ReactMouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = width
    const prevUserSelect = document.body.style.userSelect
    document.body.style.userSelect = 'none'
    const onMove = (ev: MouseEvent) => {
      setWidth(clamp(startWidth + (startX - ev.clientX), min, max))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.userSelect = prevUserSelect
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return { width, startResize }
}
