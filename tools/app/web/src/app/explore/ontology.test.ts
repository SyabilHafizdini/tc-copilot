import { describe, it, expect } from 'vitest'
import { buildOntologyTree, ancestorIds } from './ontology'
import type { GraphModel, DocView } from '../explorer/types'

const graph: GraphModel = {
  nodes: [
    { id: 'modules/prod', type: 'Module', label: 'Production', state: 'aligned' },
    { id: 'stories/US-A', type: 'Story', label: 'Story A', state: 'aligned' },
    { id: 'stories/US-B', type: 'Story', label: 'Story B', state: 'aligned' }, // no children
    { id: 'stories/US-A#AC1', type: 'AC', label: 'AC1', state: 'aligned' },
    { id: 'stories/US-A#BR1', type: 'BR', label: 'BR1', state: 'aligned' },
    { id: 'stories/US-A#C1', type: 'Component', label: 'Comp One', state: 'aligned' },
    { id: 'testcases/sit/tc-1', type: 'TC', label: 'tc-1', state: 'active' },
    { id: 'testcases/uat/tc-2', type: 'TC', label: 'tc-2', state: 'active' },
    { id: 'sources/prd/3', type: 'PRD Section', label: 'PRD 3', state: 'aligned' },
    { id: 'glossary/term-x', type: 'Term', label: 'Term X', state: 'aligned' },
  ],
  links: [
    { source: 'stories/US-A', target: 'modules/prod', type: 'module' },
    { source: 'stories/US-B', target: 'modules/prod', type: 'module' },
    { source: 'stories/US-A', target: 'stories/US-A#AC1', type: 'has_ac' },
    { source: 'stories/US-A', target: 'stories/US-A#BR1', type: 'has_br' },
    { source: 'testcases/sit/tc-1', target: 'stories/US-A#AC1', type: 'covers' },
    { source: 'testcases/uat/tc-2', target: 'stories/US-A#BR1', type: 'verifies_rules' },
    // A test case also carries a `module` link — it must NOT surface as a story.
    { source: 'testcases/sit/tc-1', target: 'modules/prod', type: 'module' },
  ],
}
const docs: Record<string, DocView> = {}

describe('buildOntologyTree', () => {
  it('roots at Modules → Story → AC/BR/Component branches, nesting TCs by covers/verifies_rules', () => {
    const forest = buildOntologyTree(graph, docs)
    const modules = forest.find((n) => n.label === 'Modules')
    expect(modules?.nodeType).toBe('group')
    const mod = modules!.children.find((n) => n.ref === 'modules/prod')
    expect(mod?.nodeType).toBe('Module')

    const storyA = mod!.children.find((n) => n.ref === 'stories/US-A')!
    const branchLabels = storyA.children.map((c) => c.label)
    expect(branchLabels).toEqual(['Acceptance Criteria', 'Business Rules', 'Components'])

    const ac = storyA.children[0].children[0]
    expect(ac.ref).toBe('stories/US-A#AC1')
    expect(ac.children.map((t) => t.ref)).toEqual(['testcases/sit/tc-1'])

    const br = storyA.children[1].children[0]
    expect(br.children.map((t) => t.ref)).toEqual(['testcases/uat/tc-2'])
  })

  it('only Story nodes become a module’s children, even when other docs carry a module link', () => {
    const forest = buildOntologyTree(graph, docs)
    const mod = forest[0].children.find((n) => n.ref === 'modules/prod')!
    expect(mod.children.every((c) => c.nodeType === 'Story')).toBe(true)
    expect(mod.children.map((c) => c.ref)).toEqual(['stories/US-A', 'stories/US-B'])
  })

  it('omits empty branches: a childless story is a selectable leaf', () => {
    const forest = buildOntologyTree(graph, docs)
    const mod = forest[0].children.find((n) => n.ref === 'modules/prod')!
    const storyB = mod.children.find((n) => n.ref === 'stories/US-B')!
    expect(storyB.children).toHaveLength(0)
    expect(storyB.ref).toBe('stories/US-B')
  })

  it('hangs non-module docs off sibling top-level groups', () => {
    const labels = buildOntologyTree(graph, docs).map((n) => n.label)
    expect(labels).toContain('Sources (PRD)')
    expect(labels).toContain('Glossary')
  })

  it('ancestorIds returns the open-path to a nested AC', () => {
    const forest = buildOntologyTree(graph, docs)
    const trail = ancestorIds(forest, 'stories/US-A#AC1')
    expect(trail).toEqual(['grp::modules', 'modules/prod', 'stories/US-A', 'stories/US-A::ac'])
  })
})
