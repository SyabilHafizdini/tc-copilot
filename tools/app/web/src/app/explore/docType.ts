type DocTypeMeta = { icon: string; label: string; cls: string }

const REGISTRY: Record<string, DocTypeMeta> = {
  'User Story':          { icon: '🎫', label: 'User Story',          cls: 'ds-story' },
  'PRD Section':         { icon: '📄', label: 'PRD Section',         cls: 'ds-prd' },
  'Acceptance Criteria': { icon: '◆', label: 'Acceptance Criteria', cls: 'ds-ac' },
  'Glossary Term':       { icon: '📖', label: 'Glossary Term',       cls: 'ds-term' },
  'Resolution':          { icon: '⚖', label: 'Resolution',          cls: 'ds-resolution' },
  'Test Case':           { icon: '✔', label: 'Test Case',           cls: 'ds-testcase' },
  'Flow':                { icon: '🔀', label: 'Flow',                cls: 'ds-flow' },
}

/** Document-type badge token (design §6.7). Keys are the frontmatter `type`
 * value exactly as the registry names it; unknowns fall back to a neutral
 * badge that echoes the raw string (or "Document" when empty). */
export function docTypeMeta(type: string): DocTypeMeta {
  return REGISTRY[type] ?? { icon: '📃', label: type || 'Document', cls: 'ds-default' }
}
