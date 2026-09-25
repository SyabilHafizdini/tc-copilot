import { describe, it, expect } from 'vitest'
import { docTypeMeta } from './docType'

describe('docTypeMeta', () => {
  it.each([
    ['User Story',          '🎫', 'User Story',          'ds-story'],
    ['PRD Section',         '📄', 'PRD Section',         'ds-prd'],
    ['Acceptance Criteria', '◆', 'Acceptance Criteria', 'ds-ac'],
    ['Glossary Term',       '📖', 'Glossary Term',       'ds-term'],
    ['Resolution',          '⚖', 'Resolution',          'ds-resolution'],
    ['Test Case',           '✔', 'Test Case',           'ds-testcase'],
    ['Flow',                '🔀', 'Flow',                'ds-flow'],
  ])('maps %s to its icon/label/cls', (type, icon, label, cls) => {
    expect(docTypeMeta(type)).toEqual({ icon, label, cls })
  })

  it('falls back to a default for an unknown type, echoing the raw string as the label', () => {
    expect(docTypeMeta('Module')).toEqual({ icon: '📃', label: 'Module', cls: 'ds-default' })
  })

  it('labels an empty type as "Document"', () => {
    expect(docTypeMeta('')).toEqual({ icon: '📃', label: 'Document', cls: 'ds-default' })
  })
})
