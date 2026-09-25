import type { GraphNode } from './types'

export const NODE_TYPE_COLORS: Record<string, string> = {
  Page: '#3B82F6',
  Component: '#10B981',
  Field: '#F59E0B',
  Action: '#8B5CF6',
  ValidationRule: '#EF4444',
  BusinessRule: '#F97316',
  APIEndpoint: '#06B6D4',
  APIResponse: '#14B8A6',
  DBColumn: '#6B7280',
  UserStory: '#EC4899',
  State: '#6366F1',
  TestCase: '#FACC15',
}

export const DEFAULT_NODE_COLOR = '#9CA3AF'

const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

/** `#abc` → `#aabbcc`. Six-digit input is returned unchanged. The expansion is
 * required, not cosmetic: NodeDetailPanel builds its badge tint by appending an
 * alpha byte to the hex, and `#abc1A` is not a valid color. */
function expandHex(hex: string): string {
  if (hex.length !== 4) return hex
  return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`
}

/** A graph's `meta.typeColors` layered over the built-in palette: an override
 * replaces a built-in name, an unknown name is added, everything else survives.
 * Malformed values are skipped defensively — validateGraph rejects them first,
 * so reaching that branch means the document bypassed validation. */
export function resolveTypeColors(
  overrides?: Record<string, string>,
): Record<string, string> {
  if (!overrides) return { ...NODE_TYPE_COLORS }
  const out: Record<string, string> = { ...NODE_TYPE_COLORS }
  for (const [nodeType, color] of Object.entries(overrides)) {
    if (typeof color === 'string' && HEX_COLOR.test(color)) {
      out[nodeType] = expandHex(color)
    }
  }
  return out
}

/** Low-level primitive: a plain lookup against a resolved palette. Components
 * should not call this directly — reach through `useNodeColor()` so they pick
 * up the current graph's palette instead of silently falling back to the
 * built-in twelve. */
export function getNodeColor(
  nodeType: string,
  colors: Record<string, string>,
): string {
  return colors[nodeType] ?? DEFAULT_NODE_COLOR
}

export function getNodeLabel(node: GraphNode): string {
  const name = node.properties.name as string | undefined
  return (
    node.displayLabel ||
    name ||
    node.nodeId.split('_').pop() ||
    node.nodeId
  )
}
