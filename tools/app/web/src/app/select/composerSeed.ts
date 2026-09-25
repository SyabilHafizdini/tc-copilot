export type SelNode = { ref: string; label: string; type: string }

export function bulletList(items: SelNode[]): string {
  return items.map((i) => `• ${i.label} (${i.ref})`).join('\n')
}

export function buildAskSeed(items: SelNode[]): string {
  return `About:\n${bulletList(items)}\n\nQuestion: `
}

export function buildCorrectSeed(items: SelNode[]): string {
  return (
    'Correction request. Capture my statement verbatim as an append-only ' +
    'Resolution, run the staleness cascade, and emit a gated card for me to ' +
    'assert. Do not edit directly.\n' +
    `${bulletList(items)}\n\nWhat is wrong / what it should be: `
  )
}
