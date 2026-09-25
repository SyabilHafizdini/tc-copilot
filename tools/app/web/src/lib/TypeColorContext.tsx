import { createContext, useContext, useCallback } from 'react'
import type { ReactNode } from 'react'
import { NODE_TYPE_COLORS, getNodeColor } from './nodeStyle'

/** Defaults to the built-in palette so a component rendered without a provider
 * behaves exactly as it did before type colors were configurable. */
const TypeColorContext = createContext<Record<string, string>>(NODE_TYPE_COLORS)

/** Pass a memoized `colors` value — a freshly built object on every render
 * defeats useNodeColor's stability guarantee and re-runs D3 effects. */
export function TypeColorProvider({
  colors,
  children,
}: {
  /** Must be the output of `resolveTypeColors()` — a fully resolved palette
   * with the twelve built-ins already merged in and every value a six-digit
   * hex string. Passing a raw `meta.typeColors` object directly loses the
   * built-ins, and a non-six-digit value breaks NodeDetailPanel's badge tint
   * (it appends an alpha byte to the hex). */
  colors: Record<string, string>
  children: ReactNode
}): ReactNode {
  return <TypeColorContext.Provider value={colors}>{children}</TypeColorContext.Provider>
}

/** A `(nodeType) => hex` resolver for the nearest provider's palette. Stable as
 * long as the palette is — callers put it in D3 effect dependency arrays. */
export function useNodeColor(): (nodeType: string) => string {
  const colors = useContext(TypeColorContext)
  return useCallback((nodeType: string) => getNodeColor(nodeType, colors), [colors])
}
